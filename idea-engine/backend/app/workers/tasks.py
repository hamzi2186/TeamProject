import asyncio
from datetime import datetime, timezone

from app.core.logging import logger
from app.db.session import async_session_factory
from app.services.report_service import generate_daily_report
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.generate_daily_report_task")
def generate_daily_report_task(target_date_str: str | None = None) -> dict:
    """
    Celery task that executes daily report generation.
    Can be scheduled automatically or triggered asynchronously on demand.
    """
    if target_date_str:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    else:
        target_date = datetime.now(timezone.utc).date()

    logger.info(f"Starting background daily report generation for {target_date}")

    async def _runner():
        async with async_session_factory() as session:
            result = await generate_daily_report(session, target_date)
            return {
                "report_id": str(result.id),
                "date": str(result.report_date),
                "total_leads": result.total_leads,
                "status": result.status.value,
                "document_filename": result.document_filename,
            }

    try:
        res = asyncio.run(_runner())
        logger.info(f"Completed background daily report generation for {target_date}: {res}")
        return res
    except Exception as exc:
        logger.error(f"Error in generate_daily_report_task for {target_date}: {exc}")
        raise
