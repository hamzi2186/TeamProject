import secrets

from fastapi import APIRouter, Header, HTTPException
from twilio.base.exceptions import TwilioRestException

from app.contracts.sms import SmsSendRequest, SmsSendResponse
from app.core.config import get_settings
from app.providers.mock_sms.adapter import send_message as send_mock_message
from app.providers.twilio.adapter import TwilioConfigurationError, send_message

router = APIRouter(prefix="/api/v1/internal/sms", tags=["internal-sms"])


def require_service_token(x_tpi_service_token: str = Header(...)) -> None:
    if not secrets.compare_digest(
        x_tpi_service_token, get_settings().tpi_internal_service_token
    ):
        raise HTTPException(401, "Invalid internal service credentials")


@router.post("/send", response_model=SmsSendResponse)
async def send_sms(
    payload: SmsSendRequest, x_tpi_service_token: str = Header(...)
) -> SmsSendResponse:
    require_service_token(x_tpi_service_token)
    try:
        if get_settings().sms_provider == "mock":
            result = await send_mock_message(
                payload.user_id, payload.to_number, payload.body
            )
        else:
            result = await send_message(payload.user_id, payload.to_number, payload.body)
    except TwilioConfigurationError as exc:
        raise HTTPException(503, str(exc)) from exc
    except TwilioRestException as exc:
        raise HTTPException(502, "Twilio rejected the SMS delivery request") from exc
    return SmsSendResponse(
        provider=get_settings().sms_provider,
        provider_message_id=result.sid,
        status=result.status,
        from_number=result.from_number,
    )
