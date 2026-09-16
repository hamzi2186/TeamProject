from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import get_repository, get_task_dispatcher
from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.main import app


class FakeDispatcher:
    def __init__(self):
        self.job_ids = []

    def dispatch(self, job_id):
        self.job_ids.append(job_id)
        return "task-1"


class FakeRepository:
    def __init__(self, owner_id):
        self.owner_id = owner_id
        self.website = SimpleNamespace(
            id=uuid4(),
            user_id=owner_id,
            original_url="https://example.com",
            normalized_url="https://example.com/",
            normalized_key="example.com",
            crawl_status="PENDING",
            last_crawled_at=None,
            content_fingerprint=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self.kb = SimpleNamespace(id=uuid4(), status="PENDING")
        self.job = SimpleNamespace(id=uuid4())
        self.user_ids = []
        self.task_ids = []

    async def create_site_kb_job(self, *, user_id, **_kwargs):
        self.user_ids.append(user_id)
        return self.website, self.kb, self.job, False

    async def set_task_id(self, job_id, task_id):
        self.task_ids.append((job_id, task_id))

    async def website_summary(self, user_id, _website_id):
        assert user_id == self.owner_id
        return SimpleNamespace(
            website=self.website,
            knowledge_base_id=self.kb.id,
            kb_status=self.kb.status,
            page_count=0,
            chunk_count=0,
            leads_using_kb=0,
        )


def test_customer_api_requires_authentication():
    response = TestClient(app).get("/api/v1/websites")
    assert response.status_code == 401


def test_internal_api_requires_service_authentication():
    response = TestClient(app).post(
        "/api/v1/internal/client-kb/search",
        json={
            "user_id": str(uuid4()),
            "knowledge_base_id": str(uuid4()),
            "query": "services",
        },
        headers={"X-Scraper-Service-Token": "wrong"},
    )
    assert response.status_code == 401


def test_ingest_uses_authenticated_tenant_and_dispatches_job(monkeypatch):
    import app.api.websites as websites_api

    async def allow(_url):
        return ["93.184.216.34"]

    monkeypatch.setattr(websites_api, "validate_public_url", allow)
    user = AuthenticatedUser(user_id=uuid4(), role="customer")
    repository = FakeRepository(user.user_id)
    dispatcher = FakeDispatcher()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_task_dispatcher] = lambda: dispatcher
    response = TestClient(app).post(
        "/api/v1/websites/ingest",
        json={"url": "HTTP://WWW.Example.COM:80/", "lead_ids": []},
    )
    assert response.status_code == 202
    assert repository.user_ids == [user.user_id]
    assert dispatcher.job_ids == [repository.job.id]
    assert response.json()["website"]["normalized_key"] == "example.com"
    app.dependency_overrides.clear()
