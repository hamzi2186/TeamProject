import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models.agent import AgentDocument, AgentKnowledgeChunk
from app.schemas.agent import IngestResponse, IngestResultItem
from app.services.chunking import MarkdownChunker
from app.services.discovery import DocumentDiscoveryService
from app.services.tpi_client import TPIEmbeddingClient, create_tpi_embedding_client


class AgentIngestionService:
    def __init__(
        self,
        db: AsyncSession,
        tpi_client: TPIEmbeddingClient | None = None,
        discovery_service: DocumentDiscoveryService | None = None,
        chunker: MarkdownChunker | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.db = db
        self.settings = settings or get_settings()
        self.tpi = tpi_client or create_tpi_embedding_client()
        self.discovery = discovery_service or DocumentDiscoveryService(self.settings.docs_root_path)
        self.chunker = chunker or MarkdownChunker()

    async def ingest(
        self,
        *,
        module_filter: str | None = None,
        force: bool = False,
    ) -> IngestResponse:
        # 1. Discover docs from filesystem
        discovered_docs = self.discovery.discover(module_filter=module_filter)

        # 2. Fetch existing documents from database
        query = select(AgentDocument)
        if module_filter:
            query = query.where(AgentDocument.module_key == module_filter.strip().casefold())
        result = await self.db.execute(query)
        existing_docs: dict[str, AgentDocument] = {
            doc.source_path: doc for doc in result.scalars().all()
        }

        discovered_paths = {doc.source_path for doc in discovered_docs}
        details: list[IngestResultItem] = []

        scanned = len(discovered_docs)
        created_count = 0
        updated_count = 0
        unchanged_count = 0
        deactivated_count = 0
        total_chunks_indexed = 0

        # 3. Process each discovered document
        for disc in discovered_docs:
            existing = existing_docs.get(disc.source_path)

            is_unchanged = (
                existing
                and existing.active
                and existing.content_hash == disc.content_hash
                and not force
            )
            if is_unchanged:
                unchanged_count += 1
                details.append(
                    IngestResultItem(
                        source_path=disc.source_path,
                        module_key=disc.module_key,
                        status="unchanged",
                        chunk_count=existing.chunk_count,
                        title=existing.title,
                    )
                )
                continue

            # Document is new or changed
            chunks = self.chunker.chunk(disc.raw_content)
            now = datetime.now(UTC)

            if chunks:
                texts = [c.content for c in chunks]
                embed_res = await self.tpi.passages_batched(
                    texts,
                    batch_size=self.settings.embedding_batch_size,
                    provider=self.settings.embedding_provider,
                    model=self.settings.embedding_model,
                    dimension=self.settings.embedding_dimension,
                )
            else:
                embed_res = None

            if existing:
                # Update existing document
                doc_id = existing.id
                existing.version += 1
                existing.content_hash = disc.content_hash
                existing.chunk_count = len(chunks)
                existing.title = disc.title
                existing.file_name = disc.file_name
                existing.active = True
                existing.last_indexed_at = now
                existing.updated_at = now

                # Delete existing chunks
                await self.db.execute(
                    delete(AgentKnowledgeChunk).where(AgentKnowledgeChunk.document_id == doc_id)
                )
                status = "updated"
                updated_count += 1
            else:
                # Create new document
                doc_id = uuid.uuid4()
                new_doc = AgentDocument(
                    id=doc_id,
                    module_key=disc.module_key,
                    source_path=disc.source_path,
                    file_name=disc.file_name,
                    title=disc.title,
                    content_hash=disc.content_hash,
                    version=1,
                    chunk_count=len(chunks),
                    active=True,
                    last_indexed_at=now,
                )
                self.db.add(new_doc)
                status = "created"
                created_count += 1

            # Insert new chunks
            if chunks and embed_res:
                for chunk, vector in zip(chunks, embed_res.embeddings, strict=False):
                    new_chunk = AgentKnowledgeChunk(
                        id=uuid.uuid4(),
                        document_id=doc_id,
                        module_key=disc.module_key,
                        source_path=disc.source_path,
                        chunk_index=chunk.chunk_index,
                        header_path=chunk.header_path,
                        content=chunk.content,
                        content_hash=chunk.content_hash,
                        embedding_provider=embed_res.provider,
                        embedding_model=embed_res.model,
                        embedding_dimension=embed_res.dimension,
                        embedding=vector,
                        metadata_json=chunk.metadata,
                    )
                    self.db.add(new_chunk)
                total_chunks_indexed += len(chunks)

            details.append(
                IngestResultItem(
                    source_path=disc.source_path,
                    module_key=disc.module_key,
                    status=status,
                    chunk_count=len(chunks),
                    title=disc.title,
                )
            )

        # 4. Detect deleted documents (in DB as active, but removed from disk)
        for path, doc in existing_docs.items():
            if doc.active and path not in discovered_paths:
                doc.active = False
                doc.chunk_count = 0
                now = datetime.now(UTC)
                doc.updated_at = now
                await self.db.execute(
                    delete(AgentKnowledgeChunk).where(AgentKnowledgeChunk.document_id == doc.id)
                )
                deactivated_count += 1
                details.append(
                    IngestResultItem(
                        source_path=doc.source_path,
                        module_key=doc.module_key,
                        status="deactivated",
                        chunk_count=0,
                        title=doc.title,
                    )
                )

        await self.db.commit()

        return IngestResponse(
            scanned=scanned,
            created=created_count,
            updated=updated_count,
            unchanged=unchanged_count,
            deactivated=deactivated_count,
            chunks_indexed=total_chunks_indexed,
            details=details,
        )

