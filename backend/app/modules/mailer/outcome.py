from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.modules.mailer.contracts import EmailOutcome


def classify_stop_condition(text: str | None) -> bool:
    if not text:
        return False
    lowered = text.lower()
    stop_markers = {
        "unsubscribe",
        "stop",
        "do not contact",
        "do-not-contact",
        "not interested",
        "not interested anymore",
        "remove me",
        "no further emails",
        "opt out",
    }
    return any(marker in lowered for marker in stop_markers)


def should_continue_from_outcome(outcome: str | None) -> bool:
    if outcome is None:
        return True
    definitive = {
        EmailOutcome.INTERESTED,
        EmailOutcome.NOT_INTERESTED,
        EmailOutcome.CONVERTED,
        EmailOutcome.DO_NOT_CONTACT,
        EmailOutcome.FAILED,
    }
    return outcome not in definitive


def compute_follow_up_at(outcome: str | None) -> datetime | None:
    if outcome == EmailOutcome.FOLLOW_UP_REQUIRED:
        return datetime.now(UTC) + timedelta(days=3)
    return None
