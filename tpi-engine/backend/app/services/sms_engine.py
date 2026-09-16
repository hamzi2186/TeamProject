import httpx
from fastapi import HTTPException

from app.core.config import get_settings


async def forward_sms_event(path: str, payload: dict) -> None:
    settings = get_settings()
    if not settings.sms_internal_service_token:
        raise HTTPException(503, "SMS internal service token is not configured")
    async with httpx.AsyncClient(
        base_url=settings.sms_engine_internal_base_url, timeout=10
    ) as client:
        response = await client.post(
            path,
            headers={"X-SMS-Service-Token": settings.sms_internal_service_token},
            json=payload,
        )
    if response.is_error:
        raise HTTPException(502, "SMS engine rejected the provider event")
