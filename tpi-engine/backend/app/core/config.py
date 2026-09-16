from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TwilioNumberRoute(BaseModel):
    user_id: str
    phone_number: str | None = None
    messaging_service_sid: str | None = None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    tpi_internal_service_token: str
    smtp_host: str
    smtp_port: int = 587
    smtp_username: str
    smtp_password: str
    smtp_from_email: EmailStr
    smtp_from_name: str = "T Rex"
    smtp_use_tls: bool = True

    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_number_routes: list[TwilioNumberRoute] = Field(default_factory=list)
    twilio_default_user_id: str | None = None
    twilio_default_sms_from_number: str | None = None
    twilio_messaging_service_sid: str | None = None
    public_webhook_base_url: str | None = None
    sms_engine_internal_base_url: str = "http://sms-backend:8002"
    sms_internal_service_token: str | None = None
    sms_provider: Literal["twilio", "mock"] = "twilio"
    mock_sms_from_number: str = "+15555550100"

    @field_validator(
        "tpi_internal_service_token", "smtp_host", "smtp_username", "smtp_password"
    )
    @classmethod
    def must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Required TPI configuration is empty")
        return value

    @property
    def twilio_configured(self) -> bool:
        return bool(self.twilio_account_sid and self.twilio_auth_token)


@lru_cache
def get_settings() -> Settings:
    return Settings()
