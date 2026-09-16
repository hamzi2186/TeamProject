from app.modules.calling.contracts import CallStatus
from app.modules.calling.outcome import classify_outcome


def test_stop_request_maps_to_do_not_contact() -> None:
    outcome = classify_outcome(transcript="Please stop calling me", status=CallStatus.COMPLETED)
    assert outcome == "DO_NOT_CONTACT"


def test_no_answer_maps_to_no_answer() -> None:
    outcome = classify_outcome(transcript="", status=CallStatus.NO_ANSWER)
    assert outcome == "NO_ANSWER"
