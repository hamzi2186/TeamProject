from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, unquote

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    frontend_url: str = "http://localhost:5173"
    backend_url: str = "http://localhost:8000"
    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    tpi_api_base_url: str = "http://localhost:8001"
    tpi_internal_service_token: str

    auth_jwt_algorithm: str = "RS256"
    auth_jwt_private_key_path: Path = Path(".secrets/auth_private.pem")
    auth_jwt_public_key_path: Path = Path(".secrets/auth_public.pem")
    auth_issuer: str = "t-rex"
    auth_audience: str = "t-rex-engines"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    otp_expire_minutes: int = 10
    otp_resend_cooldown_seconds: int = 60
    otp_max_attempts: int = 5

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        driver, separator, remainder = value.partition("://")
        if not separator:
            return value
        if "@" in remainder:
            user_info, host_info = remainder.rsplit("@", 1)
            if ":" in user_info:
                username, password = user_info.split(":", 1)
                encoded_user = quote(unquote(username), safe=".")
                encoded_password = quote(unquote(password), safe="")
                remainder = f"{encoded_user}:{encoded_password}@{host_info}"
        if driver in {"postgres", "postgresql", "postgresql+psycopg"}:
            driver = "postgresql+asyncpg"
        return f"{driver}://{remainder}"

    @field_validator("tpi_internal_service_token")
    @classmethod
    def token_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("TPI_INTERNAL_SERVICE_TOKEN must be configured")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
