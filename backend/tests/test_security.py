from uuid import uuid4

from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.core.security import create_access_token, decode_access_token, digest_token, generate_otp


def test_otp_is_six_digits():
    otp = generate_otp()
    assert len(otp) == 6
    assert otp.isdigit()


def test_refresh_digest_is_stable_and_not_plaintext():
    value = "sample-refresh-token"
    assert digest_token(value) == digest_token(value)
    assert digest_token(value) != value


def test_access_token_contract():
    user_id = uuid4()
    token, expires_in = create_access_token(user_id, "customer")
    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "customer"
    assert payload["type"] == "access"
    assert expires_in > 0


def test_database_url_reserved_password_character_is_encoded():
    normalized = Settings.normalize_database_url("postgresql://user:p@ss@db.example.test/db")
    parsed = make_url(normalized)
    assert parsed.drivername == "postgresql+asyncpg"
    assert parsed.host == "db.example.test"
    assert parsed.password == "p@ss"


def test_psycopg_environment_url_is_normalized_for_async_runtime():
    normalized = Settings.normalize_database_url(
        "postgresql+psycopg://user:password@db.example.test/db"
    )
    assert normalized.startswith("postgresql+asyncpg://")
