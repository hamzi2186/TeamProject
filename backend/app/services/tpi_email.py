import httpx

from app.core.config import get_settings


class EmailDeliveryError(RuntimeError):
    pass


async def send_auth_email(*, to: str, template: str, code: str) -> None:
    settings = get_settings()
    headers = {"X-TPI-Service-Token": settings.tpi_internal_service_token}
    payload = {"to": to, "template": template, "variables": {"code": code}}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{settings.tpi_api_base_url.rstrip('/')}/api/v1/internal/email-delivery/send",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        raise EmailDeliveryError("TPI email delivery failed") from exc
