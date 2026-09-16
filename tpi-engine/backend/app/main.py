from urllib.parse import urlparse

from fastapi import FastAPI

from app.api.calling import router as calling_router
from app.api.email_delivery import router as email_router
from app.api.hubspot import callback as hubspot_callback
from app.api.hubspot import internal_router as hubspot_internal_router
from app.api.vapi_webhooks import router as vapi_webhook_router
from app.core.config import get_settings
from app.providers.hubspot.schemas import CallbackResponse

settings = get_settings()
app = FastAPI(title="T Rex TPI", version="0.1.0")

app.include_router(email_router)
app.include_router(hubspot_internal_router)
app.include_router(calling_router)
app.include_router(vapi_webhook_router)

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


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "tpi",
        "adapters": {
            "smtp": "configured",
            "hubspot": "configured",
            "vapi": "configured" if settings.vapi_api_key else "ready",
        },
    }
