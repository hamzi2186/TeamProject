import json

from groq import AsyncGroq
from pydantic import ValidationError

from app.core.config import get_settings
from app.models.sms import SmsConversation, SmsMessage
from app.schemas.agent import AgentDecision


class AgentUnavailable(RuntimeError):
    pass


class SmsAgent:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.groq_api_key:
            raise AgentUnavailable("GROQ_API_KEY is not configured")
        self.settings = settings
        self.client = AsyncGroq(api_key=settings.groq_api_key)

    async def decide(
        self, conversation: SmsConversation, history: list[SmsMessage]
    ) -> AgentDecision:
        transcript = "\n".join(
            f"{'Lead' if item.direction == 'INBOUND' else 'Agent'}: {item.body}"
            for item in history[-20:]
        )
        prompt = f"""
You write concise, natural SMS replies for an outreach campaign.

Contact: {conversation.contact_name}
Campaign objective: {conversation.campaign_objective}
Initial template: {conversation.message_template}
Approved knowledge context:
{conversation.knowledge_context or 'No knowledge context is available.'}

Conversation:
{transcript or 'No messages yet.'}

Rules:
- Every factual product claim must be directly supported by the approved knowledge context.
- Do not infer features, workflows, pricing, or guarantees from the product name or objective.
- If the approved context does not answer a question,
  say that the detail can be covered in the demo.
- Keep the message under 480 characters and suitable for SMS.
- Do not add markdown.
- Respect a clear rejection immediately.
- Classify a terminal outcome only when the lead's message supports it.
- Use null outcome when the conversation should continue.
""".strip()
        schema = AgentDecision.model_json_schema()
        response = await self.client.chat.completions.create(
            model=self.settings.groq_model,
            temperature=self.settings.groq_temperature,
            max_completion_tokens=self.settings.groq_max_completion_tokens,
            messages=[
                {
                    "role": "system",
                    "content": "Return only the requested structured SMS decision.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "sms_agent_decision",
                    "strict": True,
                    "schema": schema,
                },
            },
        )
        content = response.choices[0].message.content
        if not content:
            raise AgentUnavailable("Groq returned an empty decision")
        try:
            return AgentDecision.model_validate(json.loads(content))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise AgentUnavailable("Groq returned an invalid SMS decision") from exc
