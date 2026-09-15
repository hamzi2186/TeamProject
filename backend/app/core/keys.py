import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import get_settings


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else Path.cwd() / path


def ensure_jwt_keys() -> tuple[str, str]:
    settings = get_settings()
    private_path = _resolve(settings.auth_jwt_private_key_path)
    public_path = _resolve(settings.auth_jwt_public_key_path)
    if not private_path.exists() or not public_path.exists():
        private_path.parent.mkdir(parents=True, exist_ok=True)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_bytes = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        public_bytes = key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        temp_private = private_path.with_suffix(".tmp")
        temp_public = public_path.with_suffix(".tmp")
        temp_private.write_bytes(private_bytes)
        temp_public.write_bytes(public_bytes)
        os.replace(temp_private, private_path)
        os.replace(temp_public, public_path)
    return private_path.read_text(), public_path.read_text()
