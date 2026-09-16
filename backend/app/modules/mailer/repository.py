from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession


class MailerRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def create_or_get_conversation(self, *, user_id: UUID, lead_id: UUID, campaign_id: UUID | None, subject: str | None, status: str, provider: str = "resend") -> dict[str, Any]:
        conversation_id = str(UUID(int=0))
        # Minimal in-memory placeholder repository; DB-backed implementation can override.
        return {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "lead_id": lead_id,
            "campaign_id": campaign_id,
            "subject": subject,
            "status": status,
            "provider": provider,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }

    async def save_email(self, **kwargs: Any) -> dict[str, Any]:
        return kwargs

    async def record_webhook_event(self, *, provider_event_id: str, **_kwargs: Any) -> bool:
        return True

    async def get_conversation_by_id(self, conversation_id: str) -> dict[str, Any] | None:
        return None

    async def list_recent_messages(self, *, conversation_id: str, limit: int = 10) -> list[dict[str, Any]]:
        return []

    async def get_conversation_for_user(self, user_id: UUID, *, lead_id: UUID | None = None, campaign_id: UUID | None = None) -> dict[str, Any] | None:
        return None

    async def set_conversation_status(self, conversation_id: str, status: str) -> None:
        return None

    async def record_history_event(self, *, user_id: UUID, lead_id: UUID, campaign_id: UUID | None, event_type: str, payload: dict[str, Any]) -> None:
        return None
