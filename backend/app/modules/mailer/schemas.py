from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiError(BaseModel):
    code: str
    message: str
    details: dict = Field(default_factory=dict)


class Envelope(BaseModel, Generic[T]):
    """The common response shape from Master PRD 23, the same one the Calling API returns."""

    success: bool = True
    data: T | None = None
    error: ApiError | None = None
    request_id: str


class MailerMetrics(BaseModel):
    conversations: int = 0
    emails_sent: int = 0
    delivered: int = 0
    replies: int = 0
    bounced: int = 0
    interested: int = 0


class LeadSummary(BaseModel):
    id: UUID
    name: str | None = None
    email: str | None = None
    website_url: str | None = None
    current_status: str | None = None


class ConversationSummary(BaseModel):
    id: UUID
    lead_id: UUID
    lead_name: str | None = None
    lead_email: str | None = None
    campaign_id: UUID | None = None
    subject: str | None = None
    status: str | None = None
    outcome: str | None = None
    turn_count: int = 0
    email_count: int = 0
    reply_count: int = 0
    last_direction: str | None = None
    last_activity_at: datetime | None = None
    delivery_status: str | None = None
    opened_at: datetime | None = None
    updated_at: datetime | None = None


class ConversationList(BaseModel):
    items: list[ConversationSummary]
    total: int
    limit: int
    offset: int
    metrics: MailerMetrics


class EmailMessage(BaseModel):
    """One email as the dashboard shows it. Text only: a stranger's HTML is never sent to the
    browser, and provider payloads and ids stay on the server."""

    id: UUID
    direction: str
    from_address: str | None = None
    to_addresses: list[str] = Field(default_factory=list)
    subject: str | None = None
    text_body: str | None = None
    delivery_status: str | None = None
    sent_or_received_at: datetime | None = None


class ConversationDetail(BaseModel):
    id: UUID
    status: str | None = None
    outcome: str | None = None
    turn_count: int = 0
    campaign_id: UUID | None = None
    opened_at: datetime | None = None
    concluded_at: datetime | None = None
    updated_at: datetime | None = None
    lead: LeadSummary | None = None
    emails: list[EmailMessage]
