import uuid
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.db.session import get_db
from app.main import app
from app.schemas.agent import AgentSearchResponse, IngestResponse, IngestResultItem
from app.services.ingestion import AgentIngestionService
from app.services.retrieval import AgentRetrievalService


def test_health():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "agent"}


def test_admin_ingest_requires_auth():
    client = TestClient(app)
    # No auth header -> 401
    response = client.post("/api/v1/agent/admin/ingest", json={})
    assert response.status_code == 401


def test_admin_ingest_rejects_customer_role():
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        user_id=uuid.uuid4(), role="customer"
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/agent/admin/ingest",
        json={"module_key": "scraper", "force": False},
    )
    assert response.status_code == 403
    app.dependency_overrides.clear()


def test_admin_ingest_allows_admin_role(monkeypatch):
    mock_ingest = AsyncMock(
        return_value=IngestResponse(
            scanned=4,
            created=4,
            updated=0,
            unchanged=0,
            deactivated=0,
            chunks_indexed=8,
            details=[
                IngestResultItem(
                    source_path="scraper/overview.md",
                    module_key="scraper",
                    status="created",
                    chunk_count=2,
                    title="Overview",
                )
            ],
        )
    )
    monkeypatch.setattr(AgentIngestionService, "ingest", mock_ingest)

    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        user_id=uuid.uuid4(), role="admin"
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/agent/admin/ingest",
        json={"module_key": "scraper", "force": False},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["scanned"] == 4
    assert data["created"] == 4
    assert data["chunks_indexed"] == 8
    app.dependency_overrides.clear()


def test_public_search_requires_auth():
    client = TestClient(app)
    response = client.post(
        "/api/v1/agent/retrieval/search",
        json={"query": "test query"},
    )
    assert response.status_code == 401


def test_public_search_with_user_auth(monkeypatch):
    mock_search = AsyncMock(
        return_value=AgentSearchResponse(
            query="test query",
            module_filter=None,
            total=0,
            items=[],
        )
    )
    monkeypatch.setattr(AgentRetrievalService, "search", mock_search)

    app.dependency_overrides[get_db] = lambda: AsyncMock()
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        user_id=uuid.uuid4(), role="customer"
    )
    client = TestClient(app)

    response = client.post(
        "/api/v1/agent/retrieval/search",
        json={"query": "test query"},
    )
    assert response.status_code == 200
    app.dependency_overrides.clear()
