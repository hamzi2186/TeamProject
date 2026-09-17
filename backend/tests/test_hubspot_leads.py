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
from app.services.scraper_client import ScraperClientError
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
        self.lead_ids: dict[tuple, object] = {}
        self.leads = {}

    async def connection_id(self, _user_id, _portal_id):
        return self.connection

    async def upsert_contacts(self, *, user_id, connection_id, contacts):
        created = 0
        for contact in contacts:
            key = (user_id, contact.provider_contact_id)
            if key not in self.keys:
                created += 1
                lead_id = uuid4()
                self.lead_ids[key] = lead_id
                self.leads[lead_id] = SimpleNamespace(
                    id=lead_id,
                    user_id=user_id,
                    hubspot_contact_id=contact.provider_contact_id,
                    website_url=contact.website,
                    website_id=None,
                )
            else:
                self.leads[self.lead_ids[key]].website_url = contact.website
            self.keys.add(key)
        return ImportCounts(len(contacts), created, len(contacts) - created)

    async def lead_ids_by_hubspot_contact(self, user_id, contact_ids):
        return {
            contact_id: self.lead_ids[(user_id, contact_id)]
            for contact_id in contact_ids
            if (user_id, contact_id) in self.lead_ids
        }


class FakeScraper:
    NORMALIZED_KEYS = {
        "http://example.com": "example.com",
        "https://www.example.com/": "example.com",
        "https://example.com/": "example.com",
        "https://failed.example/": "failed.example",
    }

    def __init__(self, leads: FakeLeadRepository, fail_urls=None) -> None:
        self.leads = leads
        self.fail_urls = set(fail_urls or [])
        self.calls = []
        self.normalization_calls = []
        self.websites = {}
        self.dispatched = []

    async def normalize_website(self, user_id, role, url):
        self.normalization_calls.append((user_id, role, url))
        normalized_key = self.NORMALIZED_KEYS.get(url, url.strip().casefold())
        return {
            "normalized_key": normalized_key,
            "normalized_url": f"https://{normalized_key}/",
        }

    async def ingest_website(self, user_id, role, url, lead_ids):
        self.calls.append((user_id, role, url, list(lead_ids)))
        if url in self.fail_urls:
            raise ScraperClientError("Website ingestion could not be started", 503)
        normalized_key = url.removeprefix("https://").rstrip("/")
        site_key = (user_id, normalized_key)
        created = site_key not in self.websites
        if created:
            self.websites[site_key] = uuid4()
            self.dispatched.append(site_key)
        website_id = self.websites[site_key]
        for lead_id in lead_ids:
            lead = self.leads.leads[lead_id]
            assert lead.user_id == user_id
            lead.website_id = website_id
        return {"website": {"id": website_id}, "reused": not created}


@pytest.mark.asyncio
async def test_repeated_import_upserts_without_duplicate():
    user_a = uuid4()
    user_b = uuid4()
    repository = FakeLeadRepository()
    service = HubSpotImportService(FakeTPI(), repository, FakeScraper(repository))
    selection = HubSpotImportRequest(hubspot_contact_ids=["contact-1"])
    first_a = await service.run(user_a, "customer", selection)
    first_b = await service.run(user_b, "customer", selection)
    second_a = await service.run(user_a, "customer", selection)
    assert (first_a.imported, first_a.created, first_a.updated) == (1, 1, 0)
    assert (first_b.imported, first_b.created, first_b.updated) == (1, 1, 0)
    assert (second_a.imported, second_a.created, second_a.updated) == (1, 0, 1)
    assert repository.keys == {(user_a, "contact-1"), (user_b, "contact-1")}


class ContactTPI(FakeTPI):
    def __init__(self, contacts):
        super().__init__()
        self._contacts = contacts

    async def contacts(self, user_id, **_kwargs):
        self.user_ids.append(user_id)
        return HubSpotContactPage(contacts=self._contacts)


@pytest.mark.asyncio
async def test_import_with_website_links_lead_and_starts_scraper_ingest():
    user_id = uuid4()
    repository = FakeLeadRepository()
    scraper = FakeScraper(repository)
    contact = NormalizedHubSpotContact(
        provider_contact_id="contact-web", website="http://example.com"
    )
    service = HubSpotImportService(ContactTPI([contact]), repository, scraper)

    result = await service.run(
        user_id,
        "customer",
        HubSpotImportRequest(hubspot_contact_ids=["contact-web"]),
    )

    lead = repository.leads[repository.lead_ids[(user_id, "contact-web")]]
    assert (result.imported, result.created, result.updated) == (1, 1, 0)
    assert result.website_ingestion_failures == []
    assert lead.website_id == scraper.websites[(user_id, "example.com")]
    assert scraper.normalization_calls == [(user_id, "customer", "http://example.com")]
    assert scraper.calls[0][:3] == (user_id, "customer", "https://example.com/")


@pytest.mark.asyncio
async def test_website_variants_reuse_one_site_and_one_active_ingest_for_same_user():
    user_id = uuid4()
    repository = FakeLeadRepository()
    scraper = FakeScraper(repository)
    contacts = [
        NormalizedHubSpotContact(provider_contact_id="one", website="http://example.com"),
        NormalizedHubSpotContact(provider_contact_id="two", website="https://www.example.com/"),
        NormalizedHubSpotContact(provider_contact_id="three", website="https://example.com/"),
    ]
    service = HubSpotImportService(ContactTPI(contacts), repository, scraper)

    await service.run(user_id, "customer", HubSpotImportRequest(select_all=True))
    await service.run(user_id, "customer", HubSpotImportRequest(select_all=True))

    website_ids = {
        repository.leads[repository.lead_ids[(user_id, contact.provider_contact_id)]].website_id
        for contact in contacts
    }
    assert len(website_ids) == 1
    assert len(scraper.websites) == 1
    assert scraper.dispatched == [(user_id, "example.com")]
    assert len(scraper.calls) == 2
    assert len(repository.keys) == 3


@pytest.mark.asyncio
async def test_same_website_isolated_between_users():
    user_a = uuid4()
    user_b = uuid4()
    repository = FakeLeadRepository()
    scraper = FakeScraper(repository)
    contact = NormalizedHubSpotContact(
        provider_contact_id="shared-contact", website="https://example.com/"
    )
    service = HubSpotImportService(ContactTPI([contact]), repository, scraper)
    selection = HubSpotImportRequest(hubspot_contact_ids=["shared-contact"])

    await service.run(user_a, "customer", selection)
    await service.run(user_b, "customer", selection)

    website_a = repository.leads[repository.lead_ids[(user_a, "shared-contact")]].website_id
    website_b = repository.leads[repository.lead_ids[(user_b, "shared-contact")]].website_id
    assert website_a != website_b
    assert set(scraper.websites) == {(user_a, "example.com"), (user_b, "example.com")}


@pytest.mark.asyncio
async def test_contact_without_website_imports_without_scraper_call():
    user_id = uuid4()
    repository = FakeLeadRepository()
    scraper = FakeScraper(repository)
    contact = NormalizedHubSpotContact(provider_contact_id="no-site")
    service = HubSpotImportService(ContactTPI([contact]), repository, scraper)

    result = await service.run(
        user_id, "customer", HubSpotImportRequest(hubspot_contact_ids=["no-site"])
    )

    lead = repository.leads[repository.lead_ids[(user_id, "no-site")]]
    assert result.created == 1
    assert lead.website_id is None
    assert scraper.calls == []
    assert scraper.normalization_calls == []


@pytest.mark.asyncio
async def test_scraper_failure_preserves_lead_and_is_reported():
    user_id = uuid4()
    repository = FakeLeadRepository()
    scraper = FakeScraper(repository, fail_urls={"https://failed.example/"})
    contact = NormalizedHubSpotContact(
        provider_contact_id="failed-site", website="https://failed.example/"
    )
    service = HubSpotImportService(ContactTPI([contact]), repository, scraper)

    result = await service.run(
        user_id, "customer", HubSpotImportRequest(hubspot_contact_ids=["failed-site"])
    )

    lead = repository.leads[repository.lead_ids[(user_id, "failed-site")]]
    assert result.created == 1
    assert lead.website_url == "https://failed.example/"
    assert lead.website_id is None
    assert len(result.website_ingestion_failures) == 1
    assert result.website_ingestion_failures[0].hubspot_contact_ids == ["failed-site"]
    assert result.website_ingestion_failures[0].message == "Website ingestion could not be started"


class FakeImportService:
    def __init__(self) -> None:
        self.user_id = None

    async def run(self, user_id, _role, _payload):
        self.user_id = user_id
        return ImportCounts(imported=2, created=1, updated=1)


def test_import_uses_authenticated_tenant(authenticated_client):
    client, user, _tpi = authenticated_client
    service = FakeImportService()
    app.dependency_overrides[get_hubspot_import_service] = lambda: service
    response = client.post("/api/v1/hubspot/import", json={"select_all": True})
    assert response.status_code == 200
    assert response.json() == {
        "imported": 2,
        "created": 1,
        "updated": 1,
        "website_ingestion_failures": [],
    }
    assert service.user_id == user.user_id


def test_user_b_cannot_retrieve_user_as_hubspot_connection():
    user_a = AuthenticatedUser(user_id=uuid4(), role="customer", email="a@example.test")
    user_b = AuthenticatedUser(user_id=uuid4(), role="customer", email="b@example.test")

    class UserScopedTPI:
        def __init__(self):
            self.user_ids = []

        async def status(self, user_id):
            self.user_ids.append(user_id)
            if user_id == user_a.user_id:
                return HubSpotConnectionStatus(
                    status="connected", connected=True, portal_id="portal-a"
                )
            return HubSpotConnectionStatus(status="disconnected", connected=False)

        async def contacts(self, user_id, **_kwargs):
            self.user_ids.append(user_id)
            if user_id != user_a.user_id:
                raise TPIHubSpotError("HubSpot is not connected", 404)
            return HubSpotContactPage(contacts=[])

    tpi = UserScopedTPI()
    app.dependency_overrides[get_current_user] = lambda: user_b
    app.dependency_overrides[get_tpi_hubspot_client] = lambda: tpi
    try:
        with TestClient(app) as client:
            assert client.get("/api/v1/hubspot/status").json()["connected"] is False
            assert client.get("/api/v1/hubspot/contacts").status_code == 404
        assert tpi.user_ids == [user_b.user_id, user_b.user_id]
    finally:
        app.dependency_overrides.clear()


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
