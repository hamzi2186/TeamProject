from fastapi import APIRouter, Header, HTTPException

from app.api.dependencies import require_service_token
from app.contracts.email import EmailDeliveryRequest, EmailDeliveryResponse
from app.services.email_delivery import EmailDeliveryError, send_email

router = APIRouter(prefix="/api/v1/internal/email-delivery", tags=["internal-email"])


@router.post("/send", response_model=EmailDeliveryResponse)
async def deliver(
    payload: EmailDeliveryRequest, x_tpi_service_token: str = Header(...)
) -> EmailDeliveryResponse:
    require_service_token(x_tpi_service_token)
    try:
        provider = await send_email(str(payload.to), payload.template, payload.variables)
    except EmailDeliveryError as exc:
        raise HTTPException(502, "Email provider delivery failed") from exc
    return EmailDeliveryResponse(accepted=True, transport=provider)
