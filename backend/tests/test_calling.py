from uuid import uuid4
from fastapi.testclient import TestClient
import pytest

from app.core.security import AuthenticatedUser, get_current_user
from app.main import app


@pytest.fixture
def auth_user():
    return AuthenticatedUser(
        user_id=uuid4(),
        role="customer",
        email="test@trex.internal",
    )


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_calling_requires_auth() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/calling/calls",
            json={
                "lead_id": "lead-1",
                "phone_number": "+1234567890",
                "purpose": "Follow up with lead",
            },
        )
    assert response.status_code == 401


def test_search_mock_kb(auth_user: AuthenticatedUser) -> None:
    app.dependency_overrides[get_current_user] = lambda: auth_user
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/calling/tools/search-client-kb",
                json={"query": "pricing plans"},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["success"] is True
            assert body["data"]["results"] == []
            assert body["data"]["status"] == "mock_pending"
    finally:
        app.dependency_overrides.clear()


def test_vapi_webhook_event_deduplication() -> None:
    payload = {
        "type": "status-update",
        "call": {
            "id": "vapi-call-999",
            "status": "in-progress",
        },
    }
    with TestClient(app) as client:
        # First delivery
        r1 = client.post(
            "/api/v1/webhooks/vapi/events",
            json=payload,
            headers={"X-TPI-Event-Id": "evt-unique-123"},
        )
        assert r1.status_code == 200
        assert r1.json()["success"] is True

        # Second delivery (duplicate event_id)
        r2 = client.post(
            "/api/v1/webhooks/vapi/events",
            json=payload,
            headers={"X-TPI-Event-Id": "evt-unique-123"},
        )
        assert r2.status_code == 200
        assert r2.json()["success"] is True
        assert r2.json()["data"]["status"] == "duplicate"
