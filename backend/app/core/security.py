import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from cryptography.hazmat.primitives import serialization
from pwdlib import PasswordHash

from app.core.config import get_settings
from app.core.keys import ensure_jwt_keys

password_hash = PasswordHash.recommended()


def hash_secret(value: str) -> str:
    return password_hash.hash(value)


def verify_secret(value: str, encoded: str) -> bool:
    return password_hash.verify(value, encoded)


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def digest_token(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def create_access_token(user_id: UUID, role: str) -> tuple[str, int]:
    settings = get_settings()
    private_key, _ = ensure_jwt_keys()
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iss": settings.auth_issuer,
        "aud": settings.auth_audience,
        "iat": now,
        "exp": expires,
        "jti": str(uuid4()),
    }
    token = jwt.encode(payload, private_key, algorithm=settings.auth_jwt_algorithm)
    return token, int((expires - now).total_seconds())


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    _, public_key = ensure_jwt_keys()
    return jwt.decode(
        token,
        public_key,
        algorithms=[settings.auth_jwt_algorithm],
        audience=settings.auth_audience,
        issuer=settings.auth_issuer,
    )


def public_jwk() -> dict:
    settings = get_settings()
    _, public_pem = ensure_jwt_keys()
    key = serialization.load_pem_public_key(public_pem.encode())
    numbers = key.public_numbers()

    def encode_int(number: int) -> str:
        raw = number.to_bytes((number.bit_length() + 7) // 8, "big")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return {
        "kty": "RSA",
        "use": "sig",
        "kid": "trex-auth-1",
        "alg": settings.auth_jwt_algorithm,
        "n": encode_int(numbers.n),
        "e": encode_int(numbers.e),
    }
