import pytest
from pydantic import ValidationError

from app.schemas.agent import AgentDecision


def test_agent_decision_accepts_known_outcome() -> None:
    decision = AgentDecision(
        message="That sounds good. Would Tuesday work?",
        outcome="FOLLOW_UP_REQUESTED",
        should_stop=True,
        reason="The lead requested a follow-up.",
    )
    assert decision.should_stop is True


def test_agent_decision_rejects_unknown_outcome() -> None:
    with pytest.raises(ValidationError):
        AgentDecision(
            message="Okay",
            outcome="MAYBE_LATER",
            should_stop=True,
            reason="Unsupported outcome",
        )
