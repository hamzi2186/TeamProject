import asyncio
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from app.core.config import get_settings
from app.providers.email_templates import render_email


class SmtpDeliveryError(RuntimeError):
    pass


def _send_sync(to: str, template: str, variables: dict[str, str]) -> None:
    settings = get_settings()
    subject, body = render_email(template, variables)
    message = EmailMessage()
    message["From"] = formataddr((settings.smtp_from_name, settings.smtp_from_email))
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            smtp.ehlo()
            if settings.smtp_use_tls:
                smtp.starttls()
                smtp.ehlo()
            smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise SmtpDeliveryError("SMTP delivery was rejected or unavailable") from None


async def send_email(to: str, template: str, variables: dict[str, str]) -> None:
    await asyncio.to_thread(_send_sync, to, template, variables)
