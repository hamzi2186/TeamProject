from typing import Literal

from app.core.config import get_settings
from app.providers.resend import adapter as resend_adapter
from app.providers.resend.adapter import ResendDeliveryError
from app.providers.smtp import adapter as smtp_adapter
from app.providers.smtp.adapter import SmtpDeliveryError


class EmailDeliveryError(RuntimeError):
    pass


async def send_email(
    to: str, template: str, variables: dict[str, str]
) -> Literal["smtp", "resend"]:
    provider = get_settings().email_provider
    try:
        if provider == "smtp":
            await smtp_adapter.send_email(to, template, variables)
        else:
            await resend_adapter.send_email(to, template, variables)
    except (SmtpDeliveryError, ResendDeliveryError):
        raise EmailDeliveryError("Email provider delivery failed") from None
    return provider
