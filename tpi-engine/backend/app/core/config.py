from functools import lru_cache
from ipaddress import ip_address
from typing import Literal
from urllib.parse import quote, unquote, urlsplit

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    SecretStr,
    ValidationInfo,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


def validate_hubspot_redirect_uri(value: str, *, app_env: str) -> str:
    """Validate the browser-facing OAuth callback without rewriting it."""
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ValueError(
            "HUBSPOT_REDIRECT_URI must be a valid absolute HTTP/HTTPS callback URL"
        ) from exc

    if parsed.scheme not in {"http", "https"} or not parsed.hostname or not parsed.path:
        raise ValueError(
            "HUBSPOT_REDIRECT_URI must be an absolute HTTP/HTTPS callback URL with a path"
        )
    if parsed.username or parsed.password or port is not None and not 1 <= port <= 65535:
        raise ValueError("HUBSPOT_REDIRECT_URI must not include credentials and must use a valid port")

    if app_env.lower() in {"development", "dev", "local"}:
        hostname = parsed.hostname.lower()
        try:
            ip_address(hostname)
            browser_reachable = True
        except ValueError:
            browser_reachable = hostname == "localhost" or "." in hostname
        if not browser_reachable:
            raise ValueError(
                "HUBSPOT_REDIRECT_URI must use a browser-reachable host in local development "
                "(for example localhost, a LAN IP, or a DNS name), not a Docker-only hostname"
            )
    return value


class TwilioNumberRoute(BaseModel):
    user_id: str
    phone_number: str | None = None
    messaging_service_sid: str | None = None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")

    app_env: str = "development"
    frontend_url: str = "http://localhost:5173"
    tpi_internal_service_token: str
    email_provider: Literal["smtp", "resend"] = "smtp"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from_email: EmailStr | None = None
    smtp_from_name: str = "T Rex"
    smtp_use_tls: bool = True
    resend_api_key: SecretStr | None = None
    resend_from_email: EmailStr | None = None
    resend_from_name: str = "T Rex"
    database_url: str | None = None
    redis_url: str = "redis://localhost:6379/0"

    # HubSpot OAuth
    hubspot_client_id: str
    hubspot_client_secret: str
    hubspot_redirect_uri: str
    hubspot_scopes: str = "crm.objects.contacts.read"
    hubspot_token_encryption_key: str
    hubspot_oauth_state_ttl_seconds: int = 600
    hubspot_refresh_skew_seconds: int = 300

    # Embeddings (scraper + agent)
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
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    llm_timeout_seconds: float = 30.0

    # SMS / Twilio
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_number_routes: list[TwilioNumberRoute] = Field(default_factory=list)
    twilio_default_user_id: str | None = None
    twilio_default_sms_from_number: str | None = None
    twilio_messaging_service_sid: str | None = None
    public_webhook_base_url: str | None = None
    sms_engine_internal_base_url: str = "http://sms-backend:8004"
    sms_internal_service_token: str | None = None
    sms_provider: Literal["twilio", "mock"] = "twilio"
    mock_sms_from_number: str = "+15555550100"

    # Vapi (Calling Engine)
    vapi_api_key: str = ""
    vapi_assistant_id: str = ""
    vapi_phone_number_id: str = ""
    vapi_webhook_secret: str = ""
    calling_internal_webhook_url: str = "http://backend:8000/api/v1/webhooks/vapi/events"

    @field_validator(
        "tpi_internal_service_token",
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

    @model_validator(mode="after")
    def email_provider_configuration_is_complete(self) -> "Settings":
        if self.email_provider == "smtp":
            required = {
                "SMTP_HOST": self.smtp_host,
                "SMTP_USERNAME": self.smtp_username,
                "SMTP_PASSWORD": self.smtp_password,
                "SMTP_FROM_EMAIL": self.smtp_from_email,
            }
        else:
            required = {
                "RESEND_API_KEY": self.resend_api_key,
                "RESEND_FROM_EMAIL": self.resend_from_email,
            }
        missing = [
            name
            for name, value in required.items()
            if not (
                value.get_secret_value().strip()
                if isinstance(value, SecretStr)
                else str(value or "").strip()
            )
        ]
        if missing:
            raise ValueError(
                f"EMAIL_PROVIDER={self.email_provider} requires: {', '.join(missing)}"
            )
        return self

    @field_validator(
        "smtp_host",
        "smtp_username",
        "smtp_password",
        "smtp_from_email",
        "resend_api_key",
        "resend_from_email",
        mode="before",
    )
    @classmethod
    def blank_provider_setting_is_unset(cls, value: object) -> object:
        if isinstance(value, SecretStr):
            return None if not value.get_secret_value().strip() else value
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("hubspot_redirect_uri")
    @classmethod
    def redirect_uri_must_be_browser_reachable(
        cls, value: str, info: ValidationInfo
    ) -> str:
        return validate_hubspot_redirect_uri(
            value, app_env=str(info.data.get("app_env", "development"))
        )

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

    @property
    def twilio_configured(self) -> bool:
        return bool(self.twilio_account_sid and self.twilio_auth_token)

    @property
    def vapi_configured(self) -> bool:
        return bool(self.vapi_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
