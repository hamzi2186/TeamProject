from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypeVar
from uuid import UUID

from pydantic import BaseModel, ValidationError

from app.modules.mailer.config import MailerSettings, get_mailer_settings
from app.modules.mailer.contracts import (
    LLM,
    AIEmailDecision,
    ClientKnowledgeBase,
    DeliveryEvent,
    EmailDirection,
    EmailOutcome,
    EmailProvider,
    GeneratedEmail,
    InboundEmailEvent,
    KBPassage,
    SentEmail,
)
from app.modules.mailer.exceptions import (
    MailerConfigurationError,
    MailerProviderError,
    MailerStopCondition,
    MailerTenantError,
    MailerValidationError,
)
from app.modules.mailer.outcome import (
    classify_stop_condition,
    html_to_text,
    should_continue_from_outcome,
    strip_quoted_reply,
)
from app.modules.mailer.prompts import (
    SYSTEM_PROMPT,
    build_first_email_prompt,
    build_response_prompt,
    extract_json_object,
    format_kb,
    format_thread,
)
from app.modules.mailer.repository import MailerRepository
from app.modules.mailer.thread import (
    build_reply_to_address,
    correlate_email,
    extract_reply_to_token,
    make_reply_to_token,
    normalize_message_id,
    parse_message_ids,
    resolve_reply_to_token,
)

M = TypeVar("M", bound=BaseModel)

_CLOSED_STATUSES = {"CONCLUDED", "CANCELLED", "FAILED"}
_NO_REPLY_OUTCOMES = {EmailOutcome.DO_NOT_CONTACT, EmailOutcome.FAILED}
_DEFAULT_OBJECTIVE = "Start a helpful, low-pressure conversation about how we can help this lead."
# The campaign objective is not stored on the conversation, so the first email keeps it in its
# payload for the replies that follow.
_CONTEXT_KEY = "mailer_context"


@dataclass(frozen=True)
class MailerResult:
    """What a service call did.

    status is one of: sent, already_sent, replied, concluded, stopped, guardrail, recorded,
    duplicate, unmatched, delivery_updated, unknown_email.
    """

    status: str
    conversation_id: UUID | None = None
    outcome: str | None = None
    reason: str | None = None
    email_id: UUID | None = None
    follow_up_at: datetime | None = None


class MailerService:
    """Two-way email conversations grounded in each lead's Client KB.

    The caller owns the database transaction: this class flushes through the repository but never
    commits, so a failure anywhere leaves nothing half written and the event can be retried.
    """

    def __init__(
        self,
        *,
        repository: MailerRepository,
        llm: LLM,
        email_provider: EmailProvider,
        knowledge_base: ClientKnowledgeBase,
        settings: MailerSettings | None = None,
    ) -> None:
        self._repo = repository
        self._llm = llm
        self._email = email_provider
        self._kb = knowledge_base
        self._settings = settings or get_mailer_settings()

    # -- outbound ------------------------------------------------------------------------

    async def start_conversation(
        self,
        *,
        user_id: UUID,
        lead_id: UUID,
        campaign_id: UUID | None = None,
        campaign_objective: str | None = None,
    ) -> MailerResult:
        """Send the first email of a campaign to a lead.

        Safe to run twice for the same lead and campaign: the second call finds the email that
        was already sent and returns it instead of sending again.
        """
        self._require_reply_settings()
        lead = await self._repo.get_lead(user_id=user_id, lead_id=lead_id)
        if lead is None:
            raise MailerTenantError("Lead is not owned by this tenant")
        if not (lead.email or "").strip():
            raise MailerValidationError("The lead has no email address, so the Mailer cannot contact it")
        await self._refuse_if_do_not_contact(user_id, lead_id)

        conversation, created = await self._repo.open_conversation(
            user_id=user_id, lead_id=lead_id, campaign_id=campaign_id
        )
        if (conversation.status or "OPEN") in _CLOSED_STATUSES:
            raise MailerStopCondition(f"The conversation is {conversation.status.lower()}")
        if not created:
            earliest = await self._repo.list_emails(
                user_id=user_id, conversation_id=conversation.id, limit=1
            )
            if earliest and earliest[0].direction == EmailDirection.OUTBOUND:
                return MailerResult("already_sent", conversation.id, email_id=earliest[0].id)

        objective = (campaign_objective or "").strip() or _DEFAULT_OBJECTIVE
        passages = await self._search_kb(lead, objective)
        generated = await self._generate(
            GeneratedEmail,
            build_first_email_prompt(
                lead_identity=_identity(lead),
                campaign_objective=objective,
                client_kb=format_kb(passages),
            ),
        )
        sent = await self._send(
            to=lead.email,
            conversation_id=conversation.id,
            subject=generated.subject,
            text_body=generated.text_body,
            in_reply_to=None,
            references=None,
            # Stable across retries and across a rolled-back conversation id, so the provider
            # can drop a repeat if we sent but failed to save.
            idempotency_key=f"mailer:first:{user_id}:{lead_id}:{campaign_id}",
        )
        email = await self._store_outbound(
            conversation, lead.email, generated.subject, generated.text_body, sent,
            in_reply_to=None, references=None, context={"campaign_objective": objective},
        )
        await self._repo.update_conversation(
            user_id=user_id,
            conversation_id=conversation.id,
            status="WAITING_FOR_LEAD",
            add_turn=True,
            provider_thread_id=sent.internet_message_id or sent.provider_email_id,
        )
        await self._repo.record_status_change(
            user_id=user_id,
            lead_id=lead_id,
            campaign_id=campaign_id,
            previous_status=None,
            new_status="CONTACTING",
            source="SYSTEM",
            reason="First email sent",
        )
        return MailerResult("sent", conversation.id, email_id=email.id)

    # -- inbound -------------------------------------------------------------------------

    async def handle_inbound_email(self, event: InboundEmailEvent) -> MailerResult:
        """Record a lead's reply and, unless a stop condition applies, answer it."""
        conversation = await self._correlate(event)
        if conversation is None:
            # Not marked as seen, so a provider retry can still match once our own record of
            # the outbound email has been committed.
            return MailerResult("unmatched", reason="No conversation matches this reply")
        user_id, lead_id = conversation.user_id, conversation.lead_id
        lead = await self._repo.get_lead(user_id=user_id, lead_id=lead_id)
        if lead is None:
            return MailerResult("unmatched", conversation.id, reason="The lead no longer exists")
        if not await self._repo.record_webhook_event(
            provider=event.provider, provider_event_id=event.event_id
        ):
            return MailerResult("duplicate", conversation.id)

        inbound, created = await self._repo.add_email(
            conversation_id=conversation.id,
            user_id=user_id,
            lead_id=lead_id,
            direction=EmailDirection.INBOUND,
            from_address=event.from_address,
            to_addresses=event.to_addresses,
            subject=event.subject,
            text_body=event.text_body,
            html_body=event.html_body,
            provider=event.provider,
            provider_email_id=event.provider_email_id,
            internet_message_id=event.internet_message_id,
            in_reply_to=event.in_reply_to,
            references_header=event.references_header,
            delivery_status="received",
            provider_payload=event.raw_payload,
            sent_or_received_at=event.received_at,
        )
        if not created:
            return MailerResult("duplicate", conversation.id)
        if (conversation.status or "OPEN") in _CLOSED_STATUSES:
            return MailerResult("recorded", conversation.id, reason="The conversation is closed")

        body = _plain_text(event)
        if classify_stop_condition(body):
            await self._conclude(
                conversation, outcome=EmailOutcome.DO_NOT_CONTACT,
                reason="The lead asked to stop receiving email", source="SYSTEM",
            )
            return MailerResult("stopped", conversation.id, outcome=EmailOutcome.DO_NOT_CONTACT)
        if (conversation.turn_count or 0) >= self._settings.max_autonomous_text_turns:
            await self._conclude(
                conversation, outcome=EmailOutcome.FOLLOW_UP_REQUIRED, source="SYSTEM",
                reason="Maximum autonomous turns reached; a person should take over",
            )
            return MailerResult(
                "guardrail", conversation.id, outcome=EmailOutcome.FOLLOW_UP_REQUIRED
            )

        thread = await self._repo.list_recent_emails(
            user_id=user_id,
            conversation_id=conversation.id,
            limit=self._settings.mailer_thread_context_emails,
        )
        objective = await self._campaign_objective(user_id, conversation.id)
        passages = await self._search_kb(lead, _strip_for_search(body, event.subject))
        decision = await self._generate(
            AIEmailDecision,
            build_response_prompt(
                lead_identity=_identity(lead),
                campaign_objective=objective,
                recent_thread=format_thread(thread),
                client_kb=format_kb(passages),
            ),
        )
        return await self._apply_decision(conversation, lead, event, thread, decision)

    async def _apply_decision(
        self, conversation: Any, lead: Any, event: InboundEmailEvent, thread: list[Any],
        decision: AIEmailDecision,
    ) -> MailerResult:
        outcome = decision.outcome
        keep_open = decision.should_continue and should_continue_from_outcome(outcome)
        previous = conversation.outcome or "CONTACTING"
        email_id = None
        if outcome not in _NO_REPLY_OUTCOMES and decision.text_body:
            subject = _reply_subject(decision.subject, thread)
            references = _references(event)
            in_reply_to = _bracket(event.internet_message_id)
            sent = await self._send(
                to=lead.email,
                conversation_id=conversation.id,
                subject=subject,
                text_body=decision.text_body,
                in_reply_to=in_reply_to,
                references=references,
                idempotency_key=f"mailer:reply:{event.provider}:{event.event_id}",
            )
            email = await self._store_outbound(
                conversation, lead.email, subject, decision.text_body, sent,
                in_reply_to=in_reply_to, references=references, context=None,
            )
            email_id = email.id

        follow_up_at = _future(decision.follow_up_at)
        if not keep_open:
            status = "CONCLUDED"
        elif outcome == EmailOutcome.FOLLOW_UP_REQUIRED and follow_up_at:
            status = "SCHEDULED_FOLLOWUP"
        else:
            status = "WAITING_FOR_LEAD"
        await self._repo.update_conversation(
            user_id=conversation.user_id,
            conversation_id=conversation.id,
            status=status,
            outcome=outcome.value,
            add_turn=email_id is not None,
            conclude=not keep_open,
        )
        if outcome.value != previous:
            await self._repo.record_status_change(
                user_id=conversation.user_id,
                lead_id=conversation.lead_id,
                campaign_id=conversation.campaign_id,
                previous_status=previous,
                new_status=outcome.value,
                source="AI",
                reason=decision.reason or None,
            )
        return MailerResult(
            "replied" if keep_open else "concluded",
            conversation.id,
            outcome=outcome.value,
            reason=decision.reason or None,
            email_id=email_id,
            follow_up_at=follow_up_at,
        )

    async def handle_delivery_event(self, event: DeliveryEvent) -> MailerResult:
        """Apply a delivery report, and stop the conversation on a hard bounce or a complaint."""
        if not await self._repo.record_webhook_event(
            provider=event.provider, provider_event_id=event.event_id
        ):
            return MailerResult("duplicate")
        email = await self._repo.update_delivery_status(
            provider=event.provider,
            provider_email_id=event.provider_email_id,
            delivery_status=event.status,
        )
        if email is None:
            return MailerResult("unknown_email")
        status = event.status.strip().lower()
        complaint = status == "complained"
        hard_bounce = status in {"bounced", "failed"} and event.permanent
        conversation = await self._repo.get_conversation(
            user_id=email.user_id, conversation_id=email.conversation_id
        )
        if (
            not (complaint or hard_bounce)
            or conversation is None
            or (conversation.status or "OPEN") in _CLOSED_STATUSES
        ):
            return MailerResult("delivery_updated", email.conversation_id, email_id=email.id)
        if complaint:
            await self._conclude(
                conversation, outcome=EmailOutcome.DO_NOT_CONTACT, source="SYSTEM",
                reason="The recipient marked the email as spam",
            )
            outcome = EmailOutcome.DO_NOT_CONTACT
        else:
            await self._conclude(
                conversation, outcome=EmailOutcome.FAILED, source="SYSTEM", status="FAILED",
                reason="The email bounced permanently",
            )
            outcome = EmailOutcome.FAILED
        return MailerResult("stopped", conversation.id, outcome=outcome, email_id=email.id)

    # -- internals -----------------------------------------------------------------------

    def _require_reply_settings(self) -> None:
        if not self._settings.mailer_reply_token_secret or not self._settings.mailer_reply_to_domain:
            raise MailerConfigurationError(
                "MAILER_REPLY_TOKEN_SECRET and MAILER_REPLY_TO_DOMAIN must be set before "
                "the Mailer can send email"
            )

    def _reply_address(self, conversation_id: UUID) -> str:
        self._require_reply_settings()
        token = make_reply_to_token(conversation_id, self._settings.mailer_reply_token_secret)
        return build_reply_to_address(
            mailbox=self._settings.mailer_reply_to_mailbox,
            domain=self._settings.mailer_reply_to_domain,
            token=token,
        )

    async def _refuse_if_do_not_contact(self, user_id: UUID, lead_id: UUID) -> None:
        conversations = await self._repo.list_conversations(
            user_id=user_id, lead_id=lead_id, limit=200
        )
        if any(item.outcome == EmailOutcome.DO_NOT_CONTACT for item in conversations):
            raise MailerStopCondition("The lead has asked not to be contacted")

    async def _search_kb(self, lead: Any, query: str) -> list[KBPassage]:
        return await self._kb.search(
            user_id=lead.user_id,
            website_id=lead.website_id,
            query=query,
            top_k=self._settings.mailer_kb_top_k,
        )

    async def _generate(self, model_cls: type[M], user_prompt: str) -> M:
        prompt = user_prompt
        for _ in range(2):
            raw = await self._llm.generate_text(
                system_prompt=SYSTEM_PROMPT, user_prompt=prompt, temperature=0.3, max_tokens=900
            )
            try:
                return model_cls.model_validate(extract_json_object(raw))
            except (ValueError, ValidationError):
                prompt = (
                    user_prompt
                    + "\n\nYour previous answer was not valid. "
                    "Reply with only the JSON object described above."
                )
        raise MailerProviderError("The model did not return a usable response", retryable=True)

    async def _send(
        self, *, to: str, conversation_id: UUID, subject: str, text_body: str,
        in_reply_to: str | None, references: str | None, idempotency_key: str,
    ) -> SentEmail:
        return await self._email.send_email(
            to=to,
            subject=subject,
            text_body=text_body,
            reply_to=self._reply_address(conversation_id),
            in_reply_to=in_reply_to,
            references=references,
            idempotency_key=idempotency_key,
            metadata={"conversation_id": str(conversation_id)},
        )

    async def _store_outbound(
        self, conversation: Any, to: str, subject: str, text_body: str, sent: SentEmail, *,
        in_reply_to: str | None, references: str | None, context: dict[str, Any] | None,
    ) -> Any:
        payload = dict(sent.payload)
        if context:
            payload[_CONTEXT_KEY] = context
        email, _ = await self._repo.add_email(
            conversation_id=conversation.id,
            user_id=conversation.user_id,
            lead_id=conversation.lead_id,
            direction=EmailDirection.OUTBOUND,
            from_address=sent.from_address,
            to_addresses=[to],
            subject=subject,
            text_body=text_body,
            provider=sent.provider,
            provider_email_id=sent.provider_email_id,
            internet_message_id=sent.internet_message_id,
            in_reply_to=in_reply_to,
            references_header=references,
            delivery_status=sent.status,
            provider_payload=payload,
        )
        return email

    async def _conclude(
        self, conversation: Any, *, outcome: EmailOutcome, reason: str, source: str,
        status: str = "CONCLUDED",
    ) -> None:
        previous = conversation.outcome or "CONTACTING"
        await self._repo.update_conversation(
            user_id=conversation.user_id,
            conversation_id=conversation.id,
            status=status,
            outcome=outcome.value,
            conclude=True,
        )
        await self._repo.record_status_change(
            user_id=conversation.user_id,
            lead_id=conversation.lead_id,
            campaign_id=conversation.campaign_id,
            previous_status=previous,
            new_status=outcome.value,
            source=source,
            reason=reason,
        )

    async def _campaign_objective(self, user_id: UUID, conversation_id: UUID) -> str:
        first = await self._repo.list_emails(user_id=user_id, conversation_id=conversation_id, limit=1)
        context = (first[0].provider_payload or {}).get(_CONTEXT_KEY) if first else None
        objective = (context or {}).get("campaign_objective") if isinstance(context, dict) else None
        return objective or _DEFAULT_OBJECTIVE

    async def _correlate(self, event: InboundEmailEvent) -> Any | None:
        """Find the conversation a reply belongs to. The tenant comes from the matched row."""
        candidates: list[dict[str, Any]] = []
        token = next(
            (found for address in event.to_addresses if (found := extract_reply_to_token(address))),
            None,
        )
        conversation_id = resolve_reply_to_token(token, self._settings.mailer_reply_token_secret)
        if conversation_id is not None:
            verified = await self._repo.get_conversation_by_verified_id(conversation_id)
            if verified is not None:
                candidates.append({"conversation_id": str(verified.id), "reply_to_token": token})
        message_ids = parse_message_ids(event.in_reply_to) + parse_message_ids(event.references_header)
        candidates += await self._repo.find_correlation_candidates(
            message_ids=message_ids, provider_email_id=event.provider_email_id
        )
        matched = await correlate_email(
            {
                "to_addresses": event.to_addresses,
                "in_reply_to": event.in_reply_to,
                "references_header": event.references_header,
                "provider_email_id": event.provider_email_id,
                "from_address": event.from_address,
            },
            candidates,
        )
        if matched is None:
            return None
        return await self._repo.get_conversation_by_verified_id(UUID(matched))


def _identity(lead: Any) -> str:
    name = (lead.display_name or " ".join(filter(None, [lead.first_name, lead.last_name]))).strip()
    return ", ".join(part for part in (name or "the lead", lead.email, lead.website_url) if part)


def _plain_text(event: InboundEmailEvent) -> str:
    return event.text_body if (event.text_body or "").strip() else html_to_text(event.html_body)


def _strip_for_search(body: str, subject: str | None) -> str:
    return strip_quoted_reply(body) or (subject or "")


def _bracket(message_id: str | None) -> str | None:
    normalized = normalize_message_id(message_id)
    return f"<{normalized}>" if normalized else None


def _references(event: InboundEmailEvent) -> str | None:
    ids: list[str] = []
    for message_id in parse_message_ids(event.references_header) + parse_message_ids(
        event.internet_message_id
    ):
        if message_id not in ids:
            ids.append(message_id)
    return " ".join(f"<{message_id}>" for message_id in ids) or None


def _reply_subject(suggested: str, thread: list[Any]) -> str:
    subject = suggested.strip()
    if not subject:
        last = next((email.subject for email in reversed(thread) if email.subject), "")
        subject = last.strip() or "your message"
    return subject if subject.lower().startswith("re:") else f"Re: {subject}"


def _future(moment: datetime | None) -> datetime | None:
    if moment is None:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment if moment > datetime.now(UTC) else None
