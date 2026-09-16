from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_calling_requires_auth(monkeypatch) -> None:
    monkeypatch.setattr("app.core.config.settings.dev_auth_bypass", False)
    response = TestClient(app).post(
        "/api/v1/calling/calls",
    )
    assert response.status_code == 401
