from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

EmailDirection = Literal["inbound", "outbound"]
EmailOutcome = Literal[
    "INTERESTED",
    "NOT_INTERESTED",
    "UNSUBSCRIBED",
    "FOLLOW_UP_LATER",
    "NO_RESPONSE",
    "FAILED",
]


class AIEmailDecision(BaseModel):
    subject: str
    text_body: str
    should_continue: bool = True
    outcome: EmailOutcome = "NO_RESPONSE"
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
    direction: EmailDirection = "outbound"
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
    timestamp: datetime | None = None
    reply_to_token: str | None = None


class WebhookEnvelope(BaseModel):
    provider: str = "resend"
    event_id: str | None = None
    event_type: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
