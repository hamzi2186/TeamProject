import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Outcome = Literal[
    "INTERESTED",
    "CONVERTED",
    "FOLLOW_UP_REQUESTED",
    "NOT_INTERESTED",
    "WRONG_NUMBER",
    "DO_NOT_CONTACT",
    "NO_RESPONSE",
]


class ConversationCreate(BaseModel):
    campaign_id: uuid.UUID
    lead_id: uuid.UUID
    contact_name: str = Field(min_length=1, max_length=200)
    from_number: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    to_number: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    timezone: str = "America/New_York"
    message_template: str = Field(min_length=1, max_length=1200)
    campaign_objective: str = Field(min_length=1, max_length=2000)
    knowledge_context: str = Field(default="", max_length=20_000)
    consent_source: str = Field(min_length=1, max_length=64)
    consented: bool = False
    max_agent_turns: int = Field(default=8, ge=1, le=30)


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    campaign_id: uuid.UUID | None
    lead_id: uuid.UUID | None
    contact_name: str
    from_number: str
    to_number: str
    timezone: str
    status: str
    outcome: Outcome | None
    message_template: str
    campaign_objective: str
    knowledge_context: str
    agent_turn_count: int
    max_agent_turns: int
    opened_at: datetime
    concluded_at: datetime | None
    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    direction: str
    from_number: str
    to_number: str
    body: str
    provider: str
    provider_message_id: str | None
    delivery_status: str
    occurred_at: datetime


class ConversationDetail(ConversationRead):
    messages: list[MessageRead]


class StartConversationRequest(BaseModel):
    pass


class MockReplyRequest(BaseModel):
    body: str = Field(min_length=1, max_length=1600)


class BulkLead(BaseModel):
    lead_id: uuid.UUID
    first_name: str = Field(min_length=1, max_length=100)
    contact_name: str = Field(min_length=1, max_length=200)
    phone_number: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    timezone: str = Field(min_length=1, max_length=64)
    consented: bool
    consent_source: str = Field(min_length=1, max_length=64)


class BulkCampaignCreate(BaseModel):
    campaign_id: uuid.UUID
    from_number: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    message_template: str = Field(min_length=1, max_length=1200)
    campaign_objective: str = Field(min_length=1, max_length=2000)
    knowledge_context: str = Field(default="", max_length=20_000)
    max_agent_turns: int = Field(default=8, ge=1, le=30)
    start_immediately: bool = True
    leads: list[BulkLead] = Field(min_length=1, max_length=500)


class BulkCampaignSkipped(BaseModel):
    lead_id: uuid.UUID
    reason: str


class BulkCampaignResult(BaseModel):
    created: list[uuid.UUID]
    queued: list[uuid.UUID]
    skipped: list[BulkCampaignSkipped]


class InboundSmsEvent(BaseModel):
    provider: Literal["twilio", "mock"] = "twilio"
    event_id: str = Field(min_length=1, max_length=160)
    user_id: uuid.UUID
    provider_message_id: str = Field(min_length=1, max_length=128)
    from_number: str
    to_number: str
    body: str = Field(max_length=3200)
    occurred_at: datetime
    raw_payload: dict = Field(default_factory=dict)


class DeliveryStatusEvent(BaseModel):
    provider: Literal["twilio", "mock"] = "twilio"
    event_id: str = Field(min_length=1, max_length=160)
    user_id: uuid.UUID
    provider_message_id: str = Field(min_length=1, max_length=128)
    status: Literal["QUEUED", "SENT", "DELIVERED", "UNDELIVERED", "FAILED"]
    error_code: str | None = None
    occurred_at: datetime
    raw_payload: dict = Field(default_factory=dict)


class InternalEventResponse(BaseModel):
    accepted: bool
    duplicate: bool = False
    conversation_id: uuid.UUID | None = None
