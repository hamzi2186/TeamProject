from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    module_key: str | None = Field(
        default=None, description="Optional module filter (e.g. 'scraper')"
    )
    force: bool = Field(
        default=False, description="If True, re-indexes even if content hash matches"
    )


class IngestResultItem(BaseModel):
    source_path: str
    module_key: str
    status: str
    chunk_count: int
    title: str | None = None


class IngestResponse(BaseModel):
    scanned: int
    created: int
    updated: int
    unchanged: int
    deactivated: int
    chunks_indexed: int
    details: list[IngestResultItem] = Field(default_factory=list)


class AgentSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000, description="Semantic query text")
    top_k: int = Field(default=5, ge=1, le=50, description="Max number of chunks to return")
    module_filter: str | None = Field(
        default=None, description="Filter by module key (e.g. 'scraper')"
    )
    similarity_threshold: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Minimum cosine similarity"
    )


class AgentSearchResultItem(BaseModel):
    chunk_id: UUID
    document_id: UUID
    module_key: str
    source_path: str
    file_name: str
    title: str | None = None
    header_path: str | None = None
    content: str
    similarity: float
    metadata: dict = Field(default_factory=dict)


class AgentSearchResponse(BaseModel):
    query: str
    module_filter: str | None = None
    total: int
    items: list[AgentSearchResultItem]


class AgentDocumentSummary(BaseModel):
    id: UUID
    module_key: str
    source_path: str
    file_name: str
    title: str | None = None
    version: int
    chunk_count: int
    active: bool
    last_indexed_at: datetime | None = None


class AssistantAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000, description="User question")
    top_k: int | None = Field(default=None, ge=1, le=50, description="Max chunks to retrieve")
    module_filter: str | None = Field(
        default=None, description="Optional module filter (e.g. 'scraper')"
    )
    similarity_threshold: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Minimum cosine similarity"
    )


class AssistantSourceItem(BaseModel):
    module_key: str
    source_path: str
    header_path: str | None = None
    similarity: float


class AssistantGenerationInfo(BaseModel):
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None


class AssistantAskResponse(BaseModel):
    answer: str
    sources: list[AssistantSourceItem] = Field(default_factory=list)
    generation: AssistantGenerationInfo | None = None

