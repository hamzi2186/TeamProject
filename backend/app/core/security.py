from dataclasses import dataclass
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.keys import ensure_jwt_keys, load_public_key

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: UUID
    role: str
    email: str


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    public_key = load_public_key()
    return jwt.decode(
        token,
        public_key,
        algorithms=[settings.auth_jwt_algorithm],
        audience=settings.auth_audience,
        issuer=settings.auth_issuer,
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> AuthenticatedUser:
    """
    Validate the RS256 Bearer JWT issued by the shared root auth service.
    Calling Engine is a token consumer — it does NOT look up the DB; it trusts
    the signed claims from the root platform.
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        payload = decode_access_token(credentials.credentials)
        if payload.get("type") != "access":
            raise ValueError("Token type must be 'access'")
        user_id = UUID(payload["sub"])
        role = payload.get("role", "customer")
        email = payload.get("email", "")
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired access token") from exc
    return AuthenticatedUser(user_id=user_id, role=role, email=email)


CurrentUser = Depends(get_current_user)


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def verify_secret(value: str, encoded: str) -> bool:
    return secrets.compare_digest(hash_secret(value), encoded)


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def digest_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_access_token(user_id: UUID, role: str) -> tuple[str, int]:
    settings = get_settings()
    private_key, _ = ensure_jwt_keys()
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "role": role, "type": "access", "iss": settings.auth_issuer, "aud": settings.auth_audience, "iat": now, "exp": expires, "jti": str(uuid4())}
    import jwt as jwt_module
    return jwt_module.encode(payload, private_key, algorithm=settings.auth_jwt_algorithm), int((expires - now).total_seconds())
