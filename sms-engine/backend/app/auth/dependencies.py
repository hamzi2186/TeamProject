import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: uuid.UUID
    role: str


@lru_cache
def jwk_client() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(get_settings().auth_jwks_url, cache_keys=True)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    demo_user_id: Annotated[str | None, Header(alias="X-Demo-User-Id")] = None,
) -> AuthenticatedUser:
    settings = get_settings()
    if credentials:
        try:
            signing_key = jwk_client().get_signing_key_from_jwt(credentials.credentials)
            claims = jwt.decode(
                credentials.credentials,
                signing_key.key,
                algorithms=["RS256"],
                audience=settings.auth_audience,
                issuer=settings.auth_issuer,
            )
            return AuthenticatedUser(user_id=uuid.UUID(claims["sub"]), role=claims["role"])
        except (jwt.PyJWTError, KeyError, ValueError) as exc:
            raise HTTPException(401, "Invalid access token") from exc
    if settings.app_env != "production" and settings.allow_demo_identity and demo_user_id:
        try:
            return AuthenticatedUser(user_id=uuid.UUID(demo_user_id), role="developer")
        except ValueError as exc:
            raise HTTPException(400, "X-Demo-User-Id must be a UUID") from exc
    raise HTTPException(401, "Authentication required")


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


def require_internal_service(
    service_token: Annotated[str, Header(alias="X-SMS-Service-Token")],
) -> None:
    import secrets

    if not secrets.compare_digest(service_token, get_settings().sms_internal_service_token):
        raise HTTPException(401, "Invalid internal service credentials")
