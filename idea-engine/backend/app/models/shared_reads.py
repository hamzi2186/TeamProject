import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base, GUID


class LeadRead(Base):
    __tablename__ = "leads"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False)
    hubspot_contact_id: Mapped[str | None] = mapped_column(Text)
    first_name: Mapped[str | None] = mapped_column(Text)
    last_name: Mapped[str | None] = mapped_column(Text)
    display_name: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    website_url: Mapped[str | None] = mapped_column(Text)
    current_status: Mapped[str] = mapped_column(Text, default="NEW")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CampaignRead(Base):
    __tablename__ = "campaigns"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="DRAFT")
    execution_mode: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CampaignStepRead(Base):
    __tablename__ = "campaign_steps"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    campaign_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, default=1)
    parallel_group: Mapped[int | None] = mapped_column(Integer)
    delay_after_previous_seconds: Mapped[int | None] = mapped_column(BigInteger)


class ConversationRead(Base):
    __tablename__ = "conversations"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(GUID)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(GUID)
    channel: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="OPEN")
    outcome: Mapped[str | None] = mapped_column(Text)
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    concluded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CallRead(Base):
    __tablename__ = "calls"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(GUID)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False)
    lead_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False)
    direction: Mapped[str] = mapped_column(Text, default="OUTBOUND")
    from_number: Mapped[str | None] = mapped_column(Text)
    to_number: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="COMPLETED")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    transcript: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str | None] = mapped_column(Text)
    recording_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SmsMessageRead(Base):
    __tablename__ = "sms_messages"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(GUID)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False)
    lead_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False)
    direction: Mapped[str] = mapped_column(Text, default="OUTBOUND")
    from_number: Mapped[str | None] = mapped_column(Text)
    to_number: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, default="")
    delivery_status: Mapped[str | None] = mapped_column(Text)
    sent_or_received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class EmailRead(Base):
    __tablename__ = "emails"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(GUID)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False)
    lead_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False)
    direction: Mapped[str] = mapped_column(Text, default="OUTBOUND")
    from_address: Mapped[str | None] = mapped_column(Text)
    to_addresses: Mapped[Any | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    subject: Mapped[str | None] = mapped_column(Text)
    text_body: Mapped[str | None] = mapped_column(Text)
    delivery_status: Mapped[str | None] = mapped_column(Text)
    sent_or_received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LeadStatusHistoryRead(Base):
    __tablename__ = "lead_status_history"
    __table_args__ = {"extend_existing": True}

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False)
    lead_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(GUID)
    previous_status: Mapped[str | None] = mapped_column(Text)
    new_status: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
