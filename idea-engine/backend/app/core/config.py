from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, unquote

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_DB_FILE = str(
    Path(__file__).resolve().parent.parent.parent / "storage" / "idea_dev.db"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    database_url: str = f"sqlite+aiosqlite:///{DEFAULT_DB_FILE}"
    redis_url: str = "redis://localhost:6379/0"

    # Shared Internal TPI Base URL (optional for enhanced LLM summarization)
    tpi_api_base_url: str = "http://localhost:8001"
    tpi_internal_service_token: str = ""

    # Storage for generated DOCX reports
    reports_storage_dir: str = str(
        Path(__file__).resolve().parent.parent.parent / "storage" / "reports"
    )
    report_run_cron: str = "0 0 * * *"

    # CORS
    frontend_origins: str = (
        "http://localhost:5176,http://localhost:5173,http://localhost:5174,http://localhost:5175"
    )

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
                    f"{quote(unquote(username), safe='.')}:"
                    f"{quote(unquote(password), safe='')}@{host_info}"
                )
        if driver in {"postgres", "postgresql", "postgresql+psycopg"}:
            driver = "postgresql+asyncpg"
        return f"{driver}://{remainder}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
