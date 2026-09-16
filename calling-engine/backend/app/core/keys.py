from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import get_settings


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else Path.cwd() / path


def load_public_key() -> str:
    """
    Load the RS256 public PEM key for JWT verification.
    Calling Engine is a consumer — it only verifies tokens, never issues them.
    The root platform (feat/foundation-auth-docker) generates and owns the keypair.
    """
    settings = get_settings()
    public_path = _resolve(settings.auth_jwt_public_key_path)
    if not public_path.exists():
        raise RuntimeError(
            f"JWT public key not found at {public_path}. "
            "Copy auth_public.pem from the root platform's .secrets/ directory."
        )
    return public_path.read_text()


def ensure_jwt_keys() -> tuple[str, str]:
    settings = get_settings()
    public_path = _resolve(settings.auth_jwt_public_key_path)
    private_path = public_path.with_name("auth_private.pem")
    if not public_path.exists() or not private_path.exists():
        if settings.app_env == "production":
            raise RuntimeError("JWT keys are not configured")
        public_path.parent.mkdir(parents=True, exist_ok=True)
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_path.write_bytes(private_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        public_path.write_bytes(private_key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    return private_path.read_text(), public_path.read_text()
