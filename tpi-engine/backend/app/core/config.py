from functools import lru_cache
from urllib.parse import quote, unquote

from pydantic import EmailStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")

    app_env: str = "development"
    tpi_internal_service_token: str = ""
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: EmailStr = "noreply@trex.internal"
    smtp_from_name: str = "T Rex"
    smtp_use_tls: bool = True
    database_url: str | None = None
    redis_url: str = "redis://localhost:6379/0"
    hubspot_client_id: str = ""
    hubspot_client_secret: str = ""
    hubspot_redirect_uri: str = "http://localhost:8001/api/v1/hubspot/callback"
    hubspot_scopes: str = "crm.objects.contacts.read"
    hubspot_token_encryption_key: str = "development-only-key-change-me"
    hubspot_oauth_state_ttl_seconds: int = 600
    hubspot_refresh_skew_seconds: int = 300
    vapi_api_key: str = ""
    vapi_assistant_id: str = ""
    vapi_phone_number_id: str = ""
    vapi_webhook_secret: str = ""
    calling_internal_webhook_url: str = "http://localhost:8002/api/v1/webhooks/vapi/events"

    @field_validator(
        "tpi_internal_service_token",
        "smtp_host",
        "smtp_username",
        "smtp_password",
        "hubspot_client_id",
        "hubspot_client_secret",
        "hubspot_redirect_uri",
        "hubspot_token_encryption_key",
    )
    @classmethod
    def must_not_be_empty(cls, value: str) -> str:
        return value

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        driver, separator, remainder = value.partition("://")
        if not separator:
            return value
        if "@" in remainder:
            user_info, host_info = remainder.rsplit("@", 1)
            if ":" in user_info:
                username, password = user_info.split(":", 1)
                encoded_user = quote(unquote(username), safe=".")
                encoded_password = quote(unquote(password), safe="")
                user_info = f"{encoded_user}:{encoded_password}"
                remainder = f"{user_info}@{host_info}"
        if driver in {"postgres", "postgresql", "postgresql+psycopg"}:
            driver = "postgresql+asyncpg"
        return f"{driver}://{remainder}"

    @property
    def hubspot_scope_list(self) -> list[str]:
        return [scope for scope in self.hubspot_scopes.replace(",", " ").split() if scope]


@lru_cache
def get_settings() -> Settings:
    return Settings()
