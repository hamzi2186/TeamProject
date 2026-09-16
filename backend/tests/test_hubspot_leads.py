import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_hubspot_import_service, get_lead_repository
from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.main import app
from app.schemas.hubspot import (
    HubSpotConnectionStatus,
    HubSpotConnectResponse,
    HubSpotContactPage,
    HubSpotImportRequest,
    NormalizedHubSpotContact,
)
from app.services.hubspot_import import HubSpotImportService
from app.services.leads import ImportCounts, contact_to_lead_values
from app.services.tpi_hubspot import (
    TPIHubSpotClient,
    TPIHubSpotError,
    get_tpi_hubspot_client,
)


class FakeTPI:
    def __init__(self) -> None:
        self.user_ids = []

    async def connect(self, user_id):
        self.user_ids.append(user_id)
        return HubSpotConnectResponse(
            authorization_url="https://example.test/oauth?state=opaque", expires_in=600
        )

    async def status(self, user_id):
        self.user_ids.append(user_id)
        return HubSpotConnectionStatus(
            status="connected",
            connected=True,
            portal_id="portal",
            scopes=["crm.objects.contacts.read"],
        )

    async def contacts(self, user_id, **_kwargs):
        self.user_ids.append(user_id)
        return HubSpotContactPage(
            contacts=[NormalizedHubSpotContact(provider_contact_id="contact-1")]
        )


@pytest.fixture
def authenticated_client():
    user = AuthenticatedUser(user_id=uuid4(), role="customer", email="user@example.test")
    tpi = FakeTPI()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_tpi_hubspot_client] = lambda: tpi
    with TestClient(app) as client:
        yield client, user, tpi
    app.dependency_overrides.clear()


def test_connect_and_status_use_authenticated_identity_and_exclude_tokens(authenticated_client):
    client, user, tpi = authenticated_client
    connect = client.get("/api/v1/hubspot/connect")
    status = client.get("/api/v1/hubspot/status")
    assert connect.status_code == 200
    assert status.status_code == 200
    assert tpi.user_ids == [user.user_id, user.user_id]
    serialized = json.dumps({"connect": connect.json(), "status": status.json()}).lower()
    assert "access_token" not in serialized
    assert "refresh_token" not in serialized
    assert "client_secret" not in serialized


def test_import_requires_authentication():
    with TestClient(app) as client:
        response = client.post("/api/v1/hubspot/import", json={"select_all": True})
    assert response.status_code == 401


def test_normalized_contact_maps_to_canonical_lead():
    user_id = uuid4()
    connection_id = uuid4()
    values = contact_to_lead_values(
        NormalizedHubSpotContact(
            provider_contact_id="123",
            firstname=" Ada ",
            lastname=" Lovelace ",
            phone="+10000000000",
            email="ada@example.test",
            website="https://example.test",
        ),
        user_id=user_id,
        connection_id=connection_id,
    )
    assert values["user_id"] == user_id
    assert values["hubspot_connection_id"] == connection_id
    assert values["hubspot_contact_id"] == "123"
    assert values["display_name"] == "Ada Lovelace"
    assert values["current_status"] == "new"
    assert set(values["source_payload"]["contact"]) == {
        "provider_contact_id",
        "firstname",
        "lastname",
        "phone",
        "email",
        "website",
    }


class FakeLeadRepository:
    def __init__(self) -> None:
        self.connection = uuid4()
        self.keys: set[tuple] = set()

    async def connection_id(self, _user_id, _portal_id):
        return self.connection

    async def upsert_contacts(self, *, user_id, connection_id, contacts):
        created = 0
        for contact in contacts:
            key = (user_id, contact.provider_contact_id)
            if key not in self.keys:
                created += 1
            self.keys.add(key)
        return ImportCounts(len(contacts), created, len(contacts) - created)


@pytest.mark.asyncio
async def test_repeated_import_upserts_without_duplicate():
    user_id = uuid4()
    repository = FakeLeadRepository()
    service = HubSpotImportService(FakeTPI(), repository)
    selection = HubSpotImportRequest(hubspot_contact_ids=["contact-1"])
    first = await service.run(user_id, selection)
    second = await service.run(user_id, selection)
    assert first == ImportCounts(imported=1, created=1, updated=0)
    assert second == ImportCounts(imported=1, created=0, updated=1)
    assert len(repository.keys) == 1


class FakeImportService:
    def __init__(self) -> None:
        self.user_id = None

    async def run(self, user_id, _payload):
        self.user_id = user_id
        return ImportCounts(imported=2, created=1, updated=1)


def test_import_uses_authenticated_tenant(authenticated_client):
    client, user, _tpi = authenticated_client
    service = FakeImportService()
    app.dependency_overrides[get_hubspot_import_service] = lambda: service
    response = client.post("/api/v1/hubspot/import", json={"select_all": True})
    assert response.status_code == 200
    assert response.json() == {"imported": 2, "created": 1, "updated": 1}
    assert service.user_id == user.user_id


class FakeLeadListRepository:
    def __init__(self, owner_id) -> None:
        self.owner_id = owner_id
        now = datetime.now(UTC)
        self.lead = SimpleNamespace(
            id=uuid4(),
            hubspot_contact_id="contact-1",
            first_name="Ada",
            last_name="Lovelace",
            display_name="Ada Lovelace",
            phone=None,
            email="ada@example.test",
            website_url=None,
            website_id=None,
            current_status="new",
            created_at=now,
            updated_at=now,
        )

    async def list_for_user(self, user_id):
        return [self.lead] if user_id == self.owner_id else []


def test_leads_list_is_tenant_scoped(authenticated_client):
    client, user, _tpi = authenticated_client
    repository = FakeLeadListRepository(user.user_id)
    app.dependency_overrides[get_lead_repository] = lambda: repository
    response = client.get("/api/v1/leads")
    assert response.status_code == 200
    assert [lead["hubspot_contact_id"] for lead in response.json()] == ["contact-1"]


@pytest.mark.asyncio
async def test_tpi_failure_is_normalized_and_provider_body_is_hidden():
    async def handler(_request):
        return httpx.Response(
            500,
            json={"message": "raw provider failure", "access_token": "must-not-escape"},
        )

    client = TPIHubSpotClient(
        base_url="http://tpi.test",
        service_token="internal-token",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(TPIHubSpotError) as captured:
        await client.status(uuid4())
    assert captured.value.status_code == 503
    assert "raw provider failure" not in str(captured.value)
    assert "must-not-escape" not in str(captured.value)
