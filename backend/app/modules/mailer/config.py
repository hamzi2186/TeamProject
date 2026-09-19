from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MailerSettings(BaseSettings):
    """Mailer Engine settings, read from the same .env files as the platform settings."""

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    # Loop-prevention guardrail from the Master PRD, not a normal stopping rule.
    max_autonomous_text_turns: int = Field(default=20, ge=1)

    # Signs the Reply-To token on every email we send. Every process that sends or receives
    # mail must use the same value; changing it stops replies to earlier emails matching.
    mailer_reply_token_secret: str = ""
    mailer_reply_to_domain: str = ""
    mailer_reply_to_mailbox: str = "mailer"

    mailer_kb_top_k: int = Field(default=6, ge=1, le=20)
    mailer_thread_context_emails: int = Field(default=10, ge=1, le=50)


@lru_cache
def get_mailer_settings() -> MailerSettings:
    return MailerSettings()
