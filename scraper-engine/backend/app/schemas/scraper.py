from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NormalizeRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


class NormalizeResponse(BaseModel):
    normalized_url: str
    normalized_key: str
    normalized_host: str


class IngestRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    lead_ids: list[UUID] = Field(default_factory=list, max_length=500)


class WebsiteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    original_url: str
    normalized_url: str
    normalized_key: str
    crawl_status: str
    last_crawled_at: datetime | None
    content_fingerprint: str | None
    created_at: datetime
    updated_at: datetime
    knowledge_base_id: UUID | None = None
    kb_status: str | None = None
    page_count: int = 0
    chunk_count: int = 0
    leads_using_kb: int = 0


class IngestResponse(BaseModel):
    website: WebsiteResponse
    knowledge_base_id: UUID
    job_id: UUID | None
    reused: bool


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    website_id: UUID
    knowledge_base_id: UUID
    status: str
    is_refresh: bool
    attempt_count: int
    pages_discovered: int
    pages_crawled: int
    pages_indexed: int
    chunks_generated: int
    error_code: str | None
    error_message: str | None
    partial_reason: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    website_id: UUID
    kb_type: str
    status: str
    embedding_provider: str | None
    embedding_model: str | None
    embedding_dimension: int | None
    page_count: int
    chunk_count: int
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class PageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    website_id: UUID
    url: str
    canonical_url: str
    title: str | None
    meta_description: str | None
    content_hash: str
    http_status: int
    content_type: str | None
    depth: int
    fetched_at: datetime


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=20_000)
    top_k: int = Field(default=6, ge=1, le=20)
    minimum_similarity: float | None = Field(default=None, ge=-1, le=1)

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Query must not be blank")
        return value


class InternalSearchRequest(SearchRequest):
    user_id: UUID
    knowledge_base_id: UUID


class SearchResult(BaseModel):
    chunk_id: UUID
    knowledge_base_id: UUID
    content: str
    source_url: str
    page_title: str | None
    chunk_index: int
    similarity: float
    metadata: dict


class SearchResponse(BaseModel):
    knowledge_base_id: UUID
    query: str
    results: list[SearchResult]
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
