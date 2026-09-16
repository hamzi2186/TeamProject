from app.modules.calling.contracts import CallOutcome, CallStatus

# Stop words that trigger DO_NOT_CONTACT outcome (PRD §29)
STOP_WORDS = (
    "stop",
    "unsubscribe",
    "do not call",
    "don't call",
    "remove me",
    "take me off",
    "opt out",
    "opt-out",
)

# Positive interest signals
INTEREST_WORDS = (
    "interested",
    "sounds good",
    "tell me more",
    "would like to",
    "want to",
    "sign me up",
    "let's do it",
)

# Conversion signals
CONVERSION_WORDS = (
    "i'll take it",
    "sign up",
    "signed up",
    "purchased",
    "booked",
    "confirmed",
    "agreed",
)

# Follow-up signals
FOLLOW_UP_WORDS = (
    "call me back",
    "follow up",
    "reach out again",
    "try again",
    "maybe later",
    "next week",
    "next month",
    "check back",
)

# Rejection signals
REJECTION_WORDS = (
    "not interested",
    "no thank you",
    "no thanks",
    "not for me",
    "don't need",
    "please remove",
)


def classify_outcome(*, transcript: str | None, status: CallStatus) -> CallOutcome:
    """
    Rule-based outcome classification per PRD §29.
    Applied after call completes — used by service and Celery finalize task.
    """
    # Status-first outcomes (no transcript needed)
    if status == CallStatus.NO_ANSWER:
        return CallOutcome.NO_ANSWER
    if status == CallStatus.FAILED:
        return CallOutcome.FAILED
    if status == CallStatus.CANCELLED:
        return CallOutcome.FAILED

    if not transcript:
        return CallOutcome.COMPLETED

    normalized = transcript.lower()

    # DO_NOT_CONTACT is highest priority — always supersedes positive signals
    if any(word in normalized for word in STOP_WORDS):
        return CallOutcome.DO_NOT_CONTACT

    if any(word in normalized for word in CONVERSION_WORDS):
        return CallOutcome.CONVERTED

    if any(word in normalized for word in INTEREST_WORDS):
        return CallOutcome.INTERESTED

    if any(word in normalized for word in FOLLOW_UP_WORDS):
        return CallOutcome.FOLLOW_UP_REQUIRED

    if any(word in normalized for word in REJECTION_WORDS):
        return CallOutcome.NOT_INTERESTED

    return CallOutcome.COMPLETED
