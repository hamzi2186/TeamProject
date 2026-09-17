import hashlib
import uuid
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.scraper import KnowledgeBase, KnowledgeChunk, ScrapeJob, WebPage, Website
from app.repositories.scraper import ScraperRepository
from app.services.chunking import DeterministicChunker
from app.services.crawler import CrawlError, SafeHTTPFetcher, WebsiteCrawler
from app.services.tpi_embeddings import TPIEmbeddingError, create_tpi_embedding_client
from app.services.urls import URLValidationError


class RetryableIndexingError(RuntimeError):
    pass


@dataclass(frozen=True)
class PendingChunk:
    page: WebPage
    index: int
    content: str
    content_hash: str
    token_count: int


async def process_scrape_job(job_id: UUID) -> None:
    settings = get_settings()
    previous_ready = False
    fetcher: SafeHTTPFetcher | None = None
    tpi: TPIEmbeddingClient | None = None
    try:
        async with SessionLocal() as db:
            job = await db.scalar(select(ScrapeJob).where(ScrapeJob.id == job_id).with_for_update())
            if job is None or job.status in {"COMPLETED", "PARTIAL"}:
                return
            if job.status == "RUNNING":
                return
            website = await db.get(Website, job.website_id)
            kb = await db.get(KnowledgeBase, job.knowledge_base_id)
            if website is None or kb is None:
                return
            previous_ready = kb.status in {"READY", "PARTIAL", "REFRESHING"} and kb.chunk_count > 0
            job.status = "RUNNING"
            job.attempt_count += 1
            job.started_at = func.now()
            job.error_code = None
            job.error_message = None
            website.crawl_status = "CRAWLING"
            kb.status = "CRAWLING"
            await db.commit()

        fetcher = SafeHTTPFetcher(
            timeout_seconds=settings.crawl_request_timeout_seconds,
            user_agent=settings.crawl_user_agent,
            max_redirects=settings.crawl_max_redirects,
        )

        async def persist_crawl_progress(
            pages_discovered: int, pages_processed: int, _pages_succeeded: int
        ) -> None:
            async with SessionLocal() as progress_db:
                progress_job = await progress_db.get(ScrapeJob, job_id)
                if progress_job is None or progress_job.status != "RUNNING":
                    return
                progress_job.pages_discovered = pages_discovered
                progress_job.pages_crawled = pages_processed
                await progress_db.commit()

        crawler = WebsiteCrawler(
            fetcher=fetcher,
            max_pages=settings.crawl_max_pages,
            max_depth=settings.crawl_max_depth,
            minimum_text_characters=settings.minimum_page_text_characters,
            enable_playwright_fallback=settings.enable_playwright_fallback,
            progress_callback=persist_crawl_progress,
        )
        tpi = create_tpi_embedding_client()
        async with SessionLocal() as db:
            job = await db.get(ScrapeJob, job_id)
            website = await db.get(Website, job.website_id) if job else None
            if job is None or website is None:
                return
            seed_url = website.normalized_url
        crawl = await crawler.crawl(seed_url)
        async with SessionLocal() as db:
            job = await db.get(ScrapeJob, job_id)
            kb = await db.get(KnowledgeBase, job.knowledge_base_id)
            job.pages_discovered = crawl.discovered_count
            job.pages_crawled = crawl.processed_count
            kb.status = "PROCESSING"
            await db.commit()

        chunker = DeterministicChunker(
            max_tokens=settings.chunk_max_tokens,
            overlap_tokens=settings.chunk_overlap_tokens,
        )
        pages: list[WebPage] = []
        pending: list[PendingChunk] = []
        async with SessionLocal() as db:
            job = await db.get(ScrapeJob, job_id)
            if job is None:
                return
            for crawled in crawl.pages:
                page = WebPage(
                    id=uuid.uuid4(),
                    user_id=job.user_id,
                    website_id=job.website_id,
                    crawl_job_id=job.id,
                    url=crawled.requested_url,
                    canonical_url=crawled.extracted.canonical_url,
                    title=crawled.extracted.title,
                    meta_description=crawled.extracted.meta_description,
                    cleaned_text=crawled.extracted.text,
                    content_hash=crawled.extracted.content_hash,
                    http_status=crawled.status_code,
                    content_type=crawled.content_type,
                    depth=crawled.depth,
                    fetched_at=crawled.fetched_at,
                )
                chunks = chunker.chunk(crawled.extracted.text)
                if not chunks:
                    continue
                pages.append(page)
                pending.extend(
                    PendingChunk(
                        page=page,
                        index=chunk.index,
                        content=chunk.content,
                        content_hash=chunk.content_hash,
                        token_count=chunk.token_count,
                    )
                    for chunk in chunks
                )
            if not pending:
                raise CrawlError("No retrieval chunks could be generated")
            existing_space = (
                (kb.embedding_provider, kb.embedding_model, kb.embedding_dimension)
                if kb and kb.embedding_provider and kb.embedding_model and kb.embedding_dimension
                else None
            )
            kb.status = "EMBEDDING"
            job.pages_indexed = len(pages)
            job.chunks_generated = len(pending)
            await db.commit()

        vectors: list[list[float]] = []
        space: tuple[str, str, int] | None = existing_space
        for start in range(0, len(pending), settings.embedding_batch_size):
            batch = pending[start : start + settings.embedding_batch_size]
            result = await tpi.passages(
                [item.content for item in batch],
                provider=space[0] if space else None,
                model=space[1] if space else None,
                dimension=space[2] if space else None,
            )
            current = (result.provider, result.model, result.dimension)
            if space is None:
                space = current
            elif current != space:
                raise TPIEmbeddingError("Embedding space is incompatible with existing knowledge base")
            if result.provider == "local" and settings.app_env.casefold() == "production":
                raise TPIEmbeddingError(
                    "Non-semantic local hash embeddings cannot be used in production"
                )
            if result.dimension != settings.embedding_storage_dimension:
                raise TPIEmbeddingError("Embedding dimension does not match vector storage")
            vectors.extend(result.embeddings)
        if space is None or len(vectors) != len(pending):
            raise TPIEmbeddingError("Embedding response count did not match chunk count")

        async with SessionLocal() as db:
            repository = ScraperRepository(db)
            job = await db.get(ScrapeJob, job_id)
            if job is None:
                return
            website = await db.get(Website, job.website_id)
            kb = await db.get(KnowledgeBase, job.knowledge_base_id)
            if website is None or kb is None:
                return
            chunks = [
                KnowledgeChunk(
                    id=uuid.uuid4(),
                    user_id=job.user_id,
                    knowledge_base_id=kb.id,
                    website_id=website.id,
                    page_id=item.page.id,
                    source_type="WEB_PAGE",
                    source_url=item.page.canonical_url,
                    chunk_index=item.index,
                    content=item.content,
                    content_hash=item.content_hash,
                    metadata_json={
                        "page_title": item.page.title,
                        "source_url": item.page.canonical_url,
                        "token_count": item.token_count,
                    },
                    embedding_provider=space[0],
                    embedding_model=space[1],
                    embedding_dimension=space[2],
                    embedding=vector,
                )
                for item, vector in zip(pending, vectors, strict=True)
            ]
            fingerprint = hashlib.sha256(
                "".join(sorted(page.content_hash for page in pages)).encode()
            ).hexdigest()
            await repository.replace_index(
                job=job,
                website=website,
                kb=kb,
                pages=pages,
                chunks=chunks,
                provider=space[0],
                model=space[1],
                dimension=space[2],
                content_fingerprint=fingerprint,
                partial_reason=crawl.partial_reason,
            )
    except (CrawlError, TPIEmbeddingError, URLValidationError) as exc:
        await _mark_failed(job_id, exc, preserve_ready=previous_ready)
        if getattr(exc, "retryable", False):
            raise RetryableIndexingError(str(exc)) from exc
    except Exception as exc:
        await _mark_failed(job_id, exc, preserve_ready=previous_ready)
        raise
    finally:
        if fetcher is not None:
            await fetcher.close()
        if tpi is not None:
            await tpi.close()


async def _mark_failed(job_id: UUID, error: Exception, *, preserve_ready: bool) -> None:
    async with SessionLocal() as db:
        job = await db.get(ScrapeJob, job_id)
        if job is None:
            return
        website = await db.get(Website, job.website_id)
        kb = await db.get(KnowledgeBase, job.knowledge_base_id)
        code = getattr(error, "code", error.__class__.__name__.upper())
        message = str(error)[:500] or "Website indexing failed"
        job.status = "FAILED"
        job.error_code = code
        job.error_message = message
        job.completed_at = func.now()
        if website:
            website.crawl_status = "READY" if preserve_ready else "FAILED"
        if kb:
            kb.status = "READY" if preserve_ready else "FAILED"
            kb.last_error = message
        await db.commit()
