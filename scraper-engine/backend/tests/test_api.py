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
        self.job = SimpleNamespace(
            id=uuid4(), status="QUEUED", celery_task_id=None, error_message=None
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
            self.job = SimpleNamespace(
                id=uuid4(), status="QUEUED", celery_task_id=None, error_message=None
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
