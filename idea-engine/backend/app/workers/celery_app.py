from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "idea_engine_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# Parse cron from settings or default to 23:59 UTC
cron_parts = settings.report_run_cron.split()
minute = cron_parts[0] if len(cron_parts) > 0 else "59"
hour = cron_parts[1] if len(cron_parts) > 1 else "23"

celery_app.conf.beat_schedule = {
    "run-end-of-day-lead-report": {
        "task": "app.workers.tasks.generate_daily_report_task",
        "schedule": crontab(minute=minute, hour=hour),
    },
}
