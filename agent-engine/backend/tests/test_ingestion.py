import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import Settings
from app.models.agent import AgentDocument
from app.services.chunking import DocumentChunk, MarkdownChunker
from app.services.discovery import DiscoveredDocument, DocumentDiscoveryService
from app.services.ingestion import AgentIngestionService
from app.services.tpi_client import EmbeddingResult, TPIEmbeddingClient


class FakeScalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return FakeScalars(self._items)


@pytest.mark.asyncio
async def test_ingestion_creates_new_documents():
    db = AsyncMock()
    db.add = MagicMock()
    # No existing documents in DB
    db.execute.return_value = FakeResult([])

    tpi = AsyncMock(spec=TPIEmbeddingClient)
    tpi.passages_batched.return_value = EmbeddingResult(
        embeddings=[[0.1] * 1024, [0.2] * 1024],
        provider="agent-jina",
        model="jina-embeddings-v3",
        dimension=1024,
    )

    discovery = MagicMock(spec=DocumentDiscoveryService)
    discovery.discover.return_value = [
        DiscoveredDocument(
            module_key="scraper",
            source_path="scraper/overview.md",
            file_name="overview.md",
            absolute_path="/docs/scraper/overview.md",
            title="Overview",
            raw_content="# Overview\n\nContent here.",
            content_hash="hash-1",
        )
    ]

    chunker = MagicMock(spec=MarkdownChunker)
    chunker.chunk.return_value = [
        DocumentChunk(
            chunk_index=0,
            header_path="Overview",
            content="Chunk 1",
            content_hash="chash-1",
        ),
        DocumentChunk(
            chunk_index=1,
            header_path="Overview",
            content="Chunk 2",
            content_hash="chash-2",
        ),
    ]

    settings = Settings(
        database_url="postgresql://test:test@localhost/test",
        tpi_internal_service_token="test",
        agent_internal_service_token="test",
        embedding_batch_size=32,
        embedding_provider="jina",
        embedding_model="jina-embeddings-v3",
        embedding_dimension=1024,
    )

    service = AgentIngestionService(
        db=db,
        tpi_client=tpi,
        discovery_service=discovery,
        chunker=chunker,
        settings=settings,
    )

    resp = await service.ingest()

    assert resp.scanned == 1
    assert resp.created == 1
    assert resp.updated == 0
    assert resp.unchanged == 0
    assert resp.deactivated == 0
    assert resp.chunks_indexed == 2
    assert tpi.passages_batched.call_count == 1
    assert db.commit.call_count == 1


@pytest.mark.asyncio
async def test_ingestion_skips_unchanged_document():
    db = AsyncMock()
    existing_doc = AgentDocument(
        id=uuid.uuid4(),
        module_key="scraper",
        source_path="scraper/overview.md",
        file_name="overview.md",
        title="Overview",
        content_hash="hash-matching",
        version=1,
        chunk_count=2,
        active=True,
    )
    db.execute.return_value = FakeResult([existing_doc])

    tpi = AsyncMock(spec=TPIEmbeddingClient)
    discovery = MagicMock(spec=DocumentDiscoveryService)
    discovery.discover.return_value = [
        DiscoveredDocument(
            module_key="scraper",
            source_path="scraper/overview.md",
            file_name="overview.md",
            absolute_path="/docs/scraper/overview.md",
            title="Overview",
            raw_content="# Overview\n\nContent here.",
            content_hash="hash-matching",
        )
    ]
    chunker = MagicMock(spec=MarkdownChunker)

    settings = Settings(
        database_url="postgresql://test:test@localhost/test",
        tpi_internal_service_token="test",
        agent_internal_service_token="test",
    )

    service = AgentIngestionService(
        db=db,
        tpi_client=tpi,
        discovery_service=discovery,
        chunker=chunker,
        settings=settings,
    )

    resp = await service.ingest()

    assert resp.scanned == 1
    assert resp.created == 0
    assert resp.updated == 0
    assert resp.unchanged == 1
    assert resp.chunks_indexed == 0
    # ZERO embedding calls when unchanged!
    assert tpi.passages_batched.call_count == 0


@pytest.mark.asyncio
async def test_ingestion_deactivates_deleted_document():
    db = AsyncMock()
    existing_doc = AgentDocument(
        id=uuid.uuid4(),
        module_key="scraper",
        source_path="scraper/deleted.md",
        file_name="deleted.md",
        title="Deleted",
        content_hash="hash-old",
        version=1,
        chunk_count=1,
        active=True,
    )
    db.execute.return_value = FakeResult([existing_doc])

    tpi = AsyncMock(spec=TPIEmbeddingClient)
    discovery = MagicMock(spec=DocumentDiscoveryService)
    # File is gone from disk
    discovery.discover.return_value = []
    chunker = MagicMock(spec=MarkdownChunker)

    settings = Settings(
        database_url="postgresql://test:test@localhost/test",
        tpi_internal_service_token="test",
        agent_internal_service_token="test",
    )

    service = AgentIngestionService(
        db=db,
        tpi_client=tpi,
        discovery_service=discovery,
        chunker=chunker,
        settings=settings,
    )

    resp = await service.ingest()

    assert resp.scanned == 0
    assert resp.created == 0
    assert resp.updated == 0
    assert resp.unchanged == 0
    assert resp.deactivated == 1
    assert existing_doc.active is False
    assert existing_doc.chunk_count == 0
