import uuid
from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.models.agent import AgentDocument, AgentKnowledgeChunk
from app.services.retrieval import AgentRetrievalService
from app.services.tpi_client import EmbeddingResult, TPIEmbeddingClient


class FakeRowResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


@pytest.mark.asyncio
async def test_retrieval_service_searches_and_ranks():
    db = AsyncMock()
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()

    fake_doc = AgentDocument(
        id=doc_id,
        module_key="scraper",
        source_path="scraper/overview.md",
        file_name="overview.md",
        title="Overview",
        content_hash="h1",
        version=1,
        chunk_count=1,
        active=True,
    )
    fake_chunk = AgentKnowledgeChunk(
        id=chunk_id,
        document_id=doc_id,
        module_key="scraper",
        source_path="scraper/overview.md",
        chunk_index=0,
        header_path="Overview",
        content="Overview chunk content",
        content_hash="ch1",
        embedding_provider="agent-jina",
        embedding_model="jina-embeddings-v3",
        embedding_dimension=1024,
        embedding=[0.1] * 1024,
        metadata_json={"word_count": 3},
    )

    # Cosine distance = 0.2 -> similarity = 1 - 0.2 = 0.8
    db.execute.return_value = FakeRowResult([(fake_chunk, fake_doc, 0.2)])

    tpi = AsyncMock(spec=TPIEmbeddingClient)
    tpi.query.return_value = EmbeddingResult(
        embeddings=[[0.1] * 1024],
        provider="agent-jina",
        model="jina-embeddings-v3",
        dimension=1024,
    )

    settings = Settings(
        database_url="postgresql://test:test@localhost/test",
        tpi_internal_service_token="test",
        agent_internal_service_token="test",
        embedding_dimension=1024,
    )

    service = AgentRetrievalService(db=db, tpi_client=tpi, settings=settings)
    res = await service.search("How does scraper work?", top_k=5, module_filter="scraper")

    assert res.total == 1
    assert len(res.items) == 1
    item = res.items[0]
    assert item.chunk_id == chunk_id
    assert item.document_id == doc_id
    assert item.module_key == "scraper"
    assert item.title == "Overview"
    assert item.similarity == 0.8
    assert item.metadata == {"word_count": 3}
    assert tpi.query.call_count == 1


@pytest.mark.asyncio
async def test_retrieval_empty_query():
    db = AsyncMock()
    tpi = AsyncMock(spec=TPIEmbeddingClient)
    settings = Settings(
        database_url="postgresql://test:test@localhost/test",
        tpi_internal_service_token="test",
        agent_internal_service_token="test",
    )

    service = AgentRetrievalService(db=db, tpi_client=tpi, settings=settings)
    res = await service.search("   ")

    assert res.total == 0
    assert len(res.items) == 0
    assert tpi.query.call_count == 0

