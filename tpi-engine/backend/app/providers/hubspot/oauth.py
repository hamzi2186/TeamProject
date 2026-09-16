import json
import secrets
from typing import Protocol
from urllib.parse import urlencode
from uuid import UUID

from app.providers.hubspot.errors import InvalidOAuthStateError

AUTHORIZE_URL = "https://app.hubspot.com/oauth/authorize"


class RedisStateClient(Protocol):
    async def set(self, key: str, value: str, *, ex: int, nx: bool) -> object: ...

    async def getdel(self, key: str) -> bytes | str | None: ...


class OAuthStateStore:
    def __init__(self, redis_client: RedisStateClient, ttl_seconds: int = 600) -> None:
        self._redis = redis_client
        self.ttl_seconds = ttl_seconds

    async def create(self, user_id: UUID) -> str:
        for _ in range(3):
            state = secrets.token_urlsafe(32)
            stored = await self._redis.set(
                f"tpi:hubspot:oauth-state:{state}",
                json.dumps({"user_id": str(user_id)}),
                ex=self.ttl_seconds,
                nx=True,
            )
            if stored:
                return state
        raise RuntimeError("Unable to allocate OAuth state")

    async def consume(self, state: str) -> UUID:
        if not state or len(state) > 256:
            raise InvalidOAuthStateError("OAuth state is invalid or expired")
        raw = await self._redis.getdel(f"tpi:hubspot:oauth-state:{state}")
        if raw is None:
            raise InvalidOAuthStateError("OAuth state is invalid, expired, or already used")
        try:
            payload = json.loads(raw)
            return UUID(payload["user_id"])
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise InvalidOAuthStateError("OAuth state is malformed") from exc


def build_authorization_url(
    *, client_id: str, redirect_uri: str, scopes: list[str], state: str
) -> str:
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes),
            "state": state,
        }
    )
    return f"{AUTHORIZE_URL}?{query}"
