from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    frontend_url: str = "http://localhost:5174"
    backend_url: str = "http://localhost:8002"

    # Database (shared Supabase/PostgreSQL project)
    database_url: str = "sqlite+aiosqlite:///./calling-engine.db"

    # Redis (shared)
    redis_url: str = "redis://localhost:6379/0"

    # TPI engine internal service
    tpi_api_base_url: str = "http://localhost:8001"
    tpi_internal_service_token: str = ""

    # Auth — Calling Engine only VERIFIES tokens (RS256 public key only)
    auth_jwt_algorithm: str = "RS256"
    auth_jwt_public_key_path: Path = Path(".secrets/auth_public.pem")
    auth_issuer: str = "t-rex"
    auth_audience: str = "t-rex-engines"
    dev_auth_bypass: bool = False

    # Calling engine specifics
    # URL where TPI will POST normalized Vapi events back to this engine
    calling_internal_webhook_url: str = "http://localhost:8002/api/v1/webhooks/vapi/events"
    tpi_request_timeout_seconds: float = 20.0


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
