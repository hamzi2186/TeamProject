from fastapi.testclient import TestClient

from app.main import app


def test_webhook_requires_event_id() -> None:
    response = TestClient(app).post("/api/v1/webhooks/vapi/events", json={"type": "call-ended"})
    assert response.status_code == 400


def test_webhook_deduplicates_event() -> None:
    client = TestClient(app)
    headers = {"X-Vapi-Event-Id": "event-1"}
    assert client.post("/api/v1/webhooks/vapi/events", headers=headers, json={}).json() == {"status": "accepted"}
    assert client.post("/api/v1/webhooks/vapi/events", headers=headers, json={}).json() == {"status": "duplicate"}
