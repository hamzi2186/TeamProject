from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi import Response

from app.api import auth as auth_api
from app.core.security import (
    hash_password,
    hash_token,
    verify_password,
    verify_token,
)
from app.models.auth import AppUser, AuthCredential
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
)


def make_db(**overrides):
    defaults = {
        "scalar": AsyncMock(),
        "commit": AsyncMock(),
        "refresh": AsyncMock(),
        "execute": AsyncMock(),
        "get": AsyncMock(),
        "add": Mock(),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_user(password_hash: str) -> AppUser:
    user = AppUser(
        id=uuid4(),
        email="person@example.com",
        role="customer",
        email_verified_at=datetime.now(UTC),
    )
    user.credential = AuthCredential(password_hash=password_hash)
    return user


def test_argon2id_password_hashing_is_salted_and_verifies():
    first = hash_password("correct horse battery staple")
    second = hash_password("correct horse battery staple")

    assert first.startswith("$argon2id$")
    assert second.startswith("$argon2id$")
    assert first != second
    assert verify_password("correct horse battery staple", first)
    assert not verify_password("incorrect password", first)


def test_legacy_sha256_password_verifies():
    legacy_hash = hash_token("legacy password")

    assert verify_password("legacy password", legacy_hash)
    assert not verify_password("incorrect password", legacy_hash)


@pytest.mark.asyncio
async def test_legacy_login_upgrades_hash_and_subsequent_login_uses_argon2(monkeypatch):
    user = make_user(hash_token("legacy password"))
    db = make_db(scalar=AsyncMock(return_value=user))
    create_session = AsyncMock(return_value=SimpleNamespace(access_token="issued"))
    monkeypatch.setattr(auth_api, "create_session", create_session)
    payload = LoginRequest(email=user.email, password="legacy password")

    await auth_api.login(payload, Response(), db)

    upgraded_hash = user.credential.password_hash
    assert upgraded_hash.startswith("$argon2id$")
    assert verify_password("legacy password", upgraded_hash)
    db.commit.assert_awaited_once()

    db.commit.reset_mock()
    await auth_api.login(payload, Response(), db)

    assert user.credential.password_hash == upgraded_hash
    db.commit.assert_not_awaited()
    assert create_session.await_count == 2


@pytest.mark.asyncio
async def test_registration_stores_argon2id_hash(monkeypatch):
    db = make_db(scalar=AsyncMock(return_value=None))
    issue_otp = AsyncMock()
    monkeypatch.setattr(auth_api, "issue_otp", issue_otp)

    result = await auth_api.register(
        RegisterRequest(email="new@example.com", password="new password value"), db
    )

    user = db.add.call_args.args[0]
    assert user.credential.password_hash.startswith("$argon2id$")
    assert verify_password("new password value", user.credential.password_hash)
    assert user.email_verified_at is None
    issue_otp.assert_awaited_once_with(db, user, "verify_email")
    assert result.verification_email_sent is True


@pytest.mark.asyncio
async def test_password_reset_stores_argon2id_hash_and_revokes_sessions(monkeypatch):
    user = make_user(hash_password("previous password"))
    otp = SimpleNamespace(
        code_hash=hash_token("123456"),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        attempt_count=0,
        used_at=None,
    )
    db = make_db(scalar=AsyncMock(side_effect=[user, otp]))
    monkeypatch.setattr(auth_api, "get_settings", lambda: SimpleNamespace(otp_max_attempts=5))

    await auth_api.reset_password(
        ResetPasswordRequest(
            email=user.email,
            code="123456",
            new_password="replacement password",
        ),
        db,
    )

    assert user.credential.password_hash.startswith("$argon2id$")
    assert verify_password("replacement password", user.credential.password_hash)
    assert not verify_password("previous password", user.credential.password_hash)
    assert otp.used_at is not None
    db.execute.assert_awaited_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_otp_verification_keeps_deterministic_sha256_behavior(monkeypatch):
    user = make_user(hash_password("unchanged password"))
    otp = SimpleNamespace(
        code_hash=hash_token("654321"),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        attempt_count=0,
        used_at=None,
    )
    db = make_db(scalar=AsyncMock(return_value=otp))
    monkeypatch.setattr(auth_api, "get_settings", lambda: SimpleNamespace(otp_max_attempts=5))

    await auth_api._consume_otp(db, user, "verify_email", "654321")

    assert verify_token("654321", otp.code_hash)
    assert otp.used_at is not None
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_token_rotation_remains_working(monkeypatch):
    user = make_user(hash_password("unchanged password"))
    stored = SimpleNamespace(
        user_id=user.id,
        revoked_at=None,
        expires_at=datetime.now(UTC) + timedelta(days=1),
        replaced_by_token_id=None,
    )
    replacement = SimpleNamespace(id=uuid4())
    db = make_db(
        scalar=AsyncMock(side_effect=[stored, replacement]),
        get=AsyncMock(return_value=user),
    )
    rotated = SimpleNamespace(refresh_token="replacement opaque token")
    monkeypatch.setattr(auth_api, "create_session", AsyncMock(return_value=rotated))

    result = await auth_api.refresh(
        RefreshRequest(refresh_token="original opaque token"), Response(), db
    )

    assert result is rotated
    assert stored.revoked_at is not None
    assert stored.replaced_by_token_id == replacement.id
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_logout_revocation_remains_working():
    db = make_db()
    response = Response()

    await auth_api.logout(
        LogoutRequest(refresh_token="opaque token"), response, db
    )

    db.execute.assert_awaited_once()
    db.commit.assert_awaited_once()
    assert response.status_code == 204
