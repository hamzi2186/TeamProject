from __future__ import annotations

from typing import Any

from app.workers.celery_app import celery_app


@celery_app.task(name="mailer.send_email")
def send_email(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {"status": "queued", "args": args, "kwargs": kwargs}


@celery_app.task(name="mailer.process_inbound_email")
def process_inbound_email(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {"status": "processed", "args": args, "kwargs": kwargs}


@celery_app.task(name="mailer.process_email_delivery_event")
def process_email_delivery_event(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {"status": "processed", "args": args, "kwargs": kwargs}


@celery_app.task(name="mailer.classify_email_outcome")
def classify_email_outcome(*args: Any, **kwargs: Any) -> dict[str, Any]:
    return {"status": "classified", "args": args, "kwargs": kwargs}
