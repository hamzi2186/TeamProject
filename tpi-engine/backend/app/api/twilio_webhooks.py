from datetime import UTC, datetime
from urllib.parse import urljoin

from fastapi import APIRouter, HTTPException, Request, Response
from twilio.request_validator import RequestValidator

from app.core.config import get_settings
from app.providers.twilio.adapter import TwilioConfigurationError, user_for_number
from app.services.sms_engine import forward_sms_event

router = APIRouter(prefix="/api/v1/provider/twilio/sms", tags=["twilio-sms"])


@router.post("/inbound")
async def inbound_sms(request: Request) -> Response:
    form = dict(await request.form())
    _validate_signature(request, form)
    try:
        user_id = user_for_number(form["To"])
    except (KeyError, TwilioConfigurationError) as exc:
        raise HTTPException(422, "Inbound number is not assigned") from exc
    await forward_sms_event(
        "/api/v1/internal/sms/events/inbound",
        {
            "provider": "twilio",
            "event_id": form["MessageSid"],
            "user_id": str(user_id),
            "provider_message_id": form["MessageSid"],
            "from_number": form["From"],
            "to_number": form["To"],
            "body": form.get("Body", ""),
            "occurred_at": datetime.now(UTC).isoformat(),
            "raw_payload": form,
        },
    )
    return Response("<Response></Response>", media_type="application/xml")


@router.post("/status", status_code=204)
async def delivery_status(request: Request) -> Response:
    form = dict(await request.form())
    _validate_signature(request, form)
    try:
        user_id = user_for_number(form.get("From", ""))
    except TwilioConfigurationError as exc:
        raise HTTPException(422, "Sender number is not assigned") from exc
    normalized = _status(form.get("MessageStatus", "failed"))
    await forward_sms_event(
        "/api/v1/internal/sms/events/status",
        {
            "provider": "twilio",
            "event_id": f"{form['MessageSid']}:{normalized}",
            "user_id": str(user_id),
            "provider_message_id": form["MessageSid"],
            "status": normalized,
            "error_code": form.get("ErrorCode") or None,
            "occurred_at": datetime.now(UTC).isoformat(),
            "raw_payload": form,
        },
    )
    return Response(status_code=204)


def _validate_signature(request: Request, form: dict) -> None:
    settings = get_settings()
    if not settings.twilio_auth_token:
        raise HTTPException(503, "Twilio is not configured")
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)
    if settings.public_webhook_base_url:
        url = urljoin(
            f"{settings.public_webhook_base_url.rstrip('/')}/",
            request.url.path.lstrip("/"),
        )
    if not RequestValidator(settings.twilio_auth_token).validate(url, form, signature):
        raise HTTPException(403, "Invalid Twilio signature")


def _status(value: str) -> str:
    return {
        "accepted": "QUEUED",
        "scheduled": "QUEUED",
        "queued": "QUEUED",
        "sending": "SENT",
        "sent": "SENT",
        "delivered": "DELIVERED",
        "undelivered": "UNDELIVERED",
        "failed": "FAILED",
    }.get(value.lower(), "FAILED")
