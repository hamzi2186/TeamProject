from functools import lru_cache

from pydantic import EmailStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    @field_validator(
        "tpi_internal_service_token", "smtp_host", "smtp_username", "smtp_password"
    )
    @classmethod
    def must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Required TPI configuration is empty")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
