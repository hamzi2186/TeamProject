from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models.agent import AgentDocument, AgentKnowledgeChunk
from app.schemas.agent import AgentSearchResponse, AgentSearchResultItem
from app.services.tpi_client import TPIEmbeddingClient, create_tpi_embedding_client


class AgentRetrievalService:
    def __init__(
        self,
        db: AsyncSession,
        tpi_client: TPIEmbeddingClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.tpi = tpi_client or create_tpi_embedding_client()

    async def search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        module_filter: str | None = None,
        similarity_threshold: float | None = None,
    ) -> AgentSearchResponse:
        k = top_k or self.settings.default_top_k
        threshold = (
            similarity_threshold
            if similarity_threshold is not None
            else self.settings.default_similarity_threshold
        )

        clean_query = query.strip()
        if not clean_query:
            return AgentSearchResponse(query=query, module_filter=module_filter, total=0, items=[])

        # 1. Generate query embedding via TPI
        embedded = await self.tpi.query(
            clean_query,
            provider=self.settings.embedding_provider,
            model=self.settings.embedding_model,
            dimension=self.settings.embedding_dimension,
        )

        has_valid_embedding = (
            bool(embedded.embeddings)
            and len(embedded.embeddings[0]) == self.settings.embedding_dimension
        )
        if not has_valid_embedding:
            return AgentSearchResponse(
                query=query, module_filter=module_filter, total=0, items=[]
            )

        query_vector = embedded.embeddings[0]

        # 2. Query pgvector using cosine distance
        distance = AgentKnowledgeChunk.embedding.cosine_distance(query_vector)

        stmt = (
            select(AgentKnowledgeChunk, AgentDocument, distance.label("distance"))
            .join(AgentDocument, AgentDocument.id == AgentKnowledgeChunk.document_id)
            .where(
                AgentDocument.active == True,  # noqa: E712
                AgentKnowledgeChunk.embedding_dimension == self.settings.embedding_dimension,
            )
        )

        if module_filter:
            stmt = stmt.where(AgentKnowledgeChunk.module_key == module_filter.strip().casefold())

        if threshold is not None and threshold > 0.0:
            stmt = stmt.where((1.0 - distance) >= threshold)

        stmt = stmt.order_by(distance).limit(k)

        rows = (await self.db.execute(stmt)).all()

        items: list[AgentSearchResultItem] = []
        for chunk, doc, row_dist in rows:
            sim = max(-1.0, min(1.0, 1.0 - float(row_dist)))
            items.append(
                AgentSearchResultItem(
                    chunk_id=chunk.id,
                    document_id=doc.id,
                    module_key=chunk.module_key,
                    source_path=chunk.source_path,
                    file_name=doc.file_name,
                    title=doc.title,
                    header_path=chunk.header_path,
                    content=chunk.content,
                    similarity=round(sim, 4),
                    metadata=chunk.metadata_json or {},
                )
            )

        return AgentSearchResponse(
            query=query,
            module_filter=module_filter,
            total=len(items),
            items=items,
        )

