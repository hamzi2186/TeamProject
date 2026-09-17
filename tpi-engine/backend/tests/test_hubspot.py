import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from app.main import app
from app.api.hubspot import callback
from app.core.config import validate_hubspot_redirect_uri
from app.providers.hubspot.client import CONTACTS_URL, TOKEN_URL, HubSpotClient
from app.providers.hubspot.crypto import TokenCipher
from app.providers.hubspot.errors import (
    InvalidOAuthStateError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderTemporaryError,
    TokenExchangeError,
)
from app.providers.hubspot.oauth import OAuthStateStore, build_authorization_url
from app.providers.hubspot.schemas import (
    CallbackResponse,
    ConnectionStatusResponse,
    ConnectResponse,
    ContactPage,
    HubSpotTokenSet,
    NormalizedContact,
)
from app.providers.hubspot.service import HubSpotService, get_hubspot_service
from app.providers.hubspot.repository import SqlAlchemyConnectionRepository


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.expired: set[str] = set()

    async def set(self, key: str, value: str, *, ex: int, nx: bool):
        if nx and key in self.values:
            return None
        self.values[key] = value
        return True

    async def getdel(self, key: str):
        if key in self.expired:
            self.values.pop(key, None)
            return None
        return self.values.pop(key, None)


def hubspot_client(handler) -> HubSpotClient:
    return HubSpotClient(
        client_id="client",
        client_secret="secret",
        redirect_uri="http://localhost/callback",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


@pytest.mark.asyncio
async def test_authorization_url_and_state_replay_prevention():
    redis = FakeRedis()
    store = OAuthStateStore(redis, ttl_seconds=600)
    user_id = uuid4()
    state = await store.create(user_id)
    url = build_authorization_url(
        client_id="client-id",
        redirect_uri="http://localhost/callback",
        scopes=["crm.objects.contacts.read"],
        state=state,
    )
    query = parse_qs(urlparse(url).query)
    assert query["client_id"] == ["client-id"]
    assert query["redirect_uri"] == ["http://localhost/callback"]
    assert query["scope"] == ["crm.objects.contacts.read"]
    assert await store.consume(state) == user_id
    with pytest.raises(InvalidOAuthStateError):
        await store.consume(state)


@pytest.mark.asyncio
async def test_state_expiry_is_rejected():
    redis = FakeRedis()
    store = OAuthStateStore(redis, ttl_seconds=1)
    state = await store.create(uuid4())
    redis.expired.add(f"tpi:hubspot:oauth-state:{state}")
    with pytest.raises(InvalidOAuthStateError):
        await store.consume(state)


@pytest.mark.parametrize(
    "redirect_uri",
    [
        "not-a-url",
        "ftp://localhost/callback",
        "http://tpi:8001/callback",
    ],
)
def test_redirect_uri_rejects_invalid_or_docker_only_local_hosts(redirect_uri):
    with pytest.raises(ValueError, match="HUBSPOT_REDIRECT_URI"):
        validate_hubspot_redirect_uri(redirect_uri, app_env="development")


def test_redirect_uri_accepts_browser_reachable_local_and_production_hosts():
    assert validate_hubspot_redirect_uri(
        "http://localhost:8001/api/v1/hubspot/callback", app_env="development"
    ) == "http://localhost:8001/api/v1/hubspot/callback"
    assert validate_hubspot_redirect_uri(
        "https://hubspot.example.test/callback", app_env="production"
    ) == "https://hubspot.example.test/callback"


def test_crypto_round_trip():
    cipher = TokenCipher(Fernet.generate_key().decode())
    encrypted = cipher.encrypt("provider-token")
    assert encrypted != "provider-token"
    assert cipher.decrypt(encrypted) == "provider-token"


@pytest.mark.asyncio
async def test_token_response_parsing():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == TOKEN_URL
        return httpx.Response(
            200,
            json={
                "access_token": "access",
                "refresh_token": "refresh",
                "expires_in": 1800,
                "token_type": "bearer",
            },
        )

    token = await hubspot_client(handler).exchange_code("authorization-code")
    assert token.access_token == "access"
    assert token.refresh_token == "refresh"
    assert token.expires_in == 1800


@pytest.mark.asyncio
async def test_normalized_contacts_and_pagination():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == urlparse(CONTACTS_URL).path
        assert request.url.params["after"] == "cursor-1"
        assert set(request.url.params["properties"].split(",")) == {
            "firstname",
            "lastname",
            "phone",
            "email",
            "website",
        }
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "123",
                        "properties": {
                            "firstname": "Ada",
                            "lastname": "Lovelace",
                            "phone": None,
                            "email": "ada@example.test",
                            "website": "https://example.test",
                            "provider_only": "discarded",
                        },
                    }
                ],
                "paging": {"next": {"after": "cursor-2"}},
            },
        )

    page = await hubspot_client(handler).get_contacts("access", after="cursor-1")
    assert page.next_after == "cursor-2"
    assert page.contacts == [
        NormalizedContact(
            provider_contact_id="123",
            firstname="Ada",
            lastname="Lovelace",
            email="ada@example.test",
            website="https://example.test",
        )
    ]
    assert "provider_only" not in page.contacts[0].model_dump()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "operation", "error_type"),
    [
        (429, "contacts", ProviderRateLimitError),
        (503, "contacts", ProviderTemporaryError),
        (401, "contacts", ProviderAuthError),
        (400, "exchange", TokenExchangeError),
    ],
)
async def test_provider_error_mapping(status: int, operation: str, error_type: type[Exception]):
    client = hubspot_client(lambda _: httpx.Response(status, json={"message": "provider detail"}))
    with pytest.raises(error_type) as captured:
        if operation == "exchange":
            await client.exchange_code("bad-code")
        else:
            await client.get_contacts("bad-access")
    assert "provider detail" not in str(captured.value)
    if operation == "exchange":
        assert "HUBSPOT_REDIRECT_URI" in str(captured.value)
        assert "browser-reachable" in str(captured.value)


class FakeRepository:
    def __init__(self, connection) -> None:
        self.connection = connection
        self.refresh_updates = 0
        self.status_updates: list[str] = []
        self.refresh_update_user_ids = []
        self.status_update_user_ids = []

    async def latest_for_user(self, _user_id):
        return self.connection

    async def update_tokens(self, connection_id, *, user_id, **values):
        self.refresh_updates += 1
        self.refresh_update_user_ids.append(user_id)
        for key, value in values.items():
            setattr(self.connection, key, value)
        return self.connection

    async def set_status(self, _connection_id, *, user_id, status):
        self.status_updates.append(status)
        self.status_update_user_ids.append(user_id)


class RefreshingClient:
    def __init__(self) -> None:
        self.refresh_calls = 0
        self.contacts_access_token = None

    async def refresh(self, refresh_token):
        assert refresh_token == "old-refresh"
        self.refresh_calls += 1
        return HubSpotTokenSet(
            access_token="new-access", refresh_token="new-refresh", expires_in=1800
        )

    async def get_contacts(self, access_token, **_kwargs):
        self.contacts_access_token = access_token
        return ContactPage(contacts=[], next_after=None)


@pytest.mark.asyncio
async def test_expired_access_token_is_refreshed_and_persisted():
    cipher = TokenCipher(Fernet.generate_key().decode())
    connection = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        status="connected",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
        encrypted_access_token=cipher.encrypt("old-access"),
        encrypted_refresh_token=cipher.encrypt("old-refresh"),
        scopes=["crm.objects.contacts.read"],
    )
    repository = FakeRepository(connection)
    provider = RefreshingClient()
    service = HubSpotService(
        client=provider,
        repository=repository,
        state_store=OAuthStateStore(FakeRedis()),
        cipher=cipher,
        client_id="client",
        redirect_uri="http://localhost/callback",
        scopes=["crm.objects.contacts.read"],
    )
    await service.contacts(uuid4())
    assert provider.refresh_calls == 1
    assert repository.refresh_updates == 1
    assert repository.refresh_update_user_ids == [connection.user_id]
    assert provider.contacts_access_token == "new-access"
    assert connection.encrypted_access_token != "new-access"


class OAuthRepository:
    def __init__(self) -> None:
        self.upserts = []
        self.connections = {}

    async def upsert(self, **values):
        self.upserts.append(values)
        record = SimpleNamespace(
            id=uuid4(),
            user_id=values["user_id"],
            hubspot_portal_id=values["portal_id"],
            encrypted_access_token=values["encrypted_access_token"],
            encrypted_refresh_token=values["encrypted_refresh_token"],
            expires_at=values["expires_at"],
            scopes=values["scopes"],
            status="connected",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.connections[record.user_id] = record
        return record

    async def latest_for_user(self, user_id):
        return self.connections.get(user_id)


class CompletingClient:
    async def exchange_code(self, _code):
        return HubSpotTokenSet(
            access_token="test-access", refresh_token="test-refresh", expires_in=1800
        )

    async def get_portal_id(self, _access_token):
        return "portal-123"


def oauth_service(repository, state_store):
    return HubSpotService(
        client=CompletingClient(),
        repository=repository,
        state_store=state_store,
        cipher=TokenCipher(Fernet.generate_key().decode()),
        client_id="client",
        redirect_uri="http://localhost:8001/api/v1/hubspot/callback",
        scopes=["crm.objects.contacts.read"],
    )


@pytest.mark.asyncio
async def test_oauth_callback_persists_the_user_from_one_time_state():
    repository = OAuthRepository()
    state_store = OAuthStateStore(FakeRedis())
    service = oauth_service(repository, state_store)
    user_a = uuid4()
    user_b = uuid4()

    state_a = await state_store.create(user_a)
    await service.complete_oauth(state=state_a, code="test-code", provider_error=None)

    assert repository.upserts[0]["user_id"] == user_a
    assert (await service.connection_status(user_b)).connected is False
    with pytest.raises(InvalidOAuthStateError):
        await service.complete_oauth(state=state_a, code="test-code", provider_error=None)


@pytest.mark.asyncio
async def test_each_user_state_creates_only_that_users_connection_even_for_same_portal():
    repository = OAuthRepository()
    state_store = OAuthStateStore(FakeRedis())
    service = oauth_service(repository, state_store)
    user_a = uuid4()
    user_b = uuid4()

    state_a = await state_store.create(user_a)
    state_b = await state_store.create(user_b)
    await service.complete_oauth(state=state_b, code="test-code", provider_error=None)
    await service.complete_oauth(state=state_a, code="test-code", provider_error=None)

    assert [entry["user_id"] for entry in repository.upserts] == [user_b, user_a]
    assert set(repository.connections) == {user_a, user_b}


class CallbackService:
    def __init__(self, error=None):
        self.error = error

    async def complete_oauth(self, **_kwargs):
        if self.error:
            raise self.error
        return None


@pytest.mark.asyncio
async def test_callback_redirects_with_non_sensitive_success_or_configuration_error(monkeypatch):
    import app.api.hubspot as hubspot_api

    monkeypatch.setattr(
        hubspot_api, "get_settings", lambda: SimpleNamespace(frontend_url="http://localhost:5173")
    )
    success = await callback(state="opaque-state", code="opaque-code", service=CallbackService())
    failure = await callback(
        state="opaque-state",
        code="opaque-code",
        service=CallbackService(TokenExchangeError("sanitized exchange failure")),
    )

    assert success.status_code == 303
    assert success.headers["location"] == "http://localhost:5173/hubspot?hubspot=connected"
    assert failure.status_code == 303
    assert failure.headers["location"] == "http://localhost:5173/hubspot?hubspot=error&reason=configuration"
    assert "opaque" not in failure.headers["location"]


class CapturingSession:
    def __init__(self, connection):
        self.connection = connection
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)

    async def commit(self):
        pass

    async def scalar(self, statement):
        self.statements.append(statement)
        return self.connection


class CapturingFactory:
    def __init__(self, session):
        self.session = session

    @asynccontextmanager
    async def __call__(self):
        yield self.session


@pytest.mark.asyncio
async def test_repository_token_and_status_updates_are_constrained_to_connection_owner():
    user_id = uuid4()
    connection_id = uuid4()
    session = CapturingSession(SimpleNamespace(id=connection_id, user_id=user_id))
    repository = SqlAlchemyConnectionRepository(CapturingFactory(session))

    await repository.update_tokens(
        connection_id,
        user_id=user_id,
        encrypted_access_token="encrypted-access",
        encrypted_refresh_token="encrypted-refresh",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        scopes=["crm.objects.contacts.read"],
    )
    await repository.set_status(connection_id, user_id=user_id, status="disconnected")

    statements = [
        str(statement.compile(dialect=postgresql.dialect())) for statement in session.statements
    ]
    updates = [statement for statement in statements if statement.startswith("UPDATE")]
    assert len(updates) == 2
    assert all("hubspot_connections.user_id" in statement for statement in updates)
    assert all("SET user_id" not in statement for statement in updates)


class FakeApiService:
    async def create_authorization_url(self, _user_id):
        return ConnectResponse(
            authorization_url="https://example.test/oauth?state=safe", expires_in=600
        )

    async def connection_status(self, _user_id):
        return ConnectionStatusResponse(
            status="connected",
            connected=True,
            portal_id="123",
            scopes=["crm.objects.contacts.read"],
        )

    async def complete_oauth(self, **_kwargs):
        return CallbackResponse(connected=True, status="connected", portal_id="123")


def test_internal_authentication_and_api_responses_exclude_tokens(monkeypatch):
    import app.api.dependencies as dependencies

    monkeypatch.setattr(
        dependencies,
        "get_settings",
        lambda: SimpleNamespace(tpi_internal_service_token="internal-test-token"),
    )
    app.dependency_overrides[get_hubspot_service] = lambda: FakeApiService()
    client = TestClient(app)
    user_id = str(uuid4())
    missing_auth = client.post(
        "/api/v1/internal/hubspot/connect", json={"user_id": user_id}
    )
    assert missing_auth.status_code == 422
    assert (
        client.post(
            "/api/v1/internal/hubspot/connect",
            json={"user_id": user_id},
            headers={"X-TPI-Service-Token": "wrong"},
        ).status_code
        == 401
    )
    response = client.get(
        "/api/v1/internal/hubspot/status",
        params={"user_id": user_id},
        headers={"X-TPI-Service-Token": "internal-test-token"},
    )
    assert response.status_code == 200
    serialized = json.dumps(response.json()).lower()
    assert "access_token" not in serialized
    assert "refresh_token" not in serialized
    assert "client_secret" not in serialized
    app.dependency_overrides.clear()
