from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api import auth as auth_api
from app.auth import service as auth_service
from app.core.config import Settings
from app.core.security import verify_token
from app.models.auth import AppUser
from app.schemas.auth import EmailOtpRequest, EmailRequest, RegisterRequest
from app.services import tpi_email
from app.services.tpi_email import EmailDeliveryError


def make_db(**overrides):
    defaults = {
        "scalar": AsyncMock(),
        "commit": AsyncMock(),
        "refresh": AsyncMock(),
        "execute": AsyncMock(),
        "add": Mock(),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.mark.asyncio
async def test_registration_delivery_failure_keeps_user_and_returns_safe_result(monkeypatch):
    db = make_db(scalar=AsyncMock(return_value=None))
    monkeypatch.setattr(
        auth_api,
        "issue_otp",
        AsyncMock(side_effect=EmailDeliveryError("provider detail with smtp-password")),
    )

    result = await auth_api.register(
        RegisterRequest(email="new@example.com", password="new password value"), db
    )

    assert db.add.call_count == 1
    assert db.commit.await_count == 1
    assert result.verification_email_sent is False
    assert "smtp-password" not in result.message
    assert "resend verification" in result.message.lower()


@pytest.mark.asyncio
async def test_issue_otp_persists_hashed_code_then_calls_tpi_email(monkeypatch):
    db = make_db(scalar=AsyncMock(return_value=None))
    user = AppUser(id=uuid4(), email="person@example.com", role="customer")
    send_auth_email = AsyncMock()
    monkeypatch.setattr(auth_service, "generate_otp", lambda: "123456")
    monkeypatch.setattr(auth_service, "send_auth_email", send_auth_email)
    monkeypatch.setattr(
        auth_service,
        "get_settings",
        lambda: SimpleNamespace(otp_resend_cooldown_seconds=60, otp_expire_minutes=10),
    )

    await auth_service.issue_otp(db, user, "verify_email")

    otp = db.add.call_args.args[0]
    assert otp.user_id == user.id
    assert otp.purpose == "verify_email"
    assert otp.code_hash != "123456"
    assert verify_token("123456", otp.code_hash)
    assert otp.expires_at > datetime.now(UTC)
    db.commit.assert_awaited_once()
    send_auth_email.assert_awaited_once_with(
        to="person@example.com", template="verify_email", code="123456"
    )


@pytest.mark.asyncio
async def test_issue_otp_invalidates_undelivered_code_so_resend_can_retry(monkeypatch):
    db = make_db(scalar=AsyncMock(return_value=None))
    user = AppUser(id=uuid4(), email="person@example.com", role="customer")
    monkeypatch.setattr(auth_service, "generate_otp", lambda: "123456")
    monkeypatch.setattr(
        auth_service,
        "send_auth_email",
        AsyncMock(side_effect=EmailDeliveryError("private provider failure")),
    )
    monkeypatch.setattr(
        auth_service,
        "get_settings",
        lambda: SimpleNamespace(otp_resend_cooldown_seconds=60, otp_expire_minutes=10),
    )

    with pytest.raises(EmailDeliveryError):
        await auth_service.issue_otp(db, user, "verify_email")

    otp = db.add.call_args.args[0]
    assert otp.used_at is not None
    assert db.commit.await_count == 2
    lookup = db.scalar.await_args.args[0]
    assert "auth_otp_codes.used_at IS NULL" in str(lookup)


@pytest.mark.asyncio
async def test_tpi_client_uses_internal_token_contract_without_smtp_configuration(monkeypatch):
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

    monkeypatch.setattr(tpi_email.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(
        tpi_email,
        "get_settings",
        lambda: SimpleNamespace(
            tpi_api_base_url="http://tpi:8001",
            tpi_internal_service_token="internal-token",
        ),
    )

    await tpi_email.send_auth_email(
        to="person@example.com", template="verify_email", code="123456"
    )

    assert request["url"] == "http://tpi:8001/api/v1/internal/email-delivery/send"
    assert request["headers"] == {"X-TPI-Service-Token": "internal-token"}
    assert request["json"] == {
        "to": "person@example.com",
        "template": "verify_email",
        "variables": {"code": "123456"},
    }
    assert not any(name.startswith("smtp") for name in Settings.model_fields)


@pytest.mark.asyncio
async def test_email_verification_consumes_code_and_marks_user_verified(monkeypatch):
    user = AppUser(id=uuid4(), email="person@example.com", role="customer")
    otp = SimpleNamespace(
        code_hash=auth_service.hash_token("123456"),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        attempt_count=0,
        used_at=None,
    )
    db = make_db(scalar=AsyncMock(side_effect=[user, otp]))
    monkeypatch.setattr(auth_api, "get_settings", lambda: SimpleNamespace(otp_max_attempts=5))

    result = await auth_api.verify_email(
        EmailOtpRequest(email="person@example.com", code="123456"), db
    )

    assert result == {"message": "Email verified successfully"}
    assert otp.used_at is not None
    assert user.email_verified_at is not None
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_resend_tpi_failure_returns_sanitized_503(monkeypatch):
    user = AppUser(id=uuid4(), email="person@example.com", role="customer")
    db = make_db(scalar=AsyncMock(return_value=user))
    monkeypatch.setattr(
        auth_api,
        "issue_otp",
        AsyncMock(side_effect=EmailDeliveryError("smtp secret and provider response")),
    )

    with pytest.raises(HTTPException) as caught:
        await auth_api.resend_verification(EmailRequest(email=user.email), db)

    assert caught.value.status_code == 503
    assert caught.value.detail == (
        "Verification email delivery is temporarily unavailable. Please try again."
    )
    assert "smtp secret" not in caught.value.detail
