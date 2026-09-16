import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SmsSendRequest(BaseModel):
    user_id: uuid.UUID
    to_number: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    body: str = Field(min_length=1, max_length=1600)


class SmsSendResponse(BaseModel):
    provider: Literal["twilio", "mock"]
    provider_message_id: str
    status: str
    from_number: str


class NormalizedInboundSms(BaseModel):
    event_id: str
    user_id: uuid.UUID
    provider_message_id: str
    from_number: str
    to_number: str
    body: str
    occurred_at: str
    raw_payload: dict


class NormalizedDeliveryStatus(BaseModel):
    event_id: str
    user_id: uuid.UUID
    provider_message_id: str
    status: Literal["QUEUED", "SENT", "DELIVERED", "UNDELIVERED", "FAILED"]
    error_code: str | None
    occurred_at: str
    raw_payload: dict


class MockSmsReplyRequest(BaseModel):
    user_id: uuid.UUID
    from_number: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    to_number: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    body: str = Field(min_length=1, max_length=1600)


class MockSmsMessage(BaseModel):
    provider_message_id: str
    user_id: uuid.UUID
    from_number: str
    to_number: str
    body: str
    status: Literal["DELIVERED"] = "DELIVERED"
    created_at: datetime
