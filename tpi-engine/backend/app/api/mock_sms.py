import uuid
from dataclasses import asdict
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status

from app.contracts.sms import MockSmsMessage, MockSmsReplyRequest
from app.core.config import get_settings
from app.providers.mock_sms.adapter import messages
from app.services.sms_engine import forward_sms_event

router = APIRouter(prefix="/api/v1/mock/sms", tags=["mock-sms"])


def require_mock_provider() -> None:
    settings = get_settings()
    if settings.app_env == "production" or settings.sms_provider != "mock":
        raise HTTPException(404, "Mock SMS transport is not enabled")


@router.get("/messages", response_model=list[MockSmsMessage])
async def list_messages() -> list[dict]:
    require_mock_provider()
    return [asdict(message) for message in messages]


@router.post("/reply", status_code=status.HTTP_202_ACCEPTED)
async def simulate_reply(payload: MockSmsReplyRequest) -> dict:
    require_mock_provider()
    sid = f"SMmock{uuid.uuid4().hex}"
    await forward_sms_event(
        "/api/v1/internal/sms/events/inbound",
        {
            "provider": "mock",
            "event_id": sid,
            "user_id": str(payload.user_id),
            "provider_message_id": sid,
            "from_number": payload.from_number,
            "to_number": payload.to_number,
            "body": payload.body,
            "occurred_at": datetime.now(UTC).isoformat(),
            "raw_payload": {"transport": "mock"},
        },
    )
    return {"accepted": True, "provider_message_id": sid}
