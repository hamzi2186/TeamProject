from functools import lru_cache
from urllib.parse import quote, unquote

from pydantic import EmailStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    frontend_url: str = "http://localhost:5173"
    tpi_internal_service_token: str
    smtp_host: str
    smtp_port: int = 587
    smtp_username: str
    smtp_password: str
    smtp_from_email: EmailStr
    smtp_from_name: str = "T Rex"
    smtp_use_tls: bool = True
    database_url: str | None = None
    redis_url: str = "redis://localhost:6379/0"
    hubspot_client_id: str
    hubspot_client_secret: str
    hubspot_redirect_uri: str
    hubspot_scopes: str = "crm.objects.contacts.read"
    hubspot_token_encryption_key: str
    hubspot_oauth_state_ttl_seconds: int = 600
    hubspot_refresh_skew_seconds: int = 300
    embedding_provider: str = "jina"
    embedding_fallback_provider: str | None = None
    jina_api_key: str | None = None
    jina_embedding_model: str = "jina-embeddings-v3"
    jina_embedding_dimension: int = 1024
    local_embedding_model: str = "trex-local-hash-v1"
    local_embedding_dimension: int = 1024
    embedding_timeout_seconds: float = 30
    agent_jina_api_key: str | None = None
    agent_jina_embedding_model: str = "jina-embeddings-v3"
    agent_jina_embedding_dimension: int = 1024

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
        if not value.strip():
            raise ValueError("Required TPI configuration is empty")
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
