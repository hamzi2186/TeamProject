import asyncio
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from app.core.config import get_settings


class SmtpDeliveryError(RuntimeError):
    pass


SUBJECTS = {
    "verify_email": "Verify your T Rex account",
    "reset_password": "Reset your T Rex password",
    "smtp_smoke": "T Rex SMTP integration check",
}


def _render(template: str, variables: dict[str, str]) -> str:
    if template == "smtp_smoke":
        return "T Rex successfully delivered this real SMTP integration check."
    code = variables.get("code", "")
    action = "verify your email" if template == "verify_email" else "reset your password"
    return (
        f"Use this six-digit code to {action}: {code}\n\n"
        "This code expires soon. If you did not request it, you can ignore this email."
    )


def _send_sync(to: str, template: str, variables: dict[str, str]) -> None:
    settings = get_settings()
    message = EmailMessage()
    message["From"] = formataddr((settings.smtp_from_name, settings.smtp_from_email))
    message["To"] = to
    message["Subject"] = SUBJECTS[template]
    message.set_content(_render(template, variables))
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            smtp.ehlo()
            if settings.smtp_use_tls:
                smtp.starttls()
                smtp.ehlo()
            smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise SmtpDeliveryError("SMTP delivery was rejected or unavailable") from exc


async def send_email(to: str, template: str, variables: dict[str, str]) -> None:
    await asyncio.to_thread(_send_sync, to, template, variables)
