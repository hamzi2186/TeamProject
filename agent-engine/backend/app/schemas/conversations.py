import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agent import AssistantGenerationInfo, AssistantSourceItem


class ConversationCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255, description="Optional conversation title")


class ConversationUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255, description="New conversation title")


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    sources: list[AssistantSourceItem] = Field(default_factory=list)
    generation: AssistantGenerationInfo | None = None
    created_at: datetime


class ConversationSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None = None
    created_at: datetime
    updated_at: datetime


class ConversationDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None = None
    created_at: datetime
    updated_at: datetime
    messages: list[MessageResponse] = Field(default_factory=list)


class ConversationMessageCreateRequest(BaseModel):
    content: str = Field(
        min_length=1,
        max_length=4000,
        description="User message or follow-up question",
    )
    top_k: int | None = Field(default=None, ge=1, le=50, description="Max chunks to retrieve")
    module_filter: str | None = Field(
        default=None, description="Optional module filter (e.g. 'scraper')"
    )
    similarity_threshold: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Minimum cosine similarity"
    )


class ConversationAskResponse(BaseModel):
    conversation_id: uuid.UUID
    user_message: MessageResponse
    assistant_message: MessageResponse

