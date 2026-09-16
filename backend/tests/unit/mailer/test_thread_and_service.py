from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.modules.mailer.contracts import AIEmailDecision
from app.modules.mailer.exceptions import MailerTenantError
from app.modules.mailer.thread import correlate_email, extract_reply_to_token, parse_address_list
from app.modules.mailer.service import MailerService


class DummyRepository:
    def __init__(self):
        self.conversations = {}
        self.emails = []
        self.webhook_events = set()

    async def create_or_get_conversation(self, **kwargs):
        cid = kwargs.get("conversation_id") or str(uuid4())
        self.conversations[cid] = {**kwargs, "conversation_id": cid}
        return self.conversations[cid]

    async def save_email(self, **kwargs):
        self.emails.append(kwargs)
        return kwargs

    async def get_conversation_by_id(self, conversation_id):
        return self.conversations.get(conversation_id)

    async def record_webhook_event(self, *, provider_event_id, **_kwargs):
        if provider_event_id in self.webhook_events:
            return False
        self.webhook_events.add(provider_event_id)
        return True

    async def list_recent_messages(self, *, conversation_id, limit=10):
        return [email for email in self.emails if email.get("conversation_id") == conversation_id][-limit:]

    async def get_conversation_for_user(self, user_id, lead_id=None, campaign_id=None):
        return next(
            (
                item
                for item in self.conversations.values()
                if item.get("user_id") == user_id
                and (lead_id is None or item.get("lead_id") == lead_id)
                and (campaign_id is None or item.get("campaign_id") == campaign_id)
            ),
            None,
        )


@pytest.mark.asyncio
async def test_reply_to_token_resolution():
    payload = "mailer+abc123@reply.example.com"
    assert extract_reply_to_token(payload) == "abc123"
    assert extract_reply_to_token("sender@example.com") is None


@pytest.mark.asyncio
async def test_thread_correlation_priority():
    user_id = uuid4()
    lead_id = uuid4()
    campaign_id = uuid4()
    conversation_id = str(uuid4())
    existing = [{
        "id": str(uuid4()),
        "conversation_id": conversation_id,
        "user_id": user_id,
        "lead_id": lead_id,
        "campaign_id": campaign_id,
        "provider_email_id": "msg-100",
        "internet_message_id": "<thread-100@example.com>",
        "in_reply_to": "<old@example.com>",
        "references_header": "<ref-1@example.com>",
        "reply_to_token": "token-777",
        "from_address": "lead@example.com",
        "direction": "outbound",
        "timestamp": datetime.now(timezone.utc),
    }]
    email = {
        "user_id": user_id,
        "lead_id": lead_id,
        "campaign_id": campaign_id,
        "from_address": "lead@example.com",
        "to_addresses": ["mailer+token-777@reply.example.com"],
        "provider_email_id": "msg-999",
        "internet_message_id": "<new@example.com>",
        "in_reply_to": "<old@example.com>",
        "references_header": "<ref-9@example.com>",
    }
    assert await correlate_email(email, existing) == conversation_id


@pytest.mark.asyncio
async def test_webhook_idempotency_and_bounce_status():
    repo = DummyRepository()
    service = MailerService(repository=repo, email_provider=None)
    first = await service.process_webhook_event({"provider": "resend", "id": "evt-1", "type": "email.bounced", "data": {"email_id": "msg-1"}})
    second = await service.process_webhook_event({"provider": "resend", "id": "evt-1", "type": "email.bounced", "data": {"email_id": "msg-1"}})
    assert first["status"] == "processed"
    assert second["status"] == "duplicate"


@pytest.mark.asyncio
async def test_mailer_tenant_isolation():
    service = MailerService(repository=DummyRepository(), email_provider=None)
    with pytest.raises(MailerTenantError):
        await service.validate_scope(user_id=uuid4(), lead_id=uuid4(), campaign_id=uuid4())


@pytest.mark.asyncio
async def test_structured_ai_output():
    decision = AIEmailDecision(
        subject="Re: Test",
        text_body="Thanks for the reply.",
        should_continue=True,
        outcome="INTERESTED",
        reason="Lead asked about pricing.",
        follow_up_at=None,
    )
    assert decision.outcome == "INTERESTED"
    assert decision.should_continue is True


@pytest.mark.asyncio
async def test_parse_address_list_handles_multiple_recipients():
    assert parse_address_list("one@example.com, two@example.com") == ["one@example.com", "two@example.com"]
    assert parse_address_list(None) == []
