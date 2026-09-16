import re
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

STOP_KEYWORDS = {"STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"}
START_KEYWORDS = {"START", "UNSTOP", "YES"}
HELP_KEYWORDS = {"HELP", "INFO"}


def compliance_command(body: str) -> str | None:
    normalized = re.sub(r"[^A-Z]", "", body.upper())
    if normalized in STOP_KEYWORDS:
        return "STOP"
    if normalized in START_KEYWORDS:
        return "START"
    if normalized in HELP_KEYWORDS:
        return "HELP"
    return None


def is_quiet_hours(
    timezone_name: str,
    *,
    start_hour: int,
    end_hour: int,
    now: datetime | None = None,
) -> bool:
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        timezone = ZoneInfo("UTC")
    local_hour = (now or datetime.now(UTC)).astimezone(timezone).hour
    if start_hour == end_hour:
        return False
    if start_hour > end_hour:
        return local_hour >= start_hour or local_hour < end_hour
    return start_hour <= local_hour < end_hour


def seconds_until_quiet_hours_end(
    timezone_name: str,
    *,
    start_hour: int,
    end_hour: int,
    now: datetime | None = None,
) -> int:
    current = now or datetime.now(UTC)
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        timezone = ZoneInfo("UTC")
    local = current.astimezone(timezone)
    target = local.replace(hour=end_hour, minute=0, second=0, microsecond=0)
    if target <= local:
        target += timedelta(days=1)
    return max(60, int((target - local).total_seconds()))
