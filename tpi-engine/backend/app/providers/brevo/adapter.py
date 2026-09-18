import httpx

from app.core.config import get_settings
from app.providers.email_templates import render_email


class BrevoDeliveryError(RuntimeError):
    pass


async def send_email(to: str, template: str, variables: dict[str, str]) -> None:
    settings = get_settings()
    subject, body = render_email(template, variables)
    payload = {
        "sender": {
            "email": str(settings.brevo_from_email),
            "name": settings.brevo_from_name,
        },
        "to": [{"email": to}],
        "subject": subject,
        "textContent": body,
    }
    headers = {
        "accept": "application/json",
        "api-key": settings.brevo_api_key.get_secret_value(),
        "content-type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://api.brevo.com/v3/smtp/email", headers=headers, json=payload
            )
            response.raise_for_status()
    except httpx.HTTPError:
        raise BrevoDeliveryError("Brevo delivery was rejected or unavailable") from None
