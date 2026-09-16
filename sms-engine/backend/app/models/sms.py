import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

SCHEMA = "sms_engine"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SmsConversation(TimestampMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('OPEN','CONCLUDED','UNRESOLVED')", name="status_valid"
        ),
        CheckConstraint(
            "outcome IS NULL OR outcome IN "
            "('INTERESTED','CONVERTED','FOLLOW_UP_REQUESTED','NOT_INTERESTED',"
            "'WRONG_NUMBER','DO_NOT_CONTACT','NO_RESPONSE')",
            name="outcome_valid",
        ),
        UniqueConstraint("user_id", "campaign_id", "lead_id", name="conversation_target"),
        Index("ix_sms_conversations_user_status_updated", "user_id", "status", "updated_at"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    contact_name: Mapped[str] = mapped_column(Text, nullable=False, default="Unknown contact")
    from_number: Mapped[str] = mapped_column(String(32), nullable=False)
    to_number: Mapped[str] = mapped_column(String(32), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="OPEN")
    outcome: Mapped[str | None] = mapped_column(String(32))
    message_template: Mapped[str] = mapped_column(Text, nullable=False, default="")
    campaign_objective: Mapped[str] = mapped_column(Text, nullable=False, default="")
    knowledge_context: Mapped[str] = mapped_column(Text, nullable=False, default="")
    agent_turn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_agent_turns: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    concluded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class SmsMessage(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("direction IN ('INBOUND','OUTBOUND')", name="direction_valid"),
        CheckConstraint(
            "delivery_status IN ('QUEUED','SENT','DELIVERED','UNDELIVERED','FAILED','RECEIVED')",
            name="delivery_status_valid",
        ),
        UniqueConstraint("provider", "provider_message_id", name="provider_message"),
        Index("ix_sms_messages_conversation_occurred", "conversation_id", "occurred_at"),
        Index("ix_sms_messages_user_lead", "user_id", "lead_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    direction: Mapped[str] = mapped_column(String(12), nullable=False)
    from_number: Mapped[str] = mapped_column(String(32), nullable=False)
    to_number: Mapped[str] = mapped_column(String(32), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="twilio")
    provider_message_id: Mapped[str | None] = mapped_column(String(128))
    delivery_status: Mapped[str] = mapped_column(String(24), nullable=False)
    provider_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SmsConsent(Base):
    __tablename__ = "consents"
    __table_args__ = (
        CheckConstraint("status IN ('UNKNOWN','CONSENTED','OPTED_OUT')", name="status_valid"),
        UniqueConstraint("user_id", "phone_number", name="user_phone"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="UNKNOWN")
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opted_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SmsProviderEvent(Base):
    __tablename__ = "provider_events"
    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="provider_event"),
        Index("ix_sms_provider_events_user_received", "user_id", "received_at"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    event_id: Mapped[str] = mapped_column(String(160), nullable=False)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
