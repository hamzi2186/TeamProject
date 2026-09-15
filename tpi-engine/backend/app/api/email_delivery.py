import secrets

from fastapi import APIRouter, Header, HTTPException

from app.contracts.email import EmailDeliveryRequest, EmailDeliveryResponse
from app.core.config import get_settings
from app.providers.smtp.adapter import SmtpDeliveryError, send_email

router = APIRouter(prefix="/api/v1/internal/email-delivery", tags=["internal-email"])


def require_service_token(x_tpi_service_token: str = Header(...)) -> None:
    expected = get_settings().tpi_internal_service_token
    if not secrets.compare_digest(x_tpi_service_token, expected):
        raise HTTPException(401, "Invalid internal service credentials")


@router.post("/send", response_model=EmailDeliveryResponse)
async def deliver(
    payload: EmailDeliveryRequest, x_tpi_service_token: str = Header(...)
) -> EmailDeliveryResponse:
    require_service_token(x_tpi_service_token)
    try:
        await send_email(str(payload.to), payload.template, payload.variables)
    except SmtpDeliveryError as exc:
        raise HTTPException(502, "Email provider delivery failed") from exc
    return EmailDeliveryResponse(accepted=True)
