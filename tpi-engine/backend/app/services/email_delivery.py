from typing import Literal

from app.core.config import get_settings
from app.providers.brevo import adapter as brevo_adapter
from app.providers.brevo.adapter import BrevoDeliveryError
from app.providers.resend import adapter as resend_adapter
from app.providers.resend.adapter import ResendDeliveryError
from app.providers.smtp import adapter as smtp_adapter
from app.providers.smtp.adapter import SmtpDeliveryError


class EmailDeliveryError(RuntimeError):
    pass


async def send_email(
    to: str, template: str, variables: dict[str, str]
) -> Literal["smtp", "resend", "brevo"]:
    provider = get_settings().email_provider
    try:
        if provider == "smtp":
            await smtp_adapter.send_email(to, template, variables)
        elif provider == "resend":
            await resend_adapter.send_email(to, template, variables)
        else:
            await brevo_adapter.send_email(to, template, variables)
    except (SmtpDeliveryError, ResendDeliveryError, BrevoDeliveryError):
        raise EmailDeliveryError("Email provider delivery failed") from None
    return provider
