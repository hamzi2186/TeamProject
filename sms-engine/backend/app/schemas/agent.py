from pydantic import BaseModel, ConfigDict, Field

from app.schemas.sms import Outcome


class AgentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=600)
    outcome: Outcome | None
    should_stop: bool
    reason: str = Field(min_length=1, max_length=300)
