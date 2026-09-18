from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError, SecretStr

from app.api import dependencies, email_delivery
from app.contracts.email import EmailDeliveryRequest
from app.core.config import Settings
from app.providers.resend import adapter as resend_adapter
from app.providers.resend.adapter import ResendDeliveryError
from app.providers.smtp import adapter as smtp_adapter
from app.services import email_delivery as email_service
from app.services.email_delivery import EmailDeliveryError


def settings_values(**overrides):
    values = {
        "_env_file": None,
        "tpi_internal_service_token": "internal-test-token",
        "hubspot_client_id": "hubspot-client",
        "hubspot_client_secret": "hubspot-secret",
        "hubspot_redirect_uri": "http://localhost:8001/api/v1/hubspot/callback",
        "hubspot_token_encryption_key": "encryption-key",
    }
    values.update(overrides)
    return values


@pytest.mark.asyncio
async def test_internal_email_endpoint_sends_verification_template(monkeypatch):
    send_email = AsyncMock(return_value="smtp")
    monkeypatch.setattr(email_delivery, "send_email", send_email)
    monkeypatch.setattr(
        dependencies,
        "get_settings",
        lambda: type("Settings", (), {"tpi_internal_service_token": "internal-test-token"})(),
    )
    payload = EmailDeliveryRequest(
        to="person@example.com",
        template="verify_email",
        variables={"code": "123456"},
    )

    result = await email_delivery.deliver(payload, "internal-test-token")

    assert result.accepted is True
    assert result.transport == "smtp"
    send_email.assert_awaited_once_with(
        "person@example.com", "verify_email", {"code": "123456"}
    )


@pytest.mark.asyncio
async def test_internal_email_endpoint_rejects_invalid_service_token(monkeypatch):
    send_email = AsyncMock()
    monkeypatch.setattr(email_delivery, "send_email", send_email)
    monkeypatch.setattr(
        dependencies,
        "get_settings",
        lambda: type("Settings", (), {"tpi_internal_service_token": "internal-test-token"})(),
    )
    payload = EmailDeliveryRequest(
        to="person@example.com",
        template="verify_email",
        variables={"code": "123456"},
    )

    with pytest.raises(HTTPException) as caught:
        await email_delivery.deliver(payload, "wrong-token")

    assert caught.value.status_code == 401
    send_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_internal_email_endpoint_sanitizes_smtp_failure(monkeypatch):
    monkeypatch.setattr(
        email_delivery,
        "send_email",
        AsyncMock(side_effect=EmailDeliveryError("provider secret response")),
    )
    monkeypatch.setattr(
        dependencies,
        "get_settings",
        lambda: type("Settings", (), {"tpi_internal_service_token": "internal-test-token"})(),
    )
    payload = EmailDeliveryRequest(
        to="person@example.com",
        template="verify_email",
        variables={"code": "123456"},
    )

    with pytest.raises(HTTPException) as caught:
        await email_delivery.deliver(payload, "internal-test-token")

    assert caught.value.status_code == 502
    assert caught.value.detail == "Email provider delivery failed"
    assert "secret" not in caught.value.detail


@pytest.mark.asyncio
async def test_smtp_mode_selects_only_smtp(monkeypatch):
    smtp_send = AsyncMock()
    resend_send = AsyncMock()
    monkeypatch.setattr(
        email_service, "get_settings", lambda: SimpleNamespace(email_provider="smtp")
    )
    monkeypatch.setattr(smtp_adapter, "send_email", smtp_send)
    monkeypatch.setattr(resend_adapter, "send_email", resend_send)

    provider = await email_service.send_email(
        "person@example.com", "verify_email", {"code": "123456"}
    )

    assert provider == "smtp"
    smtp_send.assert_awaited_once()
    resend_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_resend_mode_selects_only_resend(monkeypatch):
    smtp_send = AsyncMock()
    resend_send = AsyncMock()
    monkeypatch.setattr(
        email_service, "get_settings", lambda: SimpleNamespace(email_provider="resend")
    )
    monkeypatch.setattr(smtp_adapter, "send_email", smtp_send)
    monkeypatch.setattr(resend_adapter, "send_email", resend_send)

    provider = await email_service.send_email(
        "person@example.com", "reset_password", {"code": "654321"}
    )

    assert provider == "resend"
    resend_send.assert_awaited_once()
    smtp_send.assert_not_awaited()


def test_smtp_configuration_does_not_require_resend_fields():
    settings = Settings(
        **settings_values(
            smtp_host="smtp.example.com",
            smtp_username="smtp-user",
            smtp_password="smtp-password",
            smtp_from_email="sender@example.com",
            resend_api_key="",
            resend_from_email="",
        )
    )

    assert settings.email_provider == "smtp"
    assert settings.resend_api_key is None


def test_resend_configuration_does_not_require_smtp_fields():
    settings = Settings(
        **settings_values(
            email_provider="resend",
            resend_api_key="resend-api-key",
            resend_from_email="verified@example.com",
            smtp_host="",
            smtp_username="",
            smtp_password="",
            smtp_from_email="",
        )
    )

    assert settings.email_provider == "resend"
    assert settings.smtp_host is None


@pytest.mark.parametrize(
    ("provider", "values", "expected_field"),
    [
        ("smtp", {"smtp_password": "smtp-private-value"}, "SMTP_HOST"),
        ("resend", {"resend_api_key": "resend-private-value"}, "RESEND_FROM_EMAIL"),
    ],
)
def test_missing_selected_provider_configuration_fails_safely(
    provider, values, expected_field
):
    with pytest.raises(ValidationError) as caught:
        Settings(**settings_values(email_provider=provider, **values))

    error = str(caught.value)
    assert expected_field in error
    assert "resend-private-value" not in error
    assert "smtp-private-value" not in error


@pytest.mark.asyncio
async def test_resend_adapter_uses_https_api_and_existing_template(monkeypatch):
    request = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *, timeout):
            request["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, url, *, headers, json):
            request.update(url=url, headers=headers, json=json)
            return FakeResponse()

    monkeypatch.setattr(resend_adapter.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(
        resend_adapter,
        "get_settings",
        lambda: SimpleNamespace(
            resend_api_key=SecretStr("resend-api-key"),
            resend_from_email="verified@example.com",
            resend_from_name="T Rex",
        ),
    )

    await resend_adapter.send_email(
        "person@example.com", "verify_email", {"code": "123456"}
    )

    assert request["url"] == "https://api.resend.com/emails"
    assert request["headers"]["Authorization"].startswith("Bearer ")
    assert request["json"]["to"] == ["person@example.com"]
    assert request["json"]["subject"] == "Verify your T Rex account"
    assert "123456" in request["json"]["text"]


@pytest.mark.asyncio
async def test_resend_success_maps_to_existing_endpoint_contract(monkeypatch):
    monkeypatch.setattr(
        email_delivery, "send_email", AsyncMock(return_value="resend")
    )
    monkeypatch.setattr(
        dependencies,
        "get_settings",
        lambda: SimpleNamespace(tpi_internal_service_token="internal-test-token"),
    )
    payload = EmailDeliveryRequest(
        to="person@example.com",
        template="verify_email",
        variables={"code": "123456"},
    )

    result = await email_delivery.deliver(payload, "internal-test-token")

    assert result.accepted is True
    assert result.transport == "resend"


@pytest.mark.asyncio
async def test_resend_provider_failure_is_sanitized(monkeypatch):
    monkeypatch.setattr(
        email_service, "get_settings", lambda: SimpleNamespace(email_provider="resend")
    )
    monkeypatch.setattr(
        resend_adapter,
        "send_email",
        AsyncMock(side_effect=ResendDeliveryError("api-key and private provider body")),
    )
    monkeypatch.setattr(email_delivery, "send_email", email_service.send_email)
    monkeypatch.setattr(
        dependencies,
        "get_settings",
        lambda: SimpleNamespace(tpi_internal_service_token="internal-test-token"),
    )
    payload = EmailDeliveryRequest(
        to="person@example.com",
        template="verify_email",
        variables={"code": "123456"},
    )

    with pytest.raises(HTTPException) as caught:
        await email_delivery.deliver(payload, "internal-test-token")

    assert caught.value.status_code == 502
    assert caught.value.detail == "Email provider delivery failed"
    assert "api-key" not in caught.value.detail
