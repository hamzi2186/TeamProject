from fastapi import FastAPI

from app.api.email_delivery import router as email_router
from app.api.mock_sms import router as mock_sms_router
from app.api.sms_delivery import router as sms_delivery_router
from app.api.twilio_webhooks import router as twilio_webhooks_router
from app.core.config import get_settings

settings = get_settings()
app = FastAPI(title="T Rex TPI", version="0.1.0")
app.include_router(email_router)
app.include_router(sms_delivery_router)
app.include_router(twilio_webhooks_router)
app.include_router(mock_sms_router)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "tpi",
        "adapters": {
            "smtp": "configured",
            "sms": settings.sms_provider,
            "twilio_sms": "configured"
            if settings.twilio_configured
            else "pending_configuration",
        },
    }
