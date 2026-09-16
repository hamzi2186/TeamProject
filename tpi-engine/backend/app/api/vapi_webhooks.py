import hashlib
import hmac
import json
from typing import Any

import httpx
from fastapi import APIRouter, Header, HTTPException

from app.core.config import get_settings

router = APIRouter(prefix="/api/v1/tpi/webhooks/vapi", tags=["vapi-webhooks"])


def _verify_signature(signature: str | None, payload: dict[str, Any]) -> None:
    settings = get_settings()
    if not settings.vapi_webhook_secret:
        if settings.app_env == "production":
            raise HTTPException(status_code=503, detail="Vapi webhook secret is not configured")
        return
    if not signature:
        raise HTTPException(status_code=401, detail="Vapi webhook signature required")
    digest = hmac.new(
        settings.vapi_webhook_secret.encode(),
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature.removeprefix("sha256="), digest):
        raise HTTPException(status_code=401, detail="Invalid Vapi webhook signature")


@router.post("/events")
async def vapi_event(
    payload: dict[str, Any],
    x_vapi_signature: str | None = Header(default=None),
    x_vapi_event_id: str | None = Header(default=None),
) -> dict[str, Any]:
    settings = get_settings()
    _verify_signature(x_vapi_signature, payload)
    event_id = x_vapi_event_id or payload.get("id") or payload.get("event_id") or "vapi-evt"
    
    # Normalize event payload
    normalized_payload = {
        "event_id": event_id,
        "type": payload.get("type", "status-update"),
        "call": payload.get("call", {}),
        "status": payload.get("status") or payload.get("call", {}).get("status"),
        "raw": payload,
    }

    # Forward normalized event to Calling Engine internal webhook
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                settings.calling_internal_webhook_url,
                json=normalized_payload,
                headers={"X-TPI-Event-Id": event_id, "X-Vapi-Event-Id": event_id},
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        # Don't fail the webhook acknowledgement to Vapi if calling engine is temporarily busy
        return {"success": True, "data": {"status": "forward_failed", "detail": str(exc)}, "error": None}

    return {"success": True, "data": {"status": "forwarded", "event_id": event_id}, "error": None}
