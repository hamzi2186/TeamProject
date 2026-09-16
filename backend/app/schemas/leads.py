from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LeadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    hubspot_contact_id: str
    first_name: str | None
    last_name: str | None
    display_name: str | None
    phone: str | None
    email: str | None
    website_url: str | None
    website_id: UUID | None
    current_status: str
    created_at: datetime
    updated_at: datetime


class LeadUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: str | None = None
    website_url: str | None = None
    current_status: str | None = None


class LeadKnowledgeBaseStatusResponse(BaseModel):
    has_website: bool
    website_url: str | None = None
    website_id: UUID | None = None
    knowledge_base_id: UUID | None = None
    status: str  # NOT_CREATED, QUEUED, CRAWLING, PROCESSING / EMBEDDING, READY, PARTIAL, FAILED
    page_count: int = 0
    chunk_count: int = 0
    last_indexed_at: datetime | None = None
    error_message: str | None = None


class LeadBuildKnowledgeBaseRequest(BaseModel):
    website_url: str | None = None


class LeadSearchKnowledgeBaseRequest(BaseModel):
    query: str
    top_k: int = 6


class LeadSearchResultItem(BaseModel):
    chunk_id: UUID
    content: str
    source_url: str
    page_title: str | None = None
    similarity: float


class LeadSearchKnowledgeBaseResponse(BaseModel):
    knowledge_base_id: UUID
    query: str
    results: list[LeadSearchResultItem]
