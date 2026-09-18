import asyncio
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from app.core.config import get_settings


class SmtpDeliveryError(RuntimeError):
    pass


SUBJECTS = {"verify_email": "Verify your T Rex account", "reset_password": "Reset your T Rex password", "smtp_smoke": "T Rex SMTP integration check"}


def _render(template: str, variables: dict[str, str]) -> str:
    if template == "smtp_smoke":
        return "T Rex successfully delivered this real SMTP integration check."
    code = variables.get("code", "")
    action = "verify your email" if template == "verify_email" else "reset your password"
    return f"Use this six-digit code to {action}: {code}\n\nThis code expires soon. If you did not request it, you can ignore this email."


import logging

logger = logging.getLogger("tpi.smtp")

def _send_sync(to: str, template: str, variables: dict[str, str]) -> None:
    settings = get_settings()
    message = EmailMessage()
    message["From"] = formataddr((settings.smtp_from_name, settings.smtp_from_email))
    message["To"] = to
    message["Subject"] = SUBJECTS.get(template, "T Rex Notification")
    message.set_content(_render(template, variables))
    code = variables.get("code", "")
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            smtp.ehlo()
            if settings.smtp_use_tls:
                smtp.starttls()
                smtp.ehlo()
            smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
            logger.info("Real SMTP email delivered successfully to %s via %s", to, settings.smtp_host)
            print(f"\n[OK] [SMTP DELIVERED] Real email sent to {to} with code: {code}\n", flush=True)
    except (OSError, smtplib.SMTPException) as exc:
        print(f"\n==================================================", flush=True)
        print(f"[*] [T REX AUTH CODE] To: {to}", flush=True)
        print(f"[*] 6-Digit OTP Code: {code}", flush=True)
        print(f"[*] Action: {template}", flush=True)
        print(f"[*] SMTP status: {exc}", flush=True)
        print(f"==================================================\n", flush=True)
        logger.warning("SMTP delivery notice (%s). OTP code for %s: %s", exc, to, code)
        if settings.app_env != "production" or settings.smtp_password == "dev_pass" or settings.smtp_host in ("localhost", "127.0.0.1"):
            # Do not block authentication in dev/testing mode
            return
        raise SmtpDeliveryError("SMTP delivery was rejected or unavailable") from exc


async def send_email(to: str, template: str, variables: dict[str, str]) -> None:
    await asyncio.to_thread(_send_sync, to, template, variables)
