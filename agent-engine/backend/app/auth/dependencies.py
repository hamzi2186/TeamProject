import secrets
import time
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import httpx
import jwt
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.algorithms import RSAAlgorithm

from app.core.config import get_settings

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: UUID
    role: str


class JWKSVerifier:
    def __init__(self) -> None:
        self._keys: dict[str, object] = {}
        self._expires_at = 0.0

    async def verify(self, token: str) -> dict:
        settings = get_settings()
        try:
            header = jwt.get_unverified_header(token)
            key_id = header.get("kid")
            if time.monotonic() >= self._expires_at or (
                key_id is not None and key_id not in self._keys
            ):
                await self._refresh()
            if key_id is not None:
                key = self._keys[key_id]
            elif len(self._keys) == 1:
                key = next(iter(self._keys.values()))
            else:
                raise ValueError("Token has no key identifier")
            return jwt.decode(
                token,
                key,
                algorithms=[settings.auth_jwt_algorithm],
                audience=settings.auth_audience,
                issuer=settings.auth_issuer,
            )
        except (KeyError, jwt.PyJWTError, ValueError) as exc:
            raise HTTPException(401, "Invalid or expired access token") from exc

    async def _refresh(self) -> None:
        settings = get_settings()
        try:
            async with httpx.AsyncClient(timeout=5, trust_env=False) as client:
                response = await client.get(settings.auth_jwks_url)
                response.raise_for_status()
                keys = response.json()["keys"]
            self._keys = {
                item["kid"]: RSAAlgorithm.from_jwk(item)
                for item in keys
                if item.get("kid") and item.get("kty") == "RSA"
            }
            if not self._keys:
                raise ValueError("No supported signing keys")
            self._expires_at = time.monotonic() + 300
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise HTTPException(503, "Authentication service is unavailable") from exc


verifier = JWKSVerifier()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> AuthenticatedUser:
    if credentials is None:
        raise HTTPException(401, "Authentication required")
    payload = await verifier.verify(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(401, "Invalid access token type")
    try:
        return AuthenticatedUser(user_id=UUID(payload["sub"]), role=payload["role"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(401, "Invalid access token claims") from exc


async def require_admin_or_dev(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
) -> AuthenticatedUser:
    if user.role not in {"developer", "team_member", "admin"}:
        raise HTTPException(403, "Insufficient permissions")
    return user


def require_internal_service(
    x_agent_service_token: Annotated[str | None, Header(alias="X-Agent-Service-Token")] = None,
) -> None:
    if not x_agent_service_token or not secrets.compare_digest(
        x_agent_service_token, get_settings().agent_internal_service_token
    ):
        raise HTTPException(401, "Invalid internal service credentials")


async def require_admin_or_internal_service(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)] = None,
    x_agent_service_token: Annotated[str | None, Header(alias="X-Agent-Service-Token")] = None,
) -> None:
    # 1. Try service token
    if x_agent_service_token and secrets.compare_digest(
        x_agent_service_token, get_settings().agent_internal_service_token
    ):
        return

    # 2. Try JWT
    if credentials:
        user = await get_current_user(credentials)
        if user.role in {"developer", "team_member", "admin"}:
            return
        raise HTTPException(403, "Insufficient permissions")

    raise HTTPException(401, "Authentication required (service token or privileged JWT)")

