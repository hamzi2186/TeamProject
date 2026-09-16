from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.scraper import ScraperRepository
from app.services.tpi_embeddings import create_tpi_embedding_client


def get_repository(db: Annotated[AsyncSession, Depends(get_db)]) -> ScraperRepository:
    return ScraperRepository(db)


async def get_embedding_client():
    client = create_tpi_embedding_client()
    try:
        yield client
    finally:
        await client.close()


class TaskDispatcher:
    def dispatch(self, job_id) -> str:
        from app.workers.celery_app import ingest_website

        return ingest_website.apply_async(args=[str(job_id)], queue="scraper.crawling").id


def get_task_dispatcher() -> TaskDispatcher:
    return TaskDispatcher()
