from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api import dependencies, email_delivery
from app.contracts.email import EmailDeliveryRequest
from app.providers.smtp.adapter import SmtpDeliveryError


@pytest.mark.asyncio
async def test_internal_email_endpoint_sends_verification_template(monkeypatch):
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
        AsyncMock(side_effect=SmtpDeliveryError("smtp-password=secret provider response")),
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
