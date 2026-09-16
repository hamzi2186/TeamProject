from __future__ import annotations

from typing import Any


def build_response_prompt(*, lead_identity: str, campaign_objective: str, recent_thread: str, client_kb: str) -> str:
    return f"""
You are writing a professional outbound email reply for a lead.

Lead identity:
{lead_identity}

Campaign objective:
{campaign_objective}

Recent conversation:
{recent_thread}

Client KB:
{client_kb}

Rules:
- Respond as a helpful and concise sales assistant.
- Do not invent company claims or facts not present in the supplied context.
- If the lead is unsubscribing or requests no further contact, stop.
- Keep it grounded in the lead's context and the campaign goal.
- Return JSON only with fields: subject, text_body, should_continue, outcome, reason, follow_up_at.
""""


def build_followup_prompt(*, lead_identity: str, campaign_objective: str, recent_thread: str, client_kb: str) -> str:
    return build_response_prompt(
        lead_identity=lead_identity,
        campaign_objective=campaign_objective,
        recent_thread=recent_thread,
        client_kb=client_kb,
    )


def summarize_email_event(event: dict[str, Any]) -> str:
    return f"Email event: {event.get('type')} from {event.get('from')}"
