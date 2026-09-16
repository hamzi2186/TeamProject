import re
from app.schemas.enums import Channel, Direction, LeadOutcome
from app.schemas.reports import TimelineEvent

# Precedence hierarchy: higher value means higher priority when resolving conflicting signals
OUTCOME_PRECEDENCE: dict[LeadOutcome, int] = {
    LeadOutcome.DO_NOT_CONTACT: 100,
    LeadOutcome.CONVERTED: 90,
    LeadOutcome.INTERESTED: 80,
    LeadOutcome.FOLLOW_UP_REQUIRED: 70,
    LeadOutcome.NOT_INTERESTED: 60,
    LeadOutcome.CONTACTING: 50,
    LeadOutcome.NO_ANSWER: 40,
    LeadOutcome.NO_RESPONSE: 30,
    LeadOutcome.FAILED: 20,
    LeadOutcome.NEW: 10,
    LeadOutcome.COMPLETED: 15,
}

OPT_OUT_PATTERNS = [
    r"\bstop\b",
    r"\bunsubscribe\b",
    r"\bdo not contact\b",
    r"\bdon't contact\b",
    r"\bdon't call\b",
    r"\bremove me\b",
    r"\btake me off\b",
    r"\bnever call\b",
]

CONVERSION_PATTERNS = [
    r"\bbooked\b",
    r"\bsigned up\b",
    r"\bcontract signed\b",
    r"\blet's proceed\b",
    r"\blets proceed\b",
    r"\bdeal closed\b",
    r"\bi agree\b",
    r"\bready to buy\b",
]

INTEREST_PATTERNS = [
    r"\binterested\b",
    r"\bsounds good\b",
    r"\btell me more\b",
    r"\bsend (more|the) info\b",
    r"\bhow much\b",
    r"\bpricing\b",
    r"\bdemo\b",
    r"\blet's chat\b",
    r"\byes please\b",
]

FOLLOW_UP_PATTERNS = [
    r"\bcall (me )?(back|later)\b",
    r"\bbusy right now\b",
    r"\btomorrow\b",
    r"\bnext week\b",
    r"\blater today\b",
    r"\bfollow up\b",
    r"\breach out next\b",
]

NOT_INTERESTED_PATTERNS = [
    r"\bnot interested\b",
    r"\bno thank(s)?\b",
    r"\bno need\b",
    r"\bnot looking\b",
    r"\bwrong person\b",
    r"\bwrong number\b",
    r"\bpass\b",
]


def evaluate_lead_outcome(
    events: list[TimelineEvent],
    persisted_outcome: str | None = None,
    current_status: str | None = None,
) -> tuple[LeadOutcome, str, str | None]:
    """
    Evaluates multi-channel interaction history for a lead to determine:
    1. Canonical final outcome (following strict precedence)
    2. Specific evidence and rationale
    3. Recommended next action
    """
    if not events:
        if current_status and current_status.upper() in LeadOutcome.__members__:
            outcome = LeadOutcome(current_status.upper())
            return outcome, f"Status reflects existing lead state ({outcome.value}) with no recorded events.", "Initiate initial campaign outreach."
        return LeadOutcome.NEW, "No outreach activity or communication events recorded for this lead.", "Enroll lead in an active campaign."

    detected_outcomes: list[tuple[LeadOutcome, str, str | None]] = []

    # 1. Check if any event has an explicit outcome recorded by an engine
    for event in events:
        if event.outcome:
            clean_outcome = event.outcome.upper().strip()
            if clean_outcome in LeadOutcome.__members__:
                enum_val = LeadOutcome(clean_outcome)
                detected_outcomes.append(
                    (
                        enum_val,
                        f"Explicit {event.channel.value} outcome marked as '{enum_val.value}' at {event.timestamp.strftime('%H:%M:%S')}.",
                        _default_next_action(enum_val),
                    )
                )

    # 2. Analyze inbound communication text content
    inbound_events = [e for e in events if e.direction == Direction.INBOUND]
    for event in inbound_events:
        text = (event.content or "").lower()

        # Check opt-out
        for pat in OPT_OUT_PATTERNS:
            if re.search(pat, text):
                detected_outcomes.append(
                    (
                        LeadOutcome.DO_NOT_CONTACT,
                        f"Lead explicitly opted out in inbound {event.channel.value} ('{event.content[:60]}...').",
                        "Immediately update CRM to Do Not Contact and suppress all future campaigns.",
                    )
                )
                break

        # Check conversion
        for pat in CONVERSION_PATTERNS:
            if re.search(pat, text):
                detected_outcomes.append(
                    (
                        LeadOutcome.CONVERTED,
                        f"Lead expressed conversion agreement in inbound {event.channel.value} ('{event.content[:60]}...').",
                        "Notify account executive to finalize onboarding and execute agreement.",
                    )
                )
                break

        # Check positive interest
        for pat in INTEREST_PATTERNS:
            if re.search(pat, text):
                detected_outcomes.append(
                    (
                        LeadOutcome.INTERESTED,
                        f"Lead expressed positive interest in inbound {event.channel.value} ('{event.content[:60]}...').",
                        "Schedule discovery call or deliver tailored presentation.",
                    )
                )
                break

        # Check follow-up requested
        for pat in FOLLOW_UP_PATTERNS:
            if re.search(pat, text):
                detected_outcomes.append(
                    (
                        LeadOutcome.FOLLOW_UP_REQUIRED,
                        f"Lead requested follow-up / reschedule in inbound {event.channel.value} ('{event.content[:60]}...').",
                        "Set automated follow-up reminder for the requested time window.",
                    )
                )
                break

        # Check explicit decline
        for pat in NOT_INTERESTED_PATTERNS:
            if re.search(pat, text):
                detected_outcomes.append(
                    (
                        LeadOutcome.NOT_INTERESTED,
                        f"Lead declined in inbound {event.channel.value} ('{event.content[:60]}...').",
                        "Archive lead from current campaign; re-evaluate in 90 days.",
                    )
                )
                break

    # 3. If no decisive signal from inbound text, evaluate communication channel behavior
    if not detected_outcomes:
        # Check if calls were attempted
        calls = [e for e in events if e.channel == Channel.CALL]
        if calls and all(
            (c.duration_seconds or 0) == 0 or (c.outcome and "NO_ANSWER" in c.outcome.upper())
            for c in calls
        ):
            if not inbound_events:
                detected_outcomes.append(
                    (
                        LeadOutcome.NO_ANSWER,
                        f"{len(calls)} call attempt(s) placed with no answer or zero duration.",
                        "Retry phone outreach at an alternate time or follow up via SMS.",
                    )
                )

        # Check if only outbound messages with no inbound response
        outbound_only = len(inbound_events) == 0 and len(events) > 0
        if outbound_only and not detected_outcomes:
            channels_used = {e.channel.value for e in events}
            channels_str = ", ".join(sorted(channels_used))
            detected_outcomes.append(
                (
                    LeadOutcome.NO_RESPONSE,
                    f"Outbound touchpoints sent via {channels_str} ({len(events)} total) with no reply received.",
                    "Execute scheduled multi-channel nurture sequence or wait for response window.",
                )
            )

    # 4. If an outcome is explicitly persisted in conversation/lead record, consider it
    if persisted_outcome:
        clean_persisted = persisted_outcome.upper().strip()
        if clean_persisted in LeadOutcome.__members__:
            persisted_enum = LeadOutcome(clean_persisted)
            detected_outcomes.append(
                (
                    persisted_enum,
                    f"Persisted record outcome: {persisted_enum.value}.",
                    _default_next_action(persisted_enum),
                )
            )

    # 5. Resolve according to strict precedence
    if detected_outcomes:
        detected_outcomes.sort(key=lambda x: OUTCOME_PRECEDENCE.get(x[0], 0), reverse=True)
        return detected_outcomes[0]

    # Fallback to CONTACTING if active events exist
    return (
        LeadOutcome.CONTACTING,
        f"{len(events)} touchpoints recorded; active conversation in progress.",
        "Continue active conversation workflow.",
    )


def _default_next_action(outcome: LeadOutcome) -> str:
    match outcome:
        case LeadOutcome.DO_NOT_CONTACT:
            return "Immediately suppress all outreach and tag as Do Not Contact."
        case LeadOutcome.CONVERTED:
            return "Pass lead to account executive for onboarding."
        case LeadOutcome.INTERESTED:
            return "Send meeting invite or detailed product demo."
        case LeadOutcome.FOLLOW_UP_REQUIRED:
            return "Schedule follow-up touchpoint as requested by lead."
        case LeadOutcome.NOT_INTERESTED:
            return "Pause active campaign; place in dormant nurture pool."
        case LeadOutcome.NO_ANSWER:
            return "Retry call at alternate time or send follow-up SMS."
        case LeadOutcome.NO_RESPONSE:
            return "Send second-stage email or SMS follow-up."
        case LeadOutcome.CONTACTING:
            return "Await response or trigger next sequence step."
        case LeadOutcome.FAILED:
            return "Verify contact details (phone/email deliverability)."
        case _:
            return "Monitor lead engagement."
