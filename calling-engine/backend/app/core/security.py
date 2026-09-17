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
