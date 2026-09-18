import json

from pydantic import ValidationError

from app.core.config import get_settings
from app.models.sms import SmsConversation, SmsMessage
from app.schemas.agent import AgentDecision
from app.services.tpi_client import TPIServiceError, generate_llm_text


class AgentUnavailable(RuntimeError):
    pass


class SmsAgent:
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
- Return only JSON matching this schema: {json.dumps(AgentDecision.model_json_schema())}
""".strip()
        settings = get_settings()
        try:
            content = await generate_llm_text(
                system_prompt="Return only the requested structured SMS decision as JSON.",
                user_prompt=prompt,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
            )
            return AgentDecision.model_validate(json.loads(content))
        except (json.JSONDecodeError, ValidationError, TPIServiceError) as exc:
            raise AgentUnavailable("TPI returned an invalid SMS decision") from exc
