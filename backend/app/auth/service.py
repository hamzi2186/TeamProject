from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import generate_otp, hash_token
from app.models.auth import AppUser, AuthOtpCode
from app.services.tpi_email import EmailDeliveryError, send_auth_email


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def issue_otp(db: AsyncSession, user: AppUser, purpose: str) -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    latest = await db.scalar(
        select(AuthOtpCode)
        .where(
            AuthOtpCode.user_id == user.id,
            AuthOtpCode.purpose == purpose,
            AuthOtpCode.used_at.is_(None),
        )
        .order_by(AuthOtpCode.created_at.desc())
        .limit(1)
    )
    if latest and latest.created_at:
        created_at = latest.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        elapsed = (now - created_at).total_seconds()
        if elapsed < settings.otp_resend_cooldown_seconds:
            retry_after = int(settings.otp_resend_cooldown_seconds - elapsed)
            raise HTTPException(
                429, f"Please wait {retry_after} seconds before requesting another code"
            )
    await db.execute(
        update(AuthOtpCode)
        .where(
            AuthOtpCode.user_id == user.id,
            AuthOtpCode.purpose == purpose,
            AuthOtpCode.used_at.is_(None),
        )
        .values(used_at=now)
    )
    code = generate_otp()
    otp = AuthOtpCode(
        user_id=user.id,
        purpose=purpose,
        code_hash=hash_token(code),
        expires_at=now + timedelta(minutes=settings.otp_expire_minutes),
    )
    db.add(otp)
    await db.commit()
    print(f"\n==================================================", flush=True)
    print(f"[*] [AUTH OTP CODE] To: {user.email}", flush=True)
    print(f"[*] 6-Digit OTP Code: {code}", flush=True)
    print(f"[*] Purpose: {purpose}", flush=True)
    print(f"==================================================\n", flush=True)
    template = "verify_email" if purpose == "verify_email" else "reset_password"
    try:
        await send_auth_email(to=user.email, template=template, code=code)
    except EmailDeliveryError:
        app_env = getattr(settings, "app_env", "production")
        if app_env == "production":
            otp.used_at = datetime.now(UTC)
            await db.commit()
            raise
        import logging
        logging.getLogger("auth").warning("Email delivery failed in %s for %s. OTP Code: %s", app_env, user.email, code)

