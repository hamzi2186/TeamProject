from celery import Celery

from app.core.config import get_settings

settings = get_settings()
celery_app = Celery("trex-platform", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_default_queue="platform.default",
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
)


@celery_app.task(name="platform.health.ping")
def ping() -> str:
    return "pong"
