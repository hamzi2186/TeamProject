import asyncio
from uuid import UUID

from celery import Celery

from app.core.config import get_settings
from app.services.indexing import RetryableIndexingError, process_scrape_job

settings = get_settings()
celery_app = Celery("trex-scraper", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_default_queue="scraper.crawling",
    task_routes={"scraper.ingest_website": {"queue": "scraper.crawling"}},
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
)


@celery_app.task(bind=True, name="scraper.ingest_website", max_retries=3)
def ingest_website(self, job_id: str) -> None:
    try:
        asyncio.run(process_scrape_job(UUID(job_id)))
    except RetryableIndexingError as exc:
        countdown = min(300, 10 * (2**self.request.retries))
        raise self.retry(exc=exc, countdown=countdown) from exc


@celery_app.task(name="scraper.health.ping")
def ping() -> str:
    return "pong"
