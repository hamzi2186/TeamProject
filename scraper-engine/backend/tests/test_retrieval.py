from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.retrieval import RetrievalDimensionError, RetrievalService
from app.services.tpi_embeddings import EmbeddingResult


class FakeScalars:
    def all(self):
        return []


class FakeExecuteResult:
    def all(self):
        return []


class FakeDB:
    def __init__(self, kb):
        self.kb = kb
        self.statement = None

    async def scalar(self, statement):
        self.statement = statement
        return self.kb

    async def execute(self, statement):
        self.statement = statement
        return FakeExecuteResult()


class FakeEmbeddings:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def query(self, text, **space):
        self.calls.append((text, space))
        return self.result


def ready_kb():
    return SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        status="READY",
        kb_type="CLIENT",
        embedding_provider="jina",
        embedding_model="jina-embeddings-v3",
        embedding_dimension=1024,
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_retrieval_uses_kb_embedding_space_and_scoped_sql():
    kb = ready_kb()
    embeddings = FakeEmbeddings(
        EmbeddingResult(
            embeddings=[
                [0.0] * 1024,
            ],
            provider="jina",
            model="jina-embeddings-v3",
            dimension=1024,
        )
    )
    db = FakeDB(kb)
    response = await RetrievalService(db, embeddings).search(
        user_id=kb.user_id,
        knowledge_base_id=kb.id,
        query="services",
        top_k=6,
        minimum_similarity=None,
    )
    assert response.results == []
    assert embeddings.calls[0][1] == {
        "provider": "jina",
        "model": "jina-embeddings-v3",
        "dimension": 1024,
    }
    sql = str(db.statement)
    assert "kb_chunks.user_id" in sql
    assert "kb_chunks.knowledge_base_id" in sql
    assert "kb_chunks.embedding_provider" in sql


@pytest.mark.asyncio
async def test_cross_tenant_missing_kb_is_denied_before_vector_search():
    db = FakeDB(None)
    embeddings = FakeEmbeddings(None)
    with pytest.raises(LookupError):
        await RetrievalService(db, embeddings).search(
            user_id=uuid4(),
            knowledge_base_id=uuid4(),
            query="private data",
            top_k=6,
            minimum_similarity=None,
        )
    assert embeddings.calls == []


@pytest.mark.asyncio
async def test_query_dimension_mismatch_is_rejected():
    kb = ready_kb()
    embeddings = FakeEmbeddings(
        EmbeddingResult(
            embeddings=[[0.0] * 3],
            provider="jina",
            model="jina-embeddings-v3",
            dimension=3,
        )
    )
    with pytest.raises(RetrievalDimensionError):
        await RetrievalService(FakeDB(kb), embeddings).search(
            user_id=kb.user_id,
            knowledge_base_id=kb.id,
            query="services",
            top_k=6,
            minimum_similarity=None,
        )
