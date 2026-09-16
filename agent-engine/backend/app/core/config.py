from functools import lru_cache
from urllib.parse import quote, unquote

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            ".env",
            "agent-engine/backend/.env",
            "backend/.env",
            "../../backend/.env",
            "../backend/.env",
        ),
        extra="ignore",
    )

    app_env: str = "development"
    database_url: str
    tpi_api_base_url: str = "http://localhost:8001"
    tpi_internal_service_token: str
    auth_jwks_url: str = "http://localhost:8000/.well-known/jwks.json"
    auth_issuer: str = "t-rex"
    auth_audience: str = "t-rex-engines"
    auth_jwt_algorithm: str = "RS256"
    frontend_origins: str = "http://localhost:5173,http://localhost:5174"

    docs_root_path: str = "../../docs/agent-knowledge"
    embedding_provider: str = "jina"
    embedding_model: str = "jina-embeddings-v3"
    embedding_dimension: int = 1024
    embedding_batch_size: int = 32
    default_top_k: int = 5
    default_similarity_threshold: float = 0.5
    agent_assistant_top_k: int = 5
    agent_assistant_min_similarity: float = 0.5
    agent_assistant_context_max_chars: int = 8000

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

    @field_validator("tpi_internal_service_token")
    @classmethod
    def require_service_token(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Internal service tokens must be configured")
        return value

    @field_validator("embedding_dimension")
    @classmethod
    def enforce_migrated_dimension(cls, value: int) -> int:
        if value != 1024:
            raise ValueError("Database migration currently supports 1024-dimensional vectors")
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
