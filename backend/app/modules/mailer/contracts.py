from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


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


def _single_line(value: str) -> str:
    """Collapse whitespace so a model-written subject can never inject an extra mail header."""
    return re.sub(r"\s+", " ", value).strip()


class GeneratedEmail(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    text_body: str = Field(min_length=1, max_length=6000)

    @field_validator("subject", mode="before")
    @classmethod
    def _clean_subject(cls, value: Any) -> Any:
        return _single_line(value) if isinstance(value, str) else value

    @field_validator("text_body", mode="before")
    @classmethod
    def _clean_body(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class AIEmailDecision(BaseModel):
    subject: str = Field(default="", max_length=200)
    text_body: str = Field(default="", max_length=6000)
    should_continue: bool = True
    outcome: EmailOutcome = EmailOutcome.NO_RESPONSE
    reason: str = Field(default="", max_length=2000)
    follow_up_at: datetime | None = None

    @field_validator("subject", mode="before")
    @classmethod
    def _clean_subject(cls, value: Any) -> Any:
        return _single_line(value) if isinstance(value, str) else value

    @field_validator("text_body", mode="before")
    @classmethod
    def _clean_body(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_validator("follow_up_at")
    @classmethod
    def _aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


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


class InboundEmailEvent(BaseModel):
    """A reply, already verified and normalized by TPI. Nothing here is provider-specific."""

    provider: str = "resend"
    event_id: str = Field(min_length=1, max_length=160)
    provider_email_id: str | None = None
    from_address: str
    to_addresses: list[str] = Field(default_factory=list)
    subject: str | None = None
    text_body: str | None = None
    html_body: str | None = None
    internet_message_id: str | None = None
    in_reply_to: str | None = None
    references_header: str | None = None
    received_at: datetime | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class DeliveryEvent(BaseModel):
    """A delivery report for an email we sent, normalized by TPI.

    `status` is one of sent, delivered, delayed, bounced, failed, complained. A bounce is
    treated as permanent unless the provider says otherwise.
    """

    provider: str = "resend"
    event_id: str = Field(min_length=1, max_length=160)
    provider_email_id: str = Field(min_length=1)
    status: str
    permanent: bool = True
    occurred_at: datetime | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


@dataclass(frozen=True)
class SentEmail:
    provider: str
    provider_email_id: str | None
    from_address: str | None = None
    internet_message_id: str | None = None
    status: str = "sent"
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KBPassage:
    content: str
    source_url: str
    title: str | None = None
    similarity: float = 0.0


class EmailProvider(Protocol):
    """Sends one email. The implementation lives behind TPI; the engine never sees a vendor."""

    async def send_email(
        self,
        *,
        to: str,
        subject: str,
        text_body: str,
        reply_to: str,
        in_reply_to: str | None = None,
        references: str | None = None,
        idempotency_key: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> SentEmail: ...


class ReplyDispatcher(Protocol):
    """Hands a stored reply to a worker, which runs `MailerService.reply_to_inbound`."""

    async def enqueue_reply(self, *, conversation_id: UUID, inbound_email_id: UUID) -> None: ...


class LLM(Protocol):
    async def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 900,
    ) -> str: ...


class ClientKnowledgeBase(Protocol):
    async def search(
        self, *, user_id: UUID, website_id: UUID | None, query: str, top_k: int
    ) -> list[KBPassage]: ...
