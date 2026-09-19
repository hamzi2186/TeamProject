"""The Mailer PRD's definition of done: a 200 from the provider is not enough. Prove the whole
cycle (send, receive a reply, answer it automatically, persist the thread) across separate
transactions, the way a worker and a webhook would run it."""

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.calling import SeenWebhookEvent
from app.models.lead import Lead
from app.models.mailer import LeadStatusHistory, MailerBase
from app.modules.mailer.config import MailerSettings
from app.modules.mailer.contracts import DeliveryEvent, InboundEmailEvent, KBPassage, SentEmail
from app.modules.mailer.repository import MailerRepository
from app.modules.mailer.service import MailerService
from app.modules.mailer.thread import build_reply_to_address, extract_reply_to_token

SECRET, DOMAIN = "integration-secret", "reply.example.com"


class ScriptedLLM:
    def __init__(self, *responses):
        self.responses = list(responses)

    async def generate_text(self, *, system_prompt, user_prompt, temperature=0.3, max_tokens=900):
        return json.dumps(self.responses.pop(0))


class RecordingProvider:
    def __init__(self):
        self.sent = []

    async def send_email(self, *, to, subject, text_body, reply_to, in_reply_to=None, references=None,
                         idempotency_key=None, metadata=None):
        self.sent.append({"to": to, "subject": subject, "reply_to": reply_to, "in_reply_to": in_reply_to})
        number = len(self.sent)
        return SentEmail(provider="resend", provider_email_id=f"re_{number}",
                         from_address="outreach@us.example", internet_message_id=f"<sent-{number}@out.example>")


class StaticKB:
    async def search(self, *, user_id, website_id, query, top_k):
        return [KBPassage(content="Acme sells rocket skates.", source_url="https://acme.example")]


@pytest.mark.asyncio
async def test_send_reply_answer_and_the_thread_persists_across_transactions():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(MailerBase.metadata.create_all)
        await connection.run_sync(SeenWebhookEvent.__table__.create)
        await connection.run_sync(Lead.__table__.create)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    settings = MailerSettings(_env_file=None, mailer_reply_token_secret=SECRET, mailer_reply_to_domain=DOMAIN)
    llm = ScriptedLLM(
        {"subject": "Quick idea for Acme", "text_body": "Hi Sam, we help teams ship faster."},
        {"subject": "", "text_body": "Great question. Our skates ship in two days.", "should_continue": True,
         "outcome": "INTERESTED", "reason": "Asked about delivery", "follow_up_at": None},
    )
    provider = RecordingProvider()

    def service_for(session):
        return MailerService(repository=MailerRepository(session), llm=llm, email_provider=provider,
                             knowledge_base=StaticKB(), settings=settings)

    user_id, lead_id, other_user = uuid4(), uuid4(), uuid4()
    async with sessions() as session:
        session.add(Lead(id=lead_id, user_id=user_id, hubspot_connection_id=uuid4(), hubspot_contact_id="hs-1",
                         first_name="Sam", email="sam@lead.example", website_id=uuid4()))
        await session.commit()

    # 1. A worker sends the campaign email and commits.
    async with sessions() as session:
        sent = await service_for(session).start_conversation(
            user_id=user_id, lead_id=lead_id, campaign_id=uuid4(), campaign_objective="Book a demo"
        )
        await session.commit()
    assert sent.status == "sent" and len(provider.sent) == 1

    # 2. The lead replies to the address we sent from. This arrives as a separate webhook.
    reply_address = provider.sent[0]["reply_to"]
    assert extract_reply_to_token(reply_address) and reply_address.endswith(f"@{DOMAIN}")
    event = InboundEmailEvent(
        event_id="evt-1", provider_email_id="in-1", from_address="sam@lead.example", to_addresses=[reply_address],
        subject="Re: Quick idea for Acme", text_body="How fast can you deliver?",
        internet_message_id="<lead-1@lead.example>", in_reply_to="<sent-1@out.example>",
        references_header="<sent-1@out.example>", received_at=datetime.now(UTC),
    )
    async with sessions() as session:
        answered = await service_for(session).handle_inbound_email(event)
        await session.commit()
    assert (answered.status, answered.outcome) == ("replied", "INTERESTED")
    assert len(provider.sent) == 2 and provider.sent[1]["in_reply_to"] == "<lead-1@lead.example>"

    # 3. The provider retries the very same webhook. Nothing new happens.
    async with sessions() as session:
        assert (await service_for(session).handle_inbound_email(event)).status == "duplicate"
        await session.commit()
    assert len(provider.sent) == 2

    # 4. The provider reports the first email as delivered.
    async with sessions() as session:
        report = DeliveryEvent(event_id="d-1", provider_email_id="re_1", status="delivered")
        assert (await service_for(session).handle_delivery_event(report)).status == "delivery_updated"
        await session.commit()

    # 5. The dashboard reads it all back later, in a fresh session.
    async with sessions() as session:
        repo = MailerRepository(session)
        (conversation,) = await repo.list_conversations(user_id=user_id)
        emails = await repo.list_emails(user_id=user_id, conversation_id=conversation.id)
        assert [(e.direction, e.subject) for e in emails] == [
            ("OUTBOUND", "Quick idea for Acme"),
            ("INBOUND", "Re: Quick idea for Acme"),
            ("OUTBOUND", "Re: Quick idea for Acme"),
        ]
        assert emails[0].delivery_status == "delivered"
        assert emails[1].text_body == "How fast can you deliver?"
        assert emails[2].text_body == "Great question. Our skates ship in two days."
        assert (conversation.status, conversation.outcome, conversation.turn_count) == (
            "WAITING_FOR_LEAD", "INTERESTED", 2)
        rows = await session.scalars(select(LeadStatusHistory).order_by(LeadStatusHistory.created_at))
        assert [(r.new_status, r.source) for r in rows] == [("CONTACTING", "SYSTEM"), ("INTERESTED", "AI")]

        # Another tenant sees none of it.
        assert await repo.list_conversations(user_id=other_user) == []
        assert await repo.list_emails(user_id=other_user, conversation_id=conversation.id) == []
    await engine.dispose()
