from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.auth.service import issue_otp, normalize_email
from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    password_needs_rehash,
    verify_password,
    verify_token,
)
from app.db.session import get_db
from app.models.auth import AppUser, AuthCredential, AuthOtpCode, AuthRefreshToken
from app.schemas.auth import (
    EmailOtpRequest,
    EmailRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)
from app.services.tpi_email import EmailDeliveryError

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        "trex_refresh_token",
        token,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 86400,
        path="/api/v1/auth",
    )


async def create_session(db: AsyncSession, user: AppUser, response: Response) -> TokenResponse:
    settings = get_settings()
    access_token, expires_in = create_access_token(user.id, user.role)
    refresh_token = generate_refresh_token()
    db.add(
        AuthRefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
        )
    )
    await db.commit()
    set_refresh_cookie(response, refresh_token)
    return TokenResponse(
        access_token=access_token,
        expires_in=expires_in,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/register", status_code=201, response_model=RegisterResponse)
async def register(
    payload: RegisterRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> RegisterResponse:
    email = normalize_email(payload.email)
    if await db.scalar(select(AppUser.id).where(AppUser.email == email)):
        raise HTTPException(409, "An account with this email already exists")
    user = AppUser(email=email, role="customer")
    user.credential = AuthCredential(password_hash=hash_password(payload.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    try:
        await issue_otp(db, user, "verify_email")
    except EmailDeliveryError:
        return RegisterResponse(
            message=(
                "Account created, but the verification email could not be delivered. "
                "Use resend verification to try again."
            ),
            verification_email_sent=False,
        )
    return RegisterResponse(
        message="Registration successful. Check your email for the verification code.",
        verification_email_sent=True,
    )


@router.post("/verify-email")
async def verify_email(
    payload: EmailOtpRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> dict:
    user = await db.scalar(select(AppUser).where(AppUser.email == normalize_email(payload.email)))
    if user is None:
        raise HTTPException(400, "Invalid verification request")
    if user.email_verified_at:
        return {"message": "Email is already verified"}
    await _consume_otp(db, user, "verify_email", payload.code)
    user.email_verified_at = datetime.now(UTC)
    await db.commit()
    return {"message": "Email verified successfully"}


@router.post("/resend-verification")
async def resend_verification(
    payload: EmailRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> dict:
    user = await db.scalar(select(AppUser).where(AppUser.email == normalize_email(payload.email)))
    if user and not user.email_verified_at:
        try:
            await issue_otp(db, user, "verify_email")
        except EmailDeliveryError as exc:
            raise HTTPException(
                503, "Verification email delivery is temporarily unavailable. Please try again."
            ) from exc
    return {"message": "If the account is eligible, a verification code has been sent"}


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    user = await db.scalar(select(AppUser).where(AppUser.email == normalize_email(payload.email)))
    if (
        not user
        or not user.credential
        or not verify_password(payload.password, user.credential.password_hash)
    ):
        raise HTTPException(401, "Invalid email or password")
    if not user.email_verified_at:
        raise HTTPException(403, "Verify your email before signing in")
    if password_needs_rehash(user.credential.password_hash):
        user.credential.password_hash = hash_password(payload.password)
        await db.commit()
    return await create_session(db, user, response)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    cookie_token: Annotated[str | None, Cookie(alias="trex_refresh_token")] = None,
):
    raw_token = payload.refresh_token or cookie_token
    if not raw_token:
        raise HTTPException(401, "Refresh token required")
    now = datetime.now(UTC)
    stored = await db.scalar(
        select(AuthRefreshToken).where(AuthRefreshToken.token_hash == hash_token(raw_token))
    )
    if not stored or stored.revoked_at or stored.expires_at <= now:
        raise HTTPException(401, "Invalid or expired refresh token")
    user = await db.get(AppUser, stored.user_id)
    stored.revoked_at = now
    result = await create_session(db, user, response)
    replacement = await db.scalar(
        select(AuthRefreshToken).where(
            AuthRefreshToken.token_hash == hash_token(result.refresh_token)
        )
    )
    stored.replaced_by_token_id = replacement.id
    await db.commit()
    return result


@router.post("/logout", status_code=204)
async def logout(
    payload: LogoutRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    cookie_token: Annotated[str | None, Cookie(alias="trex_refresh_token")] = None,
):
    raw_token = payload.refresh_token or cookie_token
    if raw_token:
        await db.execute(
            update(AuthRefreshToken)
            .where(AuthRefreshToken.token_hash == hash_token(raw_token))
            .values(revoked_at=datetime.now(UTC))
        )
        await db.commit()
    response.delete_cookie("trex_refresh_token", path="/api/v1/auth")
    response.status_code = 204


@router.post("/forgot-password")
async def forgot_password(
    payload: EmailRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> dict:
    user = await db.scalar(select(AppUser).where(AppUser.email == normalize_email(payload.email)))
    if user and user.email_verified_at:
        await issue_otp(db, user, "reset_password")
    return {"message": "If the account exists, a reset code has been sent"}


@router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> dict:
    user = await db.scalar(select(AppUser).where(AppUser.email == normalize_email(payload.email)))
    if user is None:
        raise HTTPException(400, "Invalid reset request")
    await _consume_otp(db, user, "reset_password", payload.code)
    user.credential.password_hash = hash_password(payload.new_password)
    await db.execute(
        update(AuthRefreshToken)
        .where(AuthRefreshToken.user_id == user.id, AuthRefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    await db.commit()
    return {"message": "Password reset successfully"}


@router.get("/me", response_model=UserResponse)
async def me(
    current: Annotated[AuthenticatedUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await db.get(AppUser, current.user_id)


async def _consume_otp(db: AsyncSession, user: AppUser, purpose: str, code: str) -> None:
    settings = get_settings()
    otp = await db.scalar(
        select(AuthOtpCode)
        .where(
            AuthOtpCode.user_id == user.id,
            AuthOtpCode.purpose == purpose,
            AuthOtpCode.used_at.is_(None),
        )
        .order_by(AuthOtpCode.created_at.desc())
        .limit(1)
    )
    now = datetime.now(UTC)
    if not otp or otp.expires_at <= now or otp.attempt_count >= settings.otp_max_attempts:
        raise HTTPException(400, "The code is invalid or expired")
    if not verify_token(code, otp.code_hash):
        otp.attempt_count += 1
        await db.commit()
        raise HTTPException(400, "The code is invalid or expired")
    otp.used_at = now
