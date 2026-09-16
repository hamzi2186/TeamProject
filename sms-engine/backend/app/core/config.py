from functools import lru_cache
from typing import Literal
from urllib.parse import quote, unquote

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    frontend_url: str = "http://localhost:5174"
    database_url: str
    redis_url: str = "redis://localhost:6379/1"

    auth_jwks_url: str = "http://localhost:8000/.well-known/jwks.json"
    auth_issuer: str = "t-rex"
    auth_audience: str = "t-rex-engines"
    allow_demo_identity: bool = True

    tpi_api_base_url: str = "http://localhost:8001"
    tpi_internal_service_token: str
    sms_internal_service_token: str
    sms_provider: Literal["twilio", "mock"] = "twilio"

    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-20b"
    groq_temperature: float = 0.25
    groq_max_completion_tokens: int = 1024

    default_timezone: str = "America/New_York"
    quiet_hours_start: int = 20
    quiet_hours_end: int = 8
    max_agent_turns: int = 8

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
                remainder = (
                    f"{quote(unquote(username), safe='.')}:{quote(unquote(password), safe='')}"
                    f"@{host_info}"
                )
        if driver in {"postgres", "postgresql", "postgresql+psycopg"}:
            driver = "postgresql+asyncpg"
        return f"{driver}://{remainder}"

    @field_validator("tpi_internal_service_token", "sms_internal_service_token")
    @classmethod
    def token_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Internal service tokens must be configured")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
