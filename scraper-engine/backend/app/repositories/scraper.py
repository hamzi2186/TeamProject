import uuid
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scraper import KnowledgeBase, KnowledgeChunk, Lead, ScrapeJob, WebPage, Website


@dataclass(frozen=True)
class WebsiteSummary:
    website: Website
    knowledge_base_id: UUID | None
    kb_status: str | None
    page_count: int
    chunk_count: int
    leads_using_kb: int


class ScraperRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def website_for_user(self, user_id: UUID, website_id: UUID) -> Website | None:
        return await self.db.scalar(
            select(Website).where(Website.id == website_id, Website.user_id == user_id)
        )

    async def knowledge_base_for_user(
        self, user_id: UUID, knowledge_base_id: UUID
    ) -> KnowledgeBase | None:
        return await self.db.scalar(
            select(KnowledgeBase).where(
                KnowledgeBase.id == knowledge_base_id,
                KnowledgeBase.user_id == user_id,
                KnowledgeBase.kb_type == "CLIENT",
            )
        )

    async def knowledge_base_for_website(
        self, user_id: UUID, website_id: UUID
    ) -> KnowledgeBase | None:
        return await self.db.scalar(
            select(KnowledgeBase).where(
                KnowledgeBase.user_id == user_id,
                KnowledgeBase.website_id == website_id,
                KnowledgeBase.kb_type == "CLIENT",
            )
        )

    async def active_job(self, website_id: UUID) -> ScrapeJob | None:
        return await self.db.scalar(
            select(ScrapeJob)
            .where(
                ScrapeJob.website_id == website_id,
                ScrapeJob.status.in_(["QUEUED", "RUNNING"]),
            )
            .order_by(ScrapeJob.created_at.desc())
        )

    async def latest_job(self, user_id: UUID, website_id: UUID) -> ScrapeJob | None:
        return await self.db.scalar(
            select(ScrapeJob)
            .where(ScrapeJob.website_id == website_id, ScrapeJob.user_id == user_id)
            .order_by(ScrapeJob.created_at.desc())
            .limit(1)
        )

    async def job_for_user(self, user_id: UUID, job_id: UUID) -> ScrapeJob | None:
        return await self.db.scalar(
            select(ScrapeJob).where(ScrapeJob.id == job_id, ScrapeJob.user_id == user_id)
        )

    async def create_site_kb_job(
        self,
        *,
        user_id: UUID,
        original_url: str,
        normalized_url: str,
        normalized_key: str,
        lead_ids: list[UUID],
        force_refresh: bool = False,
        website_id: UUID | None = None,
    ) -> tuple[Website, KnowledgeBase, ScrapeJob | None, bool]:
        if website_id is None:
            await self.db.execute(
                insert(Website)
                .values(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    original_url=original_url,
                    normalized_url=normalized_url,
                    normalized_key=normalized_key,
                    crawl_status="PENDING",
                )
                .on_conflict_do_nothing(constraint="uq_websites_user_normalized_key")
            )
            website = await self.db.scalar(
                select(Website).where(
                    Website.user_id == user_id,
                    Website.normalized_key == normalized_key,
                )
            )
        else:
            website = await self.website_for_user(user_id, website_id)
        if website is None:
            raise LookupError("Website not found")
        await self.db.execute(
            insert(KnowledgeBase)
            .values(
                id=uuid.uuid4(),
                user_id=user_id,
                website_id=website.id,
                kb_type="CLIENT",
                status="PENDING",
            )
            .on_conflict_do_nothing(constraint="uq_client_kb_user_website")
        )
        kb = await self.knowledge_base_for_website(user_id, website.id)
        if kb is None:
            raise RuntimeError("Knowledge base could not be created")
        if lead_ids:
            unique_ids = set(lead_ids)
            owned = set(
                (
                    await self.db.scalars(
                        select(Lead.id).where(Lead.user_id == user_id, Lead.id.in_(unique_ids))
                    )
                ).all()
            )
            if owned != unique_ids:
                raise LookupError("One or more leads were not found")
            await self.db.execute(
                update(Lead)
                .where(Lead.user_id == user_id, Lead.id.in_(unique_ids))
                .values(website_id=website.id)
            )
        active = await self.active_job(website.id)
        if active:
            await self.db.commit()
            return website, kb, active, True
        if kb.status in {"READY", "PARTIAL"} and not force_refresh:
            await self.db.commit()
            return website, kb, None, True
        job = ScrapeJob(
            user_id=user_id,
            website_id=website.id,
            knowledge_base_id=kb.id,
            status="QUEUED",
            is_refresh=force_refresh or kb.status in {"READY", "PARTIAL"},
        )
        self.db.add(job)
        website.crawl_status = "PENDING"
        if kb.status not in {"READY", "PARTIAL"}:
            kb.status = "PENDING"
        await self.db.commit()
        await self.db.refresh(job)
        return website, kb, job, False

    async def set_task_id(self, job_id: UUID, task_id: str) -> None:
        await self.db.execute(
            update(ScrapeJob).where(ScrapeJob.id == job_id).values(celery_task_id=task_id)
        )
        await self.db.commit()

    async def mark_dispatch_failed(self, user_id: UUID, job_id: UUID) -> None:
        await self.db.execute(
            update(ScrapeJob)
            .where(
                ScrapeJob.id == job_id,
                ScrapeJob.user_id == user_id,
                ScrapeJob.status == "QUEUED",
                ScrapeJob.celery_task_id.is_(None),
            )
            .values(
                status="FAILED",
                error_code="TASK_DISPATCH_FAILED",
                error_message="Website ingestion could not be queued",
                completed_at=func.now(),
            )
        )
        await self.db.commit()

    async def list_websites(
        self, user_id: UUID, normalized_key: str | None = None
    ) -> list[WebsiteSummary]:
        lead_count = (
            select(func.count(Lead.id))
            .where(Lead.website_id == Website.id, Lead.user_id == user_id)
            .correlate(Website)
            .scalar_subquery()
        )
        query = (
            select(Website, KnowledgeBase, lead_count.label("lead_count"))
            .outerjoin(
                KnowledgeBase,
                (KnowledgeBase.website_id == Website.id)
                & (KnowledgeBase.user_id == user_id)
                & (KnowledgeBase.kb_type == "CLIENT"),
            )
            .where(Website.user_id == user_id)
        )
        if normalized_key is not None:
            query = query.where(Website.normalized_key == normalized_key)
        result = await self.db.execute(query.order_by(Website.updated_at.desc()))
        return [
            WebsiteSummary(
                website=website,
                knowledge_base_id=kb.id if kb else None,
                kb_status=kb.status if kb else None,
                page_count=kb.page_count if kb else 0,
                chunk_count=kb.chunk_count if kb else 0,
                leads_using_kb=lead_total,
            )
            for website, kb, lead_total in result.all()
        ]

    async def website_summary(self, user_id: UUID, website_id: UUID) -> WebsiteSummary | None:
        summaries = await self.list_websites(user_id)
        return next((item for item in summaries if item.website.id == website_id), None)

    async def pages_for_website(self, user_id: UUID, website_id: UUID) -> list[WebPage]:
        result = await self.db.scalars(
            select(WebPage)
            .where(WebPage.user_id == user_id, WebPage.website_id == website_id)
            .order_by(WebPage.depth, WebPage.canonical_url)
        )
        return list(result.all())

    async def replace_index(
        self,
        *,
        job: ScrapeJob,
        website: Website,
        kb: KnowledgeBase,
        pages: list[WebPage],
        chunks: list[KnowledgeChunk],
        provider: str,
        model: str,
        dimension: int,
        content_fingerprint: str,
        partial_reason: str | None,
    ) -> None:
        await self.db.execute(
            delete(KnowledgeChunk).where(KnowledgeChunk.knowledge_base_id == kb.id)
        )
        await self.db.execute(delete(WebPage).where(WebPage.website_id == website.id))
        self.db.add_all(pages)
        await self.db.flush()
        self.db.add_all(chunks)
        status = "PARTIAL" if partial_reason else "READY"
        kb.status = status
        kb.embedding_provider = provider
        kb.embedding_model = model
        kb.embedding_dimension = dimension
        kb.page_count = len(pages)
        kb.chunk_count = len(chunks)
        kb.last_error = None
        website.crawl_status = status
        website.last_crawled_at = func.now()
        website.content_fingerprint = content_fingerprint
        job.status = "PARTIAL" if partial_reason else "COMPLETED"
        job.pages_indexed = len(pages)
        job.chunks_generated = len(chunks)
        job.partial_reason = partial_reason
        job.completed_at = func.now()
        await self.db.commit()
