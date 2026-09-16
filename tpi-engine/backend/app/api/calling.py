from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.providers.vapi.adapter import VapiAdapter, VapiProviderError

router = APIRouter(prefix="/api/v1/internal/calling", tags=["internal-calling"])
provider = VapiAdapter()


def require_service_token(token: str | None) -> None:
    settings = get_settings()
    if not settings.tpi_internal_service_token or token != settings.tpi_internal_service_token:
        raise HTTPException(status_code=401, detail="Invalid TPI service token")


class StartCallRequest(BaseModel):
    user_id: str
    lead_id: str
    phone_number: str
    purpose: str
    campaign_id: str | None = None
    prompt: str | None = None
    lead_variables: dict[str, Any] = Field(default_factory=dict)


@router.post("/start")
def start_call(request: StartCallRequest, x_tpi_service_token: str | None = Header(default=None)) -> dict[str, Any]:
    require_service_token(x_tpi_service_token)
    try:
        result = provider.start_call(**request.model_dump())
    except VapiProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"success": True, "data": {"provider": "vapi", "provider_call_id": result.get("id"), "call": result}, "error": None}


@router.get("/{provider_call_id}")
def get_call(provider_call_id: str, x_tpi_service_token: str | None = Header(default=None)) -> dict[str, Any]:
    require_service_token(x_tpi_service_token)
    return {"success": True, "data": provider.get_call(provider_call_id), "error": None}


@router.delete("/{provider_call_id}")
def cancel_call(provider_call_id: str, x_tpi_service_token: str | None = Header(default=None)) -> dict[str, Any]:
    require_service_token(x_tpi_service_token)
    return {"success": True, "data": provider.cancel_call(provider_call_id), "error": None}
