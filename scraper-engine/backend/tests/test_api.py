from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_repository, get_task_dispatcher
from app.api.websites import processing_status
from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.main import app


def make_job(status="QUEUED", **overrides):
    values = {
        "id": uuid4(),
        "website_id": uuid4(),
        "knowledge_base_id": uuid4(),
        "status": status,
        "is_refresh": False,
        "celery_task_id": None,
        "attempt_count": 0,
        "pages_discovered": 0,
        "pages_crawled": 0,
        "pages_indexed": 0,
        "chunks_generated": 0,
        "error_code": None,
        "error_message": None,
        "partial_reason": None,
        "started_at": None,
        "completed_at": None,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


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
        self.job = make_job(
            website_id=self.website.id,
            knowledge_base_id=self.kb.id,
        )
        self.user_ids = []
        self.task_ids = []
        self.dispatch_failures = []

    async def create_site_kb_job(self, *, user_id, **_kwargs):
        self.user_ids.append(user_id)
        return self.website, self.kb, self.job, False

    async def set_task_id(self, job_id, task_id):
        self.task_ids.append((job_id, task_id))
        self.job.celery_task_id = task_id

    async def mark_dispatch_failed(self, user_id, job_id):
        assert user_id == self.owner_id
        assert job_id == self.job.id
        self.job.status = "FAILED"
        self.job.error_message = "Website ingestion could not be queued"
        self.dispatch_failures.append(job_id)

    async def website_summary(self, user_id, _website_id):
        if user_id != self.owner_id:
            return None
        return SimpleNamespace(
            website=self.website,
            knowledge_base_id=self.kb.id,
            kb_status=self.kb.status,
            page_count=0,
            chunk_count=0,
            leads_using_kb=0,
        )

    async def latest_job(self, user_id, _website_id):
        return self.job if user_id == self.owner_id else None


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


def test_active_job_is_reused_without_another_dispatch(monkeypatch):
    import app.api.websites as websites_api

    async def allow(_url):
        return ["93.184.216.34"]

    monkeypatch.setattr(websites_api, "validate_public_url", allow)
    user = AuthenticatedUser(user_id=uuid4(), role="customer")
    repository = FakeRepository(user.user_id)

    async def reused_job(*, user_id, **_kwargs):
        repository.user_ids.append(user_id)
        return repository.website, repository.kb, repository.job, True

    repository.create_site_kb_job = reused_job
    dispatcher = FakeDispatcher()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_task_dispatcher] = lambda: dispatcher
    try:
        response = TestClient(app).post(
            "/api/v1/websites/ingest",
            json={"url": "https://example.com", "lead_ids": []},
        )
        assert response.status_code == 202
        assert response.json()["reused"] is True
        assert dispatcher.job_ids == []
        assert repository.task_ids == []
    finally:
        app.dependency_overrides.clear()


def test_dispatch_failure_closes_job_and_later_ingest_dispatches_fresh_job(monkeypatch):
    import app.api.websites as websites_api

    async def allow(_url):
        return ["93.184.216.34"]

    class FailOnceDispatcher(FakeDispatcher):
        def __init__(self):
            super().__init__()
            self.attempts = 0

        def dispatch(self, job_id):
            self.attempts += 1
            self.job_ids.append(job_id)
            if self.attempts == 1:
                raise RuntimeError("broker credentials and address must stay private")
            return "task-retry"

    class RetryRepository(FakeRepository):
        def __init__(self, owner_id):
            super().__init__(owner_id)
            self.jobs = []

        async def create_site_kb_job(self, *, user_id, **_kwargs):
            self.user_ids.append(user_id)
            self.job = make_job(
                website_id=self.website.id,
                knowledge_base_id=self.kb.id,
            )
            self.jobs.append(self.job)
            return self.website, self.kb, self.job, False

    monkeypatch.setattr(websites_api, "validate_public_url", allow)
    user = AuthenticatedUser(user_id=uuid4(), role="customer")
    repository = RetryRepository(user.user_id)
    dispatcher = FailOnceDispatcher()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_repository] = lambda: repository
    app.dependency_overrides[get_task_dispatcher] = lambda: dispatcher
    client = TestClient(app)
    try:
        first = client.post(
            "/api/v1/websites/ingest",
            json={"url": "https://example.com", "lead_ids": []},
        )
        assert first.status_code == 503
        assert first.json() == {"detail": "Website ingestion could not be queued"}
        failed_job = repository.jobs[0]
        assert failed_job.status == "FAILED"
        assert failed_job.celery_task_id is None
        assert "credentials" not in first.text
        assert "address" not in first.text

        second = client.post(
            "/api/v1/websites/ingest",
            json={"url": "https://example.com", "lead_ids": []},
        )
        assert second.status_code == 202
        fresh_job = repository.jobs[1]
        assert fresh_job.id != failed_job.id
        assert fresh_job.celery_task_id == "task-retry"
        assert dispatcher.job_ids == [failed_job.id, fresh_job.id]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("job_status", "kb_status", "expected_stage"),
    [
        ("QUEUED", "PENDING", "QUEUED"),
        ("RUNNING", "CRAWLING", "CRAWLING"),
        ("RUNNING", "PROCESSING", "EXTRACTING"),
        ("RUNNING", "EMBEDDING", "EMBEDDING"),
        ("COMPLETED", "READY", "READY"),
        ("PARTIAL", "PARTIAL", "PARTIAL"),
        ("FAILED", "FAILED", "FAILED"),
    ],
)
def test_processing_status_maps_job_and_kb_lifecycle(job_status, kb_status, expected_stage):
    repository = FakeRepository(uuid4())
    repository.kb.status = kb_status
    repository.job = make_job(
        status=job_status,
        website_id=repository.website.id,
        knowledge_base_id=repository.kb.id,
        pages_discovered=12,
        pages_crawled=9,
        pages_indexed=8,
        chunks_generated=24,
        error_code="CRAWLERROR" if job_status == "FAILED" else None,
        partial_reason="Crawl page limit reached" if job_status == "PARTIAL" else None,
    )

    result = processing_status(
        SimpleNamespace(
            website=repository.website,
            kb_status=kb_status,
            page_count=8,
            chunk_count=24,
        ),
        repository.job,
    )

    assert result.processing_stage == expected_stage
    assert result.knowledge_base_status == kb_status
    assert result.pages_discovered == 12
    assert result.pages_processed == 9
    assert result.pages_succeeded == 8
    assert result.chunks_created == 24


def test_status_endpoint_is_tenant_safe_and_sanitizes_failure_details():
    owner = AuthenticatedUser(user_id=uuid4(), role="customer")
    other = AuthenticatedUser(user_id=uuid4(), role="customer")
    repository = FakeRepository(owner.user_id)
    repository.kb.status = "FAILED"
    repository.job = make_job(
        status="FAILED",
        website_id=repository.website.id,
        knowledge_base_id=repository.kb.id,
        error_code="UNEXPECTED_DATABASE_ERROR",
        error_message="postgresql://private-user:private-password@private-host/database",
    )
    app.dependency_overrides[get_repository] = lambda: repository
    client = TestClient(app)
    try:
        app.dependency_overrides[get_current_user] = lambda: owner
        response = client.get(f"/api/v1/websites/{repository.website.id}/status")
        assert response.status_code == 200
        assert response.json()["processing"]["processing_stage"] == "FAILED"
        assert response.json()["processing"]["error"] == (
            "Website knowledge processing failed. Please try again."
        )
        assert "private-password" not in response.text

        app.dependency_overrides[get_current_user] = lambda: other
        assert client.get(f"/api/v1/websites/{repository.website.id}/status").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_manual_and_automatic_jobs_share_processing_contract():
    repository = FakeRepository(uuid4())
    summary = SimpleNamespace(
        website=repository.website,
        kb_status="CRAWLING",
        page_count=0,
        chunk_count=0,
    )
    automatic = processing_status(summary, make_job(status="RUNNING", is_refresh=False))
    manual = processing_status(summary, make_job(status="RUNNING", is_refresh=True))

    assert automatic.model_dump(exclude={"updated_at"}) == manual.model_dump(
        exclude={"updated_at"}
    )
