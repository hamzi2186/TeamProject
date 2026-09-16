from datetime import datetime, timezone

from app.schemas.enums import Channel, Direction, LeadOutcome
from app.schemas.reports import TimelineEvent
from app.services.outcome_evaluator import evaluate_lead_outcome


def test_opt_out_overrides_interest():
    now = datetime.now(timezone.utc)
    events = [
        TimelineEvent(
            channel=Channel.CALL,
            direction=Direction.OUTBOUND,
            timestamp=now,
            content="Pitching product",
            outcome="INTERESTED",
        ),
        TimelineEvent(
            channel=Channel.SMS,
            direction=Direction.INBOUND,
            timestamp=now,
            content="Please stop contacting me and unsubscribe.",
        ),
    ]

    outcome, reason, next_action = evaluate_lead_outcome(events)
    assert outcome == LeadOutcome.DO_NOT_CONTACT
    assert "opted out" in reason.lower()
    assert "suppress" in next_action.lower()


def test_conversion_detection():
    now = datetime.now(timezone.utc)
    events = [
        TimelineEvent(
            channel=Channel.CALL,
            direction=Direction.INBOUND,
            timestamp=now,
            content="We reviewed the pricing and we booked the kickoff meeting. Deal closed.",
        ),
    ]

    outcome, reason, next_action = evaluate_lead_outcome(events)
    assert outcome == LeadOutcome.CONVERTED
    assert "conversion" in reason.lower()


def test_interest_detection():
    now = datetime.now(timezone.utc)
    events = [
        TimelineEvent(
            channel=Channel.EMAIL,
            direction=Direction.OUTBOUND,
            timestamp=now,
            content="Intro email",
        ),
        TimelineEvent(
            channel=Channel.SMS,
            direction=Direction.INBOUND,
            timestamp=now,
            content="Sounds good! Can you send more info and pricing details?",
        ),
    ]

    outcome, reason, next_action = evaluate_lead_outcome(events)
    assert outcome == LeadOutcome.INTERESTED
    assert "interest" in reason.lower()


def test_follow_up_detection():
    now = datetime.now(timezone.utc)
    events = [
        TimelineEvent(
            channel=Channel.CALL,
            direction=Direction.INBOUND,
            timestamp=now,
            content="I am busy right now, please call me back tomorrow afternoon.",
        ),
    ]

    outcome, reason, next_action = evaluate_lead_outcome(events)
    assert outcome == LeadOutcome.FOLLOW_UP_REQUIRED
    assert "follow-up" in reason.lower()


def test_unanswered_calls():
    now = datetime.now(timezone.utc)
    events = [
        TimelineEvent(
            channel=Channel.CALL,
            direction=Direction.OUTBOUND,
            timestamp=now,
            duration_seconds=0,
            outcome="NO_ANSWER",
        ),
    ]

    outcome, reason, next_action = evaluate_lead_outcome(events)
    assert outcome == LeadOutcome.NO_ANSWER
    assert "no_answer" in reason.lower() or "no answer" in reason.lower()


def test_outbound_only_no_response():
    now = datetime.now(timezone.utc)
    events = [
        TimelineEvent(
            channel=Channel.EMAIL,
            direction=Direction.OUTBOUND,
            timestamp=now,
            content="Outreach email",
        ),
        TimelineEvent(
            channel=Channel.SMS,
            direction=Direction.OUTBOUND,
            timestamp=now,
            content="Follow up text",
        ),
    ]

    outcome, reason, next_action = evaluate_lead_outcome(events)
    assert outcome == LeadOutcome.NO_RESPONSE
    assert "no reply" in reason.lower()
