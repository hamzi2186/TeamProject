from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class EmailDirection(StrEnum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class EmailOutcome(StrEnum):
    """The subset of the canonical lead outcomes (Master PRD section 41) an email turn can produce."""

    INTERESTED = "INTERESTED"
    NOT_INTERESTED = "NOT_INTERESTED"
    FOLLOW_UP_REQUIRED = "FOLLOW_UP_REQUIRED"
    NO_RESPONSE = "NO_RESPONSE"
    CONVERTED = "CONVERTED"
    DO_NOT_CONTACT = "DO_NOT_CONTACT"
    FAILED = "FAILED"


class AIEmailDecision(BaseModel):
    subject: str
    text_body: str
    should_continue: bool = True
    outcome: EmailOutcome = EmailOutcome.NO_RESPONSE
    reason: str = ""
    follow_up_at: datetime | None = None


class MailerConversation(BaseModel):
    conversation_id: str
    user_id: UUID
    lead_id: UUID
    campaign_id: UUID | None = None
    channel: str = "EMAIL"
    status: str = "WAITING_FOR_LEAD"
    subject: str | None = None
    provider: str = "resend"
    reply_to_token: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class EmailRecord(BaseModel):
    conversation_id: str | None = None
    user_id: UUID | None = None
    lead_id: UUID | None = None
    campaign_id: UUID | None = None
    direction: EmailDirection = EmailDirection.OUTBOUND
    from_address: str | None = None
    to_addresses: list[str] = Field(default_factory=list)
    subject: str | None = None
    text_body: str | None = None
    html_body: str | None = None
    provider: str = "resend"
    provider_email_id: str | None = None
    internet_message_id: str | None = None
    in_reply_to: str | None = None
    references_header: str | None = None
    delivery_status: str = "queued"
    provider_payload: dict[str, Any] = Field(default_factory=dict)
    sent_or_received_at: datetime | None = None
    reply_to_token: str | None = None


class WebhookEnvelope(BaseModel):
    provider: str = "resend"
    event_id: str | None = None
    event_type: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
