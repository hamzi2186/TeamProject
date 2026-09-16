from datetime import UTC, datetime

from app.services.compliance import compliance_command, is_quiet_hours


def test_stop_keywords_are_normalized() -> None:
    assert compliance_command(" stop! ") == "STOP"
    assert compliance_command("Unsubscribe") == "STOP"


def test_start_and_help_keywords_are_recognized() -> None:
    assert compliance_command("START") == "START"
    assert compliance_command("help") == "HELP"
    assert compliance_command("Yes, tell me more") is None


def test_overnight_quiet_hours_use_recipient_timezone() -> None:
    quiet = datetime(2026, 9, 16, 2, 0, tzinfo=UTC)  # 22:00 previous day in New York
    daytime = datetime(2026, 9, 16, 16, 0, tzinfo=UTC)  # 12:00 in New York
    assert is_quiet_hours(
        "America/New_York", start_hour=20, end_hour=8, now=quiet
    )
    assert not is_quiet_hours(
        "America/New_York", start_hour=20, end_hour=8, now=daytime
    )
