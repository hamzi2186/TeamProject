from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class CallDirection(StrEnum):
    OUTBOUND = "OUTBOUND"
    INBOUND = "INBOUND"


class CallStatus(StrEnum):
    QUEUED = "QUEUED"
    RINGING = "RINGING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    NO_ANSWER = "NO_ANSWER"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class CallOutcome(StrEnum):
    INTERESTED = "INTERESTED"
    NOT_INTERESTED = "NOT_INTERESTED"
    FOLLOW_UP_REQUIRED = "FOLLOW_UP_REQUIRED"
    NO_ANSWER = "NO_ANSWER"
    CONVERTED = "CONVERTED"
    DO_NOT_CONTACT = "DO_NOT_CONTACT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class CallRecord(BaseModel):
    call_id: str
    conversation_id: str | None
    user_id: str
    lead_id: str
    direction: CallDirection
    from_number: str | None = None
    to_number: str | None = None
    provider: str
    provider_call_id: str | None = None
    status: CallStatus
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: int | None = None
    transcript: str | None = None
    summary: str | None = None
    outcome: CallOutcome | None = None
    recording_url: str | None = None
    provider_payload: dict[str, Any] = Field(default_factory=dict)
