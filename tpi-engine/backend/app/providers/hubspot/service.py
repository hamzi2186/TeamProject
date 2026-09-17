from datetime import UTC, datetime, timedelta
from functools import lru_cache
from uuid import UUID

import httpx
from redis.asyncio import Redis

from app.core.config import get_settings
from app.providers.hubspot.client import HubSpotClient
from app.providers.hubspot.crypto import TokenCipher
from app.providers.hubspot.errors import (
    HubSpotConfigurationError,
    ConnectionNotFoundError,
    ConnectionRevokedError,
    HubSpotError,
    OAuthDeniedError,
    ProviderAuthError,
    TokenRefreshError,
)
from app.providers.hubspot.oauth import OAuthStateStore, build_authorization_url
from app.providers.hubspot.repository import (
    ConnectionRepository,
    HubSpotConnectionRecord,
    SqlAlchemyConnectionRepository,
)
from app.providers.hubspot.schemas import (
    CallbackResponse,
    ConnectionStatusResponse,
    ConnectResponse,
    ContactPage,
)


class HubSpotService:
    def __init__(
        self,
        *,
        client: HubSpotClient,
        repository: ConnectionRepository,
        state_store: OAuthStateStore,
        cipher: TokenCipher,
        client_id: str,
        redirect_uri: str,
        scopes: list[str],
        refresh_skew_seconds: int = 300,
    ) -> None:
        self._client = client
        self._repository = repository
        self._state_store = state_store
        self._cipher = cipher
        self._client_id = client_id
        self._redirect_uri = redirect_uri
        self._scopes = scopes
        self._refresh_skew = timedelta(seconds=refresh_skew_seconds)

    async def create_authorization_url(self, user_id: UUID) -> ConnectResponse:
        if not self._client_id or self._client_id.startswith("replace-"):
            raise HubSpotConfigurationError("HubSpot OAuth credentials are not configured in the shared .env file")
        state = await self._state_store.create(user_id)
        return ConnectResponse(
            authorization_url=build_authorization_url(
                client_id=self._client_id,
                redirect_uri=self._redirect_uri,
                scopes=self._scopes,
                state=state,
            ),
            expires_in=self._state_store.ttl_seconds,
        )

    async def complete_oauth(
        self, *, state: str, code: str | None, provider_error: str | None
    ) -> CallbackResponse:
        user_id = await self._state_store.consume(state)
        if provider_error:
            raise OAuthDeniedError("HubSpot authorization was denied")
        if not code:
            raise OAuthDeniedError("HubSpot authorization code was not provided")
        token_set = await self._client.exchange_code(code)
        portal_id = await self._client.get_portal_id(token_set.access_token)
        refresh_token = token_set.refresh_token
        if not refresh_token:
            raise ConnectionRevokedError("HubSpot did not issue a refresh credential")
        scopes = token_set.scopes or self._scopes
        await self._repository.upsert(
            user_id=user_id,
            portal_id=portal_id,
            encrypted_access_token=self._cipher.encrypt(token_set.access_token),
            encrypted_refresh_token=self._cipher.encrypt(refresh_token),
            expires_at=datetime.now(UTC) + timedelta(seconds=token_set.expires_in),
            scopes=scopes,
        )
        return CallbackResponse(connected=True, status="connected", portal_id=portal_id)

    async def connection_status(self, user_id: UUID) -> ConnectionStatusResponse:
        connection = await self._repository.latest_for_user(user_id)
        if connection is None:
            return ConnectionStatusResponse(status="disconnected", connected=False)
        return ConnectionStatusResponse(
            status=connection.status,
            connected=connection.status == "connected",
            portal_id=connection.hubspot_portal_id,
            scopes=connection.scopes,
            created_at=connection.created_at,
            updated_at=connection.updated_at,
            expires_at=connection.expires_at,
        )

    async def contacts(
        self, user_id: UUID, *, after: str | None = None, limit: int = 100
    ) -> ContactPage:
        connection = await self._repository.latest_for_user(user_id)
        if connection is None:
            raise ConnectionNotFoundError("HubSpot is not connected")
        if connection.status != "connected":
            raise ConnectionRevokedError("HubSpot connection is not active")
        access_token = await self._valid_access_token(connection)
        try:
            return await self._client.get_contacts(access_token, after=after, limit=limit)
        except ProviderAuthError as exc:
            await self._repository.set_status(
                connection.id, user_id=connection.user_id, status="disconnected"
            )
            raise ConnectionRevokedError("HubSpot connection was revoked") from exc

    async def _valid_access_token(self, connection: HubSpotConnectionRecord) -> str:
        now = datetime.now(UTC)
        expires_at = connection.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at > now + self._refresh_skew:
            return self._cipher.decrypt(connection.encrypted_access_token)
        refresh_token = self._cipher.decrypt(connection.encrypted_refresh_token)
        try:
            refreshed = await self._client.refresh(refresh_token)
        except (TokenRefreshError, ProviderAuthError) as exc:
            await self._repository.set_status(
                connection.id, user_id=connection.user_id, status="disconnected"
            )
            raise ConnectionRevokedError("HubSpot refresh credential is invalid") from exc
        next_refresh = refreshed.refresh_token or refresh_token
        saved = await self._repository.update_tokens(
            connection.id,
            user_id=connection.user_id,
            encrypted_access_token=self._cipher.encrypt(refreshed.access_token),
            encrypted_refresh_token=self._cipher.encrypt(next_refresh),
            expires_at=now + timedelta(seconds=refreshed.expires_in),
            scopes=refreshed.scopes or connection.scopes,
        )
        return self._cipher.decrypt(saved.encrypted_access_token)


@lru_cache
def get_hubspot_service() -> HubSpotService:
    settings = get_settings()
    redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    client = HubSpotClient(
        client_id=settings.hubspot_client_id,
        client_secret=settings.hubspot_client_secret,
        redirect_uri=settings.hubspot_redirect_uri,
        http_client=httpx.AsyncClient(timeout=20),
    )
    return HubSpotService(
        client=client,
        repository=SqlAlchemyConnectionRepository(),
        state_store=OAuthStateStore(redis_client, settings.hubspot_oauth_state_ttl_seconds),
        cipher=TokenCipher(settings.hubspot_token_encryption_key),
        client_id=settings.hubspot_client_id,
        redirect_uri=settings.hubspot_redirect_uri,
        scopes=settings.hubspot_scope_list,
        refresh_skew_seconds=settings.hubspot_refresh_skew_seconds,
    )


def error_payload(error: HubSpotError) -> dict:
    return {
        "success": False,
        "data": None,
        "error": {"code": error.code, "message": str(error), "retryable": error.retryable},
    }
