import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Call(TimestampMixin, Base):
    """
    Calling Engine business-visible call record.
    PRD §17.6 — Call Persistence.
    user_id FK references app_users.id (shared platform table).
    lead_id FK references leads.id (shared platform table).
    """

    __tablename__ = "calls"
    __table_args__ = (
        Index("ix_calls_user_id", "user_id"),
        Index("ix_calls_lead_id", "lead_id"),
        Index("ix_calls_provider_call_id", "provider_call_id"),
        Index("ix_calls_campaign_id", "campaign_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # References shared app_users.id — FK constraint added in migration
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # References shared leads.id — FK added in migration when leads table exists
    lead_id: Mapped[str] = mapped_column(Text, nullable=False)

    # References shared conversations.id if available
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Optional campaign association
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Call direction: OUTBOUND | INBOUND
    direction: Mapped[str] = mapped_column(String(16), nullable=False)

    from_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_number: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Provider identity
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="vapi")
    provider_call_id: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)

    # Status: QUEUED | RINGING | IN_PROGRESS | COMPLETED | NO_ANSWER | FAILED | CANCELLED
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="QUEUED")

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Outcome: INTERESTED | NOT_INTERESTED | FOLLOW_UP_REQUIRED | NO_ANSWER |
    #          CONVERTED | DO_NOT_CONTACT | COMPLETED | FAILED
    outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)

    recording_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Normalized provider metadata (never raw provider secrets)
    provider_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class SeenWebhookEvent(Base):
    """
    Idempotency table for inbound webhook events.
    Prevents duplicate processing when TPI or Vapi retries the same event.
    """

    __tablename__ = "seen_webhook_events"
    __table_args__ = (Index("ix_seen_webhook_events_source", "source"),)

    # event_id is the provider-generated unique event identifier
    event_id: Mapped[str] = mapped_column(Text, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="vapi")
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
