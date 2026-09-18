SUBJECTS = {
    "verify_email": "Verify your T Rex account",
    "reset_password": "Reset your T Rex password",
    "smtp_smoke": "T Rex SMTP integration check",
}


def render_email(template: str, variables: dict[str, str]) -> tuple[str, str]:
    subject = SUBJECTS.get(template, "T Rex Notification")
    if template == "smtp_smoke":
        return subject, "T Rex successfully delivered this real SMTP integration check."
    code = variables.get("code", "")
    action = "verify your email" if template == "verify_email" else "reset your password"
    body = (
        f"Use this six-digit code to {action}: {code}\n\n"
        "This code expires soon. If you did not request it, you can ignore this email."
    )
    return subject, body
