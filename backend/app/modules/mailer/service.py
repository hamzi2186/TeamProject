from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.modules.mailer.contracts import AIEmailDecision, EmailDirection, EmailOutcome
from app.modules.mailer.exceptions import MailerTenantError, MailerValidationError
from app.modules.mailer.outcome import classify_stop_condition, compute_follow_up_at, should_continue_from_outcome
from app.modules.mailer.thread import correlate_email


class MailerService:
    def __init__(self, *, repository: Any | None = None, email_provider: Any | None = None, llm: Any | None = None) -> None:
        self.repository = repository
        self.email_provider = email_provider
        self.llm = llm

    async def validate_scope(self, *, user_id: UUID, lead_id: UUID | None = None, campaign_id: UUID | None = None, conversation_id: str | None = None) -> None:
        if user_id is None:
            raise MailerTenantError("user_id is required")
        if lead_id is None and campaign_id is None and conversation_id is None:
            raise MailerTenantError("At least one ownership scope must be provided")
        if self.repository is None:
            raise MailerTenantError("Repository ownership validation is unavailable")
        if hasattr(self.repository, "get_conversation_for_user"):
            match = await self.repository.get_conversation_for_user(user_id, lead_id=lead_id, campaign_id=campaign_id)
            if match is None and (lead_id is not None or campaign_id is not None):
                raise MailerTenantError("Requested Mailer resource is not owned by this tenant")
        elif lead_id is not None or campaign_id is not None:
            raise MailerTenantError("Requested Mailer resource is not owned by this tenant")

    async def open_conversation(self, *, user_id: UUID, lead_id: UUID, campaign_id: UUID | None, subject: str, status: str = "WAITING_FOR_LEAD") -> dict[str, Any]:
        if self.repository is None:
            return {
                "conversation_id": str(UUID(int=0)),
                "user_id": user_id,
                "lead_id": lead_id,
                "campaign_id": campaign_id,
                "subject": subject,
                "status": status,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
        return await self.repository.create_or_get_conversation(
            user_id=user_id,
            lead_id=lead_id,
            campaign_id=campaign_id,
            subject=subject,
            status=status,
        )

    async def process_webhook_event(self, event: dict[str, Any]) -> dict[str, Any]:
        if self.repository is None:
            return {"status": "processed", "event_id": event.get("id")}
        provider_event_id = str(event.get("id") or event.get("event_id") or "")
        if provider_event_id:
            created = await self.repository.record_webhook_event(provider_event_id=provider_event_id, payload=event)
            if created is False:
                return {"status": "duplicate", "event_id": provider_event_id}
        return {"status": "processed", "event_id": provider_event_id}

    async def correlate_inbound_email(self, email: dict[str, Any]) -> str | None:
        if self.repository is None:
            return None
        existing = await self.repository.list_recent_messages(conversation_id=email.get("conversation_id") or "")
        return await correlate_email(email, existing)

    async def normalize_inbound_payload(self, *, provider_payload: dict[str, Any], user_id: UUID, lead_id: UUID, campaign_id: UUID | None) -> dict[str, Any]:
        return {
            "conversation_id": provider_payload.get("conversation_id"),
            "user_id": user_id,
            "lead_id": lead_id,
            "campaign_id": campaign_id,
            "direction": EmailDirection.INBOUND,
            "from_address": provider_payload.get("from") or provider_payload.get("from_address"),
            "to_addresses": provider_payload.get("to") or [],
            "subject": provider_payload.get("subject"),
            "text_body": provider_payload.get("text") or provider_payload.get("text_body"),
            "html_body": provider_payload.get("html") or provider_payload.get("html_body"),
            "provider": "resend",
            "provider_email_id": provider_payload.get("email_id") or provider_payload.get("provider_email_id"),
            "internet_message_id": provider_payload.get("internet_message_id"),
            "in_reply_to": provider_payload.get("in_reply_to"),
            "references_header": provider_payload.get("references") or provider_payload.get("references_header"),
            "delivery_status": "received",
            "provider_payload": provider_payload,
            "sent_or_received_at": datetime.now(timezone.utc),
        }

    async def classify_outcome(self, *, lead_identity: str, campaign_objective: str, recent_thread: str, client_kb: str) -> AIEmailDecision:
        if self.llm is None:
            return AIEmailDecision(
                subject="Re: Follow up",
                text_body="Thanks for the reply. I’d be happy to continue the conversation.",
                should_continue=True,
                outcome="INTERESTED",
                reason="Fallback decision based on workflow context.",
                follow_up_at=None,
            )
        # This method is intentionally lightweight because the actual LLM adapter remains a shared TPI concern.
        decision = await self.llm.generate_json(
            system_prompt="You are a lead-scouting assistant.",
            user_prompt=f"Lead: {lead_identity}\nCampaign: {campaign_objective}\nThread: {recent_thread}\nKB: {client_kb}",
        )
        return AIEmailDecision.model_validate(decision)

    async def handle_stop_conditions(self, text: str | None, outcome: str | None) -> bool:
        if classify_stop_condition(text):
            return True
        if outcome in {EmailOutcome.DO_NOT_CONTACT, EmailOutcome.NOT_INTERESTED, EmailOutcome.FAILED}:
            return True
        return not should_continue_from_outcome(outcome)

    async def send_campaign_email(self, *, user_id: UUID, lead_id: UUID, campaign_id: UUID | None, subject: str, body: str, reply_to_token: str | None = None) -> dict[str, Any]:
        if self.email_provider is None:
            return {
                "conversation_id": str(UUID(int=0)),
                "user_id": user_id,
                "lead_id": lead_id,
                "campaign_id": campaign_id,
                "status": "queued",
                "provider_email_id": None,
                "subject": subject,
                "text_body": body,
                "reply_to_token": reply_to_token,
            }
        return await self.email_provider.send_email(
            user_id=user_id,
            lead_id=lead_id,
            campaign_id=campaign_id,
            subject=subject,
            body=body,
            reply_to_token=reply_to_token,
        )

    async def save_outbound_email(self, *, conversation_id: str, user_id: UUID, lead_id: UUID, campaign_id: UUID | None, subject: str, body: str, provider_email_id: str | None = None, provider_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.repository is None:
            return {"conversation_id": conversation_id, "user_id": user_id, "lead_id": lead_id, "campaign_id": campaign_id, "subject": subject, "text_body": body, "provider_email_id": provider_email_id, "provider_payload": provider_payload or {}}
        return await self.repository.save_email(
            conversation_id=conversation_id,
            user_id=user_id,
            lead_id=lead_id,
            campaign_id=campaign_id,
            direction=EmailDirection.OUTBOUND,
            from_address="noreply@trexmail.io",
            to_addresses=[],
            subject=subject,
            text_body=body,
            provider="resend",
            provider_email_id=provider_email_id,
            provider_payload=provider_payload or {},
            sent_or_received_at=datetime.now(timezone.utc),
        )

    async def save_inbound_email(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        if self.repository is None:
            return payload
        return await self.repository.save_email(**payload)

    async def process_inbound_email(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not payload.get("user_id") or not payload.get("lead_id"):
            raise MailerValidationError("Inbound payload is missing user_id or lead_id")
        if self.repository is None:
            return {"status": "processed", "payload": payload}
        await self.repository.record_history_event(
            user_id=payload["user_id"],
            lead_id=payload["lead_id"],
            campaign_id=payload.get("campaign_id"),
            event_type="mailer.inbound_received",
            payload=payload,
        )
        return {"status": "processed", "payload": payload}

    async def handle_bounce(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.repository is None:
            return {"status": "handled", "event": payload}
        outcome = payload.get("outcome") or "FAILED"
        return {"status": "handled", "outcome": outcome, "event": payload}

    async def finalize_outcome(self, *, outcome: str | None, reason: str | None) -> AIEmailDecision:
        normalized = outcome or "NO_RESPONSE"
        decision = AIEmailDecision(
            subject="Re: Follow up",
            text_body="Thanks for your response. I’ll keep the conversation moving.",
            should_continue=should_continue_from_outcome(normalized),
            outcome=normalized,
            reason=reason or "Lead response processed.",
            follow_up_at=compute_follow_up_at(normalized),
        )
        return decision
