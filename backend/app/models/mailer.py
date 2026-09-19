"""ORM mappings for the shared tables the Mailer Engine reads and writes.

`emails`, `conversations` and `lead_status_history` already exist in the shared database
(Master PRD 24.12, 24.14, 24.16) but no migration in `backend/alembic/versions/` creates them.
These classes therefore live on their own metadata instead of the root `Base`: Alembic
autogenerate targets `Base.metadata`, so registering them there would make the next
`--autogenerate` propose `CREATE TABLE` for tables that already exist.

Cross-table foreign keys are deliberately left out of the mappings (the database enforces them).
`conversations` is shared by every channel, so mailer queries must always filter on
`EMAIL_CHANNEL`.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMAIL_CHANNEL = "EMAIL"

_JSON = JSON().with_variant(JSONB, "postgresql")


def _now() -> datetime:
    return datetime.now(UTC)


class MailerBase(DeclarativeBase):
    pass


class EmailConversation(MailerBase):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    lead_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    channel: Mapped[str | None] = mapped_column(Text, default=EMAIL_CHANNEL)
    status: Mapped[str | None] = mapped_column(Text, default="OPEN")
    provider_thread_id: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str | None] = mapped_column(Text)
    turn_count: Mapped[int | None] = mapped_column(Integer, default=0)
    opened_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=_now
    )
    concluded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=_now
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=_now, onupdate=_now
    )


class Email(MailerBase):
    __tablename__ = "emails"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    lead_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    from_address: Mapped[str | None] = mapped_column(Text)
    to_addresses: Mapped[list[str] | None] = mapped_column(_JSON, default=list)
    subject: Mapped[str | None] = mapped_column(Text)
    text_body: Mapped[str | None] = mapped_column(Text)
    html_body: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(Text)
    provider_email_id: Mapped[str | None] = mapped_column(Text)
    internet_message_id: Mapped[str | None] = mapped_column(Text)
    in_reply_to: Mapped[str | None] = mapped_column(Text)
    references_header: Mapped[str | None] = mapped_column(Text)
    delivery_status: Mapped[str | None] = mapped_column(Text)
    provider_payload: Mapped[dict[str, Any] | None] = mapped_column(_JSON, default=dict)
    sent_or_received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=_now
    )
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=_now
    )


class LeadStatusHistory(MailerBase):
    __tablename__ = "lead_status_history"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    lead_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    previous_status: Mapped[str | None] = mapped_column(Text)
    new_status: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=_now
    )
