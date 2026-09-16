from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.schemas.sms import InboundSmsEvent


def event(**overrides) -> InboundSmsEvent:
    return InboundSmsEvent(
        event_id="SM-test",
        user_id="33333333-3333-4333-8333-333333333333",
        provider_message_id="SM-test",
        from_number="+15555550111",
        to_number="+15555550100",
        body="Hello",
        occurred_at=datetime.now(UTC),
        **overrides,
    )


def test_inbound_event_defaults_to_twilio() -> None:
    assert event().provider == "twilio"


def test_inbound_event_accepts_mock_provider() -> None:
    assert event(provider="mock").provider == "mock"


def test_inbound_event_rejects_unknown_provider() -> None:
    with pytest.raises(ValidationError):
        event(provider="other")
