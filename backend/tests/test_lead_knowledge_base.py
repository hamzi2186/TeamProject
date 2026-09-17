from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.leads import map_knowledge_base_status
from app.api.dependencies import get_lead_repository, get_scraper_client
from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.main import app
from app.schemas.leads import LeadUpdate


class FakeLeadRepository:
    def __init__(self, leads: list[SimpleNamespace] | None = None) -> None:
        self.leads: dict[tuple[str, str], SimpleNamespace] = {}
        for lead in leads or []:
            self.leads[(str(lead.user_id), str(lead.id))] = lead

    async def get_for_user(self, user_id, lead_id):
        return self.leads.get((str(user_id), str(lead_id)))

    async def list_for_user(self, user_id):
        return [lead for (uid, _), lead in self.leads.items() if uid == str(user_id)]

    async def update_for_user(self, user_id, lead_id, payload: LeadUpdate):
        lead = await self.get_for_user(user_id, lead_id)
        if not lead:
            return None
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(lead, key, value)
        return lead

    async def set_lead_website(self, user_id, lead_id, website_id, website_url=None):
        lead = await self.get_for_user(user_id, lead_id)
        if not lead:
            return None
        lead.website_id = website_id
        if website_url:
            lead.website_url = website_url
        return lead


class FakeScraperClient:
    def __init__(self) -> None:
        self.websites = {}
        self.jobs = {}
        self.searches = []

    async def get_website_status(self, user_id, role, website_id):
        return self.websites.get(str(website_id))

    async def lookup_website_by_url(self, user_id, role, url):
        for data in self.websites.values():
            if data["website"]["original_url"] == url or data["website"]["normalized_url"] == url:
                return data["website"]
        return None

    async def ingest_website(self, user_id, role, url, lead_ids):
        site_id = uuid4()
        kb_id = uuid4()
        job_id = uuid4()
        website_payload = {
            "id": site_id,
            "original_url": url,
            "normalized_url": url,
            "normalized_key": f"{user_id}:{url}",
            "crawl_status": "CRAWLING",
            "last_crawled_at": None,
            "content_fingerprint": None,
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
            "knowledge_base_id": kb_id,
            "kb_status": "CRAWLING",
            "page_count": 0,
            "chunk_count": 0,
            "leads_using_kb": len(lead_ids),
        }
        job_payload = {
            "id": job_id,
            "status": "QUEUED",
            "pages_discovered": 0,
            "pages_crawled": 0,
            "pages_indexed": 0,
            "chunks_generated": 0,
            "error_message": None,
        }
        self.websites[str(site_id)] = {
            "website": website_payload,
            "job": job_payload,
        }
        return {
            "website": website_payload,
            "knowledge_base_id": kb_id,
            "job_id": job_id,
            "reused": False,
        }

    async def refresh_website(self, user_id, role, website_id):
        entry = self.websites.get(str(website_id))
        if entry:
            entry["website"]["kb_status"] = "CRAWLING"
            entry["job"] = {
                "id": uuid4(),
                "status": "QUEUED",
                "pages_discovered": 0,
                "pages_crawled": 0,
                "pages_indexed": 0,
                "chunks_generated": 0,
                "error_message": None,
            }
            return {
                "website": entry["website"],
                "knowledge_base_id": entry["website"]["knowledge_base_id"],
                "job_id": entry["job"]["id"],
                "reused": False,
            }
        raise LookupError("Website not found")

    async def search_knowledge_base(self, user_id, role, kb_id, query, top_k=6):
        self.searches.append({"kb_id": kb_id, "query": query, "top_k": top_k})
        return {
            "knowledge_base_id": kb_id,
            "query": query,
            "results": [
                {
                    "chunk_id": uuid4(),
                    "knowledge_base_id": kb_id,
                    "content": "Acme Corp provides automated CRM intelligence and sales automation.",
                    "source_url": "https://example.com/services",
                    "page_title": "Our Services | Acme Corp",
                    "chunk_index": 0,
                    "similarity": 0.88,
                    "metadata": {},
                }
            ],
            "embedding_provider": "jina",
            "embedding_model": "jina-embeddings-v3",
            "embedding_dimension": 1024,
        }


@pytest.fixture
def test_setup():
    user = AuthenticatedUser(user_id=uuid4(), role="customer", email="test@example.com")
    lead_id = uuid4()
    lead = SimpleNamespace(
        id=lead_id,
        user_id=user.user_id,
        hubspot_contact_id="hs-123",
        first_name="Jane",
        last_name="Doe",
        display_name="Jane Doe",
        phone="+1234567890",
        email="jane@example.com",
        website_url="https://example.com",
        website_id=None,
        current_status="new",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    repo = FakeLeadRepository([lead])
    scraper = FakeScraperClient()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_lead_repository] = lambda: repo
    app.dependency_overrides[get_scraper_client] = lambda: scraper

    with TestClient(app) as client:
        yield client, user, lead, repo, scraper

    app.dependency_overrides.clear()


def test_get_kb_status_not_created_when_no_website_id(test_setup):
    client, user, lead, repo, scraper = test_setup
    res = client.get(f"/api/v1/leads/{lead.id}/knowledge-base")
    assert res.status_code == 200
    data = res.json()
    assert data["has_website"] is True
    assert data["website_url"] == "https://example.com"
    assert data["status"] == "NOT_CREATED"
    assert data["page_count"] == 0
    assert data["chunk_count"] == 0


def test_build_knowledge_base_triggers_ingest_and_updates_lead(test_setup):
    client, user, lead, repo, scraper = test_setup
    res = client.post(
        f"/api/v1/leads/{lead.id}/knowledge-base/build",
        json={"website_url": "https://example.com"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["has_website"] is True
    assert data["status"] == "QUEUED"
    assert lead.website_id is not None
    assert str(lead.website_id) == str(data["website_id"])


def test_get_kb_status_when_ready(test_setup):
    client, user, lead, repo, scraper = test_setup
    site_id = uuid4()
    kb_id = uuid4()
    lead.website_id = site_id

    scraper.websites[str(site_id)] = {
        "website": {
            "id": site_id,
            "original_url": "https://example.com",
            "normalized_url": "https://example.com",
            "normalized_key": f"{user.user_id}:https://example.com",
            "crawl_status": "COMPLETED",
            "last_crawled_at": datetime.now(UTC).isoformat(),
            "content_fingerprint": "hash123",
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "knowledge_base_id": kb_id,
            "kb_status": "READY",
            "page_count": 12,
            "chunk_count": 48,
            "leads_using_kb": 1,
        },
        "job": None,
    }

    res = client.get(f"/api/v1/leads/{lead.id}/knowledge-base")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "READY"
    assert data["page_count"] == 12
    assert data["chunk_count"] == 48
    assert data["last_indexed_at"] is not None


def test_get_kb_status_when_partial(test_setup):
    client, user, lead, repo, scraper = test_setup
    site_id = uuid4()
    kb_id = uuid4()
    lead.website_id = site_id

    scraper.websites[str(site_id)] = {
        "website": {
            "id": site_id,
            "original_url": "https://example.com",
            "normalized_url": "https://example.com",
            "normalized_key": f"{user.user_id}:https://example.com",
            "crawl_status": "PARTIAL",
            "last_crawled_at": datetime.now(UTC).isoformat(),
            "content_fingerprint": "hash123",
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "knowledge_base_id": kb_id,
            "kb_status": "PARTIAL",
            "page_count": 5,
            "chunk_count": 20,
            "leads_using_kb": 1,
        },
        "job": {"status": "PARTIAL", "error_message": None},
    }

    res = client.get(f"/api/v1/leads/{lead.id}/knowledge-base")

    assert res.status_code == 200
    assert res.json()["status"] == "PARTIAL"


@pytest.mark.parametrize(
    "stage",
    ["QUEUED", "CRAWLING", "EXTRACTING", "EMBEDDING", "READY", "PARTIAL", "FAILED"],
)
def test_root_preserves_scraper_processing_contract(stage):
    processing = {
        "knowledge_base_status": "PARTIAL" if stage == "PARTIAL" else stage,
        "processing_stage": stage,
        "pages_discovered": 10,
        "pages_processed": 8,
        "pages_succeeded": 7,
        "pages_failed": None,
        "chunks_created": 20,
        "embeddings_created": 20 if stage in {"READY", "PARTIAL"} else None,
        "started_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
        "completed_at": datetime.now(UTC) if stage in {"READY", "PARTIAL", "FAILED"} else None,
        "error": "Website knowledge processing failed. Please try again."
        if stage == "FAILED"
        else None,
    }

    result = map_knowledge_base_status(
        {
            "id": uuid4(),
            "original_url": "https://example.com",
            "knowledge_base_id": uuid4(),
            "kb_status": processing["knowledge_base_status"],
            "page_count": 7,
            "chunk_count": 20,
        },
        None,
        "https://example.com",
        processing,
    )

    assert result.status == stage
    assert result.processing_stage == stage
    assert result.pages_discovered == 10
    assert result.pages_processed == 8
    assert result.pages_succeeded == 7
    assert result.chunks_created == 20
    if stage == "FAILED":
        assert result.error_message == "Website knowledge processing failed. Please try again."


def test_refresh_knowledge_base(test_setup):
    client, user, lead, repo, scraper = test_setup
    site_id = uuid4()
    kb_id = uuid4()
    lead.website_id = site_id

    scraper.websites[str(site_id)] = {
        "website": {
            "id": site_id,
            "original_url": "https://example.com",
            "normalized_url": "https://example.com",
            "normalized_key": f"{user.user_id}:https://example.com",
            "crawl_status": "COMPLETED",
            "last_crawled_at": datetime.now(UTC).isoformat(),
            "knowledge_base_id": kb_id,
            "kb_status": "READY",
            "page_count": 5,
            "chunk_count": 20,
            "leads_using_kb": 1,
        },
        "job": None,
    }

    res = client.post(f"/api/v1/leads/{lead.id}/knowledge-base/refresh")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "QUEUED"


def test_search_knowledge_base(test_setup):
    client, user, lead, repo, scraper = test_setup
    site_id = uuid4()
    kb_id = uuid4()
    lead.website_id = site_id

    scraper.websites[str(site_id)] = {
        "website": {
            "id": site_id,
            "original_url": "https://example.com",
            "normalized_url": "https://example.com",
            "normalized_key": f"{user.user_id}:https://example.com",
            "crawl_status": "COMPLETED",
            "last_crawled_at": datetime.now(UTC).isoformat(),
            "knowledge_base_id": kb_id,
            "kb_status": "READY",
            "page_count": 5,
            "chunk_count": 20,
            "leads_using_kb": 1,
        },
        "job": None,
    }

    res = client.post(
        f"/api/v1/leads/{lead.id}/knowledge-base/search",
        json={"query": "What services do they offer?", "top_k": 3},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["knowledge_base_id"] == str(kb_id)
    assert data["query"] == "What services do they offer?"
    assert len(data["results"]) == 1
    assert data["results"][0]["page_title"] == "Our Services | Acme Corp"
    assert "CRM intelligence" in data["results"][0]["content"]
    assert data["results"][0]["similarity"] == 0.88


def test_cannot_access_other_users_lead(test_setup):
    client, user, lead, repo, scraper = test_setup
    other_lead_id = uuid4()
    res = client.get(f"/api/v1/leads/{other_lead_id}/knowledge-base")
    assert res.status_code == 404
