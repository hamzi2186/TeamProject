from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calling import Call, SeenWebhookEvent
from app.modules.calling.contracts import CallRecord
from app.modules.calling.exceptions import CallNotFoundError


class CallRepository(Protocol):
    async def save(self, call: CallRecord) -> CallRecord: ...
    async def list_for_user(self, user_id: UUID) -> list[CallRecord]: ...
    async def get_for_user(self, user_id: UUID, call_id: str) -> CallRecord: ...
    async def get_by_provider_call_id(self, provider_call_id: str) -> CallRecord | None: ...
    async def has_event(self, event_id: str) -> bool: ...
    async def record_event(self, event_id: str) -> None: ...


def _row_to_record(row: Call) -> CallRecord:
    """Convert SQLAlchemy Call ORM row to Pydantic CallRecord."""
    return CallRecord(
        call_id=str(row.id),
        conversation_id=str(row.conversation_id) if row.conversation_id else None,
        user_id=str(row.user_id),
        lead_id=row.lead_id,
        direction=row.direction,
        from_number=row.from_number,
        to_number=row.to_number,
        provider=row.provider,
        provider_call_id=row.provider_call_id,
        status=row.status,
        started_at=row.started_at,
        ended_at=row.ended_at,
        duration_seconds=row.duration_seconds,
        transcript=row.transcript,
        summary=row.summary,
        outcome=row.outcome,
        recording_url=row.recording_url,
        provider_payload=row.provider_payload or {},
    )


class SQLCallRepository:
    """PostgreSQL-backed call repository via shared Supabase project."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def save(self, call: CallRecord) -> CallRecord:
        import uuid as _uuid

        call_uuid = _uuid.UUID(call.call_id)
        user_uuid = _uuid.UUID(call.user_id)
        conv_uuid = _uuid.UUID(call.conversation_id) if call.conversation_id else None

        existing = await self.db.get(Call, call_uuid)
        if existing is None:
            row = Call(
                id=call_uuid,
                user_id=user_uuid,
                lead_id=call.lead_id,
                conversation_id=conv_uuid,
                campaign_id=None,
                direction=call.direction,
                from_number=call.from_number,
                to_number=call.to_number,
                provider=call.provider,
                provider_call_id=call.provider_call_id,
                status=call.status,
                started_at=call.started_at,
                ended_at=call.ended_at,
                duration_seconds=call.duration_seconds,
                transcript=call.transcript,
                summary=call.summary,
                outcome=call.outcome,
                recording_url=call.recording_url,
                provider_payload=call.provider_payload,
            )
            self.db.add(row)
        else:
            existing.status = call.status
            existing.started_at = call.started_at or existing.started_at
            existing.ended_at = call.ended_at or existing.ended_at
            existing.duration_seconds = call.duration_seconds or existing.duration_seconds
            existing.transcript = call.transcript or existing.transcript
            existing.summary = call.summary or existing.summary
            existing.outcome = call.outcome or existing.outcome
            existing.recording_url = call.recording_url or existing.recording_url
            existing.provider_payload = call.provider_payload or existing.provider_payload
            existing.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        return call

    async def list_for_user(self, user_id: UUID) -> list[CallRecord]:
        result = await self.db.execute(
            select(Call).where(Call.user_id == user_id).order_by(Call.created_at.desc())
        )
        return [_row_to_record(row) for row in result.scalars().all()]

    async def get_for_user(self, user_id: UUID, call_id: str) -> CallRecord:
        import uuid as _uuid
        row = await self.db.get(Call, _uuid.UUID(call_id))
        if row is None or row.user_id != user_id:
            raise CallNotFoundError(call_id)
        return _row_to_record(row)

    async def get_by_provider_call_id(self, provider_call_id: str) -> CallRecord | None:
        result = await self.db.execute(
            select(Call).where(Call.provider_call_id == provider_call_id)
        )
        row = result.scalar_one_or_none()
        return _row_to_record(row) if row else None

    async def has_event(self, event_id: str) -> bool:
        result = await self.db.execute(
            select(SeenWebhookEvent).where(SeenWebhookEvent.event_id == event_id)
        )
        return result.scalar_one_or_none() is not None

    async def record_event(self, event_id: str) -> None:
        self.db.add(SeenWebhookEvent(event_id=event_id, source="vapi"))
        await self.db.commit()
