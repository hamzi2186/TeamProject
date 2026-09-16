from urllib.parse import urlparse

from fastapi import FastAPI

from app.api.email_delivery import router as email_router
from app.api.embeddings import router as embeddings_router
from app.api.hubspot import callback as hubspot_callback
from app.api.hubspot import internal_router as hubspot_internal_router
from app.api.mock_sms import router as mock_sms_router
from app.api.sms_delivery import router as sms_delivery_router
from app.api.twilio_webhooks import router as twilio_webhooks_router
from app.core.config import get_settings
from app.providers.hubspot.schemas import CallbackResponse

settings = get_settings()
app = FastAPI(title="T Rex TPI", version="0.1.0")

# Email
app.include_router(email_router)

# Embeddings (scraper + agent)
app.include_router(embeddings_router)

# HubSpot OAuth
app.include_router(hubspot_internal_router)
hubspot_callback_path = urlparse(settings.hubspot_redirect_uri).path
if not hubspot_callback_path.startswith("/"):
    raise RuntimeError("HUBSPOT_REDIRECT_URI must contain an absolute callback path")
app.add_api_route(
    hubspot_callback_path,
    hubspot_callback,
    methods=["GET"],
    response_model=CallbackResponse,
    tags=["hubspot-oauth"],
)

# SMS / Twilio
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
            "hubspot": "configured",
            "embeddings": settings.embedding_provider,
            "sms": settings.sms_provider,
            "twilio_sms": "configured"
            if settings.twilio_configured
            else "pending_configuration",
        },
    }
