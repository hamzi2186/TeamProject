from pathlib import Path

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
