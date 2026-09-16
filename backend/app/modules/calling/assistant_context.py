from dataclasses import dataclass


@dataclass(frozen=True)
class AssistantContext:
    lead_id: str
    lead_name: str
    campaign_goal: str
    recent_context: str = ""

    def as_variables(self) -> dict[str, str]:
        return {
            "lead_id": self.lead_id,
            "lead_name": self.lead_name,
            "campaign_goal": self.campaign_goal,
            "recent_context": self.recent_context,
        }
