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


class TPIServiceError(RuntimeError):
    pass


async def generate_llm_text(
    *, system_prompt: str, user_prompt: str, temperature: float, max_tokens: int
) -> str:
    settings = get_settings()
    async with httpx.AsyncClient(base_url=settings.tpi_api_base_url, timeout=45) as client:
        try:
            response = await client.post(
                "/api/v1/internal/llm/generate",
                headers={
                    "X-TPI-Service-Token": settings.tpi_internal_service_token,
                    "X-Consumer-Engine": "sms",
                },
                json={
                    "system_prompt": system_prompt,
                    "user_prompt": user_prompt,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "consumer": "sms",
                },
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise TPIServiceError("TPI LLM service is unavailable") from exc
    if response.status_code >= 400:
        raise TPIServiceError("TPI LLM service could not generate a decision")
    try:
        text = response.json()["text"]
    except (KeyError, TypeError, ValueError) as exc:
        raise TPIServiceError("TPI LLM service returned an invalid response") from exc
    if not isinstance(text, str) or not text.strip():
        raise TPIServiceError("TPI LLM service returned an empty response")
    return text


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
