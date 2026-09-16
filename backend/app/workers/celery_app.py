from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "trex-calling",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.update(
    task_default_queue="calling.calls",
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_routes={
        "calling.*": {"queue": "calling.calls"},
    },
)
