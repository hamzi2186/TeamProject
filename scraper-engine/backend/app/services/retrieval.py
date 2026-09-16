from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scraper import KnowledgeBase, KnowledgeChunk, WebPage
from app.schemas.scraper import SearchResponse, SearchResult
from app.services.tpi_embeddings import TPIEmbeddingClient


class KnowledgeBaseNotReadyError(RuntimeError):
    pass


class RetrievalDimensionError(RuntimeError):
    pass


class RetrievalService:
    def __init__(self, db: AsyncSession, embeddings: TPIEmbeddingClient) -> None:
        self._db = db
        self._embeddings = embeddings

    async def search(
        self,
        *,
        user_id: UUID,
        knowledge_base_id: UUID,
        query: str,
        top_k: int,
        minimum_similarity: float | None,
    ) -> SearchResponse:
        kb = await self._db.scalar(
            select(KnowledgeBase).where(
                KnowledgeBase.id == knowledge_base_id,
                KnowledgeBase.user_id == user_id,
                KnowledgeBase.kb_type == "CLIENT",
            )
        )
        if kb is None:
            raise LookupError("Knowledge base not found")
        if kb.status not in {"READY", "PARTIAL"}:
            raise KnowledgeBaseNotReadyError("Knowledge base is not ready")
        if not kb.embedding_provider or not kb.embedding_model or not kb.embedding_dimension:
            raise RetrievalDimensionError("Knowledge base embedding metadata is incomplete")
        embedded = await self._embeddings.query(
            query,
            provider=kb.embedding_provider,
            model=kb.embedding_model,
            dimension=kb.embedding_dimension,
        )
        actual_space = (embedded.provider, embedded.model, embedded.dimension)
        expected_space = (kb.embedding_provider, kb.embedding_model, kb.embedding_dimension)
        if actual_space != expected_space or len(embedded.embeddings[0]) != kb.embedding_dimension:
            raise RetrievalDimensionError(
                "Query embedding is incompatible with this knowledge base"
            )
        distance = KnowledgeChunk.embedding.cosine_distance(embedded.embeddings[0])
        statement = (
            select(KnowledgeChunk, WebPage.title, distance.label("distance"))
            .join(WebPage, WebPage.id == KnowledgeChunk.page_id)
            .where(
                KnowledgeChunk.user_id == user_id,
                KnowledgeChunk.knowledge_base_id == knowledge_base_id,
                KnowledgeChunk.embedding_provider == kb.embedding_provider,
                KnowledgeChunk.embedding_model == kb.embedding_model,
                KnowledgeChunk.embedding_dimension == kb.embedding_dimension,
            )
            .order_by(distance)
            .limit(top_k)
        )
        if minimum_similarity is not None:
            statement = statement.where((1 - distance) >= minimum_similarity)
        rows = (await self._db.execute(statement)).all()
        return SearchResponse(
            knowledge_base_id=kb.id,
            query=query,
            results=[
                SearchResult(
                    chunk_id=chunk.id,
                    knowledge_base_id=chunk.knowledge_base_id,
                    content=chunk.content,
                    source_url=chunk.source_url,
                    page_title=title,
                    chunk_index=chunk.chunk_index,
                    similarity=max(-1.0, min(1.0, 1.0 - float(row_distance))),
                    metadata=chunk.metadata_json,
                )
                for chunk, title, row_distance in rows
            ],
            embedding_provider=kb.embedding_provider,
            embedding_model=kb.embedding_model,
            embedding_dimension=kb.embedding_dimension,
        )
