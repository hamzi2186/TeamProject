import uuid
from dataclasses import dataclass

import httpx

from app.core.config import get_settings


@dataclass(frozen=True)
class SentMessage:
    provider: str
    provider_message_id: str
    status: str
    from_number: str


async def send_sms(*, user_id: uuid.UUID, to_number: str, body: str) -> SentMessage:
    settings = get_settings()
    async with httpx.AsyncClient(base_url=settings.tpi_api_base_url, timeout=20) as client:
        response = await client.post(
            "/api/v1/internal/sms/send",
            headers={"X-TPI-Service-Token": settings.tpi_internal_service_token},
            json={"user_id": str(user_id), "to_number": to_number, "body": body},
        )
        response.raise_for_status()
        payload = response.json()
    return SentMessage(
        provider=payload["provider"],
        provider_message_id=payload["provider_message_id"],
        status=payload["status"],
        from_number=payload["from_number"],
    )


async def simulate_mock_reply(
    *, user_id: uuid.UUID, from_number: str, to_number: str, body: str
) -> None:
    settings = get_settings()
    async with httpx.AsyncClient(base_url=settings.tpi_api_base_url, timeout=20) as client:
        response = await client.post(
            "/api/v1/mock/sms/reply",
            json={
                "user_id": str(user_id),
                "from_number": from_number,
                "to_number": to_number,
                "body": body,
            },
        )
        response.raise_for_status()
