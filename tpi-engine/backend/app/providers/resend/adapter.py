from email.utils import formataddr

import httpx

from app.core.config import get_settings
from app.providers.email_templates import render_email


class ResendDeliveryError(RuntimeError):
    pass


async def send_email(to: str, template: str, variables: dict[str, str]) -> None:
    settings = get_settings()
    subject, body = render_email(template, variables)
    payload = {
        "from": formataddr((settings.resend_from_name, settings.resend_from_email)),
        "to": [to],
        "subject": subject,
        "text": body,
    }
    headers = {
        "Authorization": f"Bearer {settings.resend_api_key.get_secret_value()}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://api.resend.com/emails", headers=headers, json=payload
            )
            response.raise_for_status()
    except httpx.HTTPError:
        raise ResendDeliveryError("Resend delivery was rejected or unavailable") from None
