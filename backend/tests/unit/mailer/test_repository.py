import asyncio
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.models.calling import SeenWebhookEvent
from app.models.lead import Lead
from app.models.mailer import Email, EmailConversation, MailerBase
from app.modules.mailer.exceptions import MailerTenantError, MailerValidationError
from app.modules.mailer.repository import (
    MailerRepository,
    _webhook_event_insert,
    should_apply_delivery_status,
)
from app.modules.mailer.thread import (
    build_reply_to_address,
    correlate_email,
    extract_reply_to_token,
    make_reply_to_token,
    resolve_reply_to_token,
)


async def _reload(db, conversation_id):
    return await db.scalar(
        select(EmailConversation)
        .where(EmailConversation.id == conversation_id)
        .execution_options(populate_existing=True)
    )


async def _send(repo, conversation, **fields):
    defaults = {
        "conversation_id": conversation.id,
        "user_id": conversation.user_id,
        "lead_id": conversation.lead_id,
        "direction": "OUTBOUND",
    }
    email, _ = await repo.add_email(**{**defaults, **fields})
    return email


# -- conversations ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_open_conversation_creates_one_per_lead_and_campaign(repo):
    user, lead, campaign = uuid4(), uuid4(), uuid4()
    first, created = await repo.open_conversation(user_id=user, lead_id=lead, campaign_id=campaign)
    again, created_again = await repo.open_conversation(
        user_id=user, lead_id=lead, campaign_id=campaign
    )
    assert created and not created_again and again.id == first.id
    assert (first.channel, first.status, first.turn_count) == ("EMAIL", "OPEN", 0)

    other_campaign, created = await repo.open_conversation(
        user_id=user, lead_id=lead, campaign_id=uuid4()
    )
    assert created and other_campaign.id != first.id

    # A conversation with no campaign must still be found again, not duplicated on every call.
    no_campaign, created = await repo.open_conversation(user_id=user, lead_id=lead)
    same, created_again = await repo.open_conversation(user_id=user, lead_id=lead)
    assert created and not created_again and same.id == no_campaign.id

    other_tenant, created = await repo.open_conversation(
        user_id=uuid4(), lead_id=lead, campaign_id=campaign
    )
    assert created and other_tenant.id != first.id


@pytest.mark.asyncio
async def test_conversations_are_scoped_to_the_tenant_and_the_email_channel(repo, db):
    user, lead = uuid4(), uuid4()
    sms = EmailConversation(id=uuid4(), user_id=user, lead_id=lead, channel="SMS", status="OPEN")
    db.add(sms)
    await db.flush()

    mine, created = await repo.open_conversation(user_id=user, lead_id=lead)
    assert created and mine.id != sms.id  # an SMS thread with the same lead is not reused

    assert (await repo.get_conversation(user_id=user, conversation_id=mine.id)).id == mine.id
    assert await repo.get_conversation(user_id=uuid4(), conversation_id=mine.id) is None
    assert await repo.get_conversation(user_id=user, conversation_id=sms.id) is None
    assert await repo.get_conversation_by_verified_id(sms.id) is None
    assert (await repo.get_conversation_by_verified_id(mine.id)).user_id == user
    assert [c.id for c in await repo.list_conversations(user_id=user)] == [mine.id]
    assert await repo.list_conversations(user_id=uuid4()) == []


@pytest.mark.asyncio
async def test_list_conversations_filters_orders_and_pages(repo, db):
    user, lead, campaign = uuid4(), uuid4(), uuid4()
    rows = [
        EmailConversation(id=uuid4(), user_id=user, lead_id=lead, campaign_id=campaign,
                          channel="EMAIL", status="OPEN", updated_at=datetime(2026, 1, 1)),
        EmailConversation(id=uuid4(), user_id=user, lead_id=uuid4(), campaign_id=None,
                          channel="EMAIL", status="CONCLUDED", updated_at=datetime(2026, 3, 1)),
        EmailConversation(id=uuid4(), user_id=user, lead_id=uuid4(), campaign_id=None,
                          channel="EMAIL", status="OPEN", updated_at=datetime(2026, 2, 1)),
    ]
    db.add_all(rows)
    await db.flush()
    oldest, newest, middle = rows

    assert [c.id for c in await repo.list_conversations(user_id=user)] == [
        newest.id, middle.id, oldest.id,
    ]
    assert [c.id for c in await repo.list_conversations(user_id=user, status="OPEN")] == [
        middle.id, oldest.id,
    ]
    assert [c.id for c in await repo.list_conversations(user_id=user, lead_id=oldest.lead_id)] == [
        oldest.id,
    ]
    assert [c.id for c in await repo.list_conversations(user_id=user, campaign_id=campaign)] == [
        oldest.id,
    ]
    assert [c.id for c in await repo.list_conversations(user_id=user, limit=1, offset=1)] == [
        middle.id,
    ]


@pytest.mark.asyncio
async def test_update_conversation_counts_turns_and_concludes(repo, db):
    conversation, _ = await repo.open_conversation(user_id=uuid4(), lead_id=uuid4())
    user = conversation.user_id

    updated = await repo.update_conversation(
        user_id=user, conversation_id=conversation.id, status="WAITING_FOR_LEAD", add_turn=True
    )
    assert (updated.status, updated.turn_count) == ("WAITING_FOR_LEAD", 1)
    updated = await repo.update_conversation(
        user_id=user, conversation_id=conversation.id, add_turn=True
    )
    assert updated.turn_count == 2 and updated.concluded_at is None

    updated = await repo.update_conversation(
        user_id=user, conversation_id=conversation.id, status="CONCLUDED",
        outcome="DO_NOT_CONTACT", conclude=True, provider_thread_id="thread-1",
    )
    assert (updated.status, updated.outcome, updated.provider_thread_id) == (
        "CONCLUDED", "DO_NOT_CONTACT", "thread-1",
    )
    assert updated.concluded_at is not None and updated.turn_count == 2

    assert await repo.update_conversation(
        user_id=user, conversation_id=conversation.id
    ) is not None  # no-op update still returns the row


@pytest.mark.asyncio
async def test_update_conversation_refuses_another_tenant(repo, db):
    conversation, _ = await repo.open_conversation(user_id=uuid4(), lead_id=uuid4())
    result = await repo.update_conversation(
        user_id=uuid4(), conversation_id=conversation.id, status="CONCLUDED", add_turn=True
    )
    assert result is None
    untouched = await _reload(db, conversation.id)
    assert (untouched.status, untouched.turn_count) == ("OPEN", 0)


# -- emails ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_email_stores_every_field_and_lists_the_thread_in_order(repo, db):
    conversation, _ = await repo.open_conversation(user_id=uuid4(), lead_id=uuid4())
    sent = await _send(
        repo, conversation, from_address="us@example.com", to_addresses=["lead@example.com"],
        subject="Hello", text_body="Hi", html_body="<p>Hi</p>", provider="resend",
        provider_email_id="re_1", internet_message_id="<a@out>", delivery_status="queued",
        provider_payload={"id": "re_1"}, sent_or_received_at=datetime(2026, 1, 1, 9),
    )
    reply = await _send(
        repo, conversation, direction="INBOUND", from_address="lead@example.com",
        in_reply_to="<a@out>", references_header="<a@out>", delivery_status="received",
        sent_or_received_at=datetime(2026, 1, 1, 10),
    )
    thread = await repo.list_emails(user_id=conversation.user_id, conversation_id=conversation.id)
    assert [e.id for e in thread] == [sent.id, reply.id]
    assert thread[0].to_addresses == ["lead@example.com"]
    assert thread[0].provider_payload == {"id": "re_1"}
    assert thread[1].in_reply_to == "<a@out>"
    assert await repo.list_emails(user_id=uuid4(), conversation_id=conversation.id) == []


@pytest.mark.asyncio
async def test_add_email_is_idempotent_on_the_provider_id(repo):
    conversation, _ = await repo.open_conversation(user_id=uuid4(), lead_id=uuid4())
    kwargs = dict(
        conversation_id=conversation.id, user_id=conversation.user_id,
        lead_id=conversation.lead_id, direction="OUTBOUND", provider="resend",
        provider_email_id="re_dup",
    )
    first, created = await repo.add_email(**kwargs)
    again, created_again = await repo.add_email(**kwargs)
    assert created and not created_again and again.id == first.id
    thread = await repo.list_emails(user_id=conversation.user_id, conversation_id=conversation.id)
    assert len(thread) == 1


@pytest.mark.asyncio
async def test_add_email_enforces_tenant_lead_and_direction(repo):
    conversation, _ = await repo.open_conversation(user_id=uuid4(), lead_id=uuid4())
    common = dict(conversation_id=conversation.id, direction="OUTBOUND")

    with pytest.raises(MailerTenantError):
        await repo.add_email(user_id=uuid4(), lead_id=conversation.lead_id, **common)
    with pytest.raises(MailerValidationError):
        await repo.add_email(user_id=conversation.user_id, lead_id=uuid4(), **common)
    for bad in ("outbound", "SIDEWAYS", ""):
        with pytest.raises(MailerValidationError):
            await repo.add_email(
                conversation_id=conversation.id, user_id=conversation.user_id,
                lead_id=conversation.lead_id, direction=bad,
            )
    assert await repo.list_emails(
        user_id=conversation.user_id, conversation_id=conversation.id
    ) == []


@pytest.mark.asyncio
async def test_adding_an_email_bumps_the_conversation_so_it_sorts_first(repo, db):
    conversation, _ = await repo.open_conversation(user_id=uuid4(), lead_id=uuid4())
    before = (await _reload(db, conversation.id)).updated_at
    await asyncio.sleep(0.02)
    await _send(repo, conversation)
    assert (await _reload(db, conversation.id)).updated_at > before


@pytest.mark.asyncio
async def test_list_recent_emails_returns_the_latest_oldest_first(repo):
    conversation, _ = await repo.open_conversation(user_id=uuid4(), lead_id=uuid4())
    for hour in range(5):
        await _send(repo, conversation, subject=f"m{hour}",
                    sent_or_received_at=datetime(2026, 1, 1, hour))
    recent = await repo.list_recent_emails(
        user_id=conversation.user_id, conversation_id=conversation.id, limit=3
    )
    assert [e.subject for e in recent] == ["m2", "m3", "m4"]
    assert await repo.list_recent_emails(user_id=uuid4(), conversation_id=conversation.id) == []


# -- correlating an inbound reply ------------------------------------------------------


@pytest.mark.asyncio
async def test_a_reply_is_traced_back_to_its_conversation_and_tenant(repo):
    conversation, _ = await repo.open_conversation(user_id=uuid4(), lead_id=uuid4())
    await _send(repo, conversation, provider="resend", provider_email_id="re_1",
                internet_message_id="<sent-1@out.example>")

    candidates = await repo.find_correlation_candidates(message_ids=["sent-1@out.example"])
    assert [c["conversation_id"] for c in candidates] == [str(conversation.id)]
    assert candidates[0]["user_id"] == conversation.user_id

    reply = {"in_reply_to": "<sent-1@out.example>", "references_header": "<root@x> <sent-1@out.example>"}
    assert await correlate_email(reply, candidates) == str(conversation.id)

    by_provider = await repo.find_correlation_candidates(message_ids=[], provider_email_id="re_1")
    assert [c["conversation_id"] for c in by_provider] == [str(conversation.id)]
    assert await repo.find_correlation_candidates(message_ids=["nobody@x"]) == []
    assert await repo.find_correlation_candidates(message_ids=[]) == []


@pytest.mark.asyncio
async def test_correlation_ignores_emails_from_other_channels(repo, db):
    sms = EmailConversation(id=uuid4(), user_id=uuid4(), lead_id=uuid4(), channel="SMS")
    db.add(sms)
    await db.flush()
    db.add(Email(id=uuid4(), conversation_id=sms.id, user_id=sms.user_id, lead_id=sms.lead_id,
                 direction="OUTBOUND", internet_message_id="<sms-1@x>"))
    await db.flush()
    assert await repo.find_correlation_candidates(message_ids=["<sms-1@x>"]) == []


@pytest.mark.asyncio
async def test_a_signed_reply_to_address_leads_to_the_owning_tenant(repo):
    secret = "test-signing-secret"
    conversation, _ = await repo.open_conversation(user_id=uuid4(), lead_id=uuid4())
    address = build_reply_to_address(
        mailbox="mailer", domain="reply.example.com",
        token=make_reply_to_token(conversation.id, secret),
    )
    found = await repo.get_conversation_by_verified_id(
        resolve_reply_to_token(extract_reply_to_token(address), secret)
    )
    assert found.id == conversation.id and found.user_id == conversation.user_id

    forged = f"mailer+{make_reply_to_token(conversation.id, 'attacker')}@reply.example.com"
    assert resolve_reply_to_token(extract_reply_to_token(forged), secret) is None


# -- delivery events -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("current", "new", "expected"),
    [
        (None, "sent", True), ("queued", "sent", True), ("sent", "delivered", True),
        ("delivered", "sent", False), ("delivered", "delivered", False),
        ("sent", "bounced", True), ("delivered", "bounced", True),
        ("bounced", "delivered", False), ("bounced", "failed", False),
        ("sent", "mystery", False), ("sent", None, False), ("received", "sent", True),
    ],
)
def test_delivery_status_only_moves_forward(current, new, expected):
    assert should_apply_delivery_status(current, new) is expected


@pytest.mark.asyncio
async def test_delivery_events_update_the_outbound_email_they_refer_to(repo):
    conversation, _ = await repo.open_conversation(user_id=uuid4(), lead_id=uuid4())
    await _send(repo, conversation, provider="resend", provider_email_id="re_9",
                delivery_status="queued")
    await _send(repo, conversation, direction="INBOUND", provider="resend",
                provider_email_id="in_1", delivery_status="received")

    async def event(status, provider_id="re_9"):
        return await repo.update_delivery_status(
            provider="resend", provider_email_id=provider_id, delivery_status=status
        )

    assert (await event("SENT")).delivery_status == "sent"
    assert (await event("delivered")).delivery_status == "delivered"
    assert (await event("sent")).delivery_status == "delivered"  # late duplicate does not undo it
    assert (await event("mystery")).delivery_status == "delivered"
    assert (await event("bounced")).delivery_status == "bounced"
    assert (await event("delivered")).delivery_status == "bounced"  # a bounce is final

    assert await event("delivered", "re_unknown") is None
    assert await event("delivered", "") is None
    assert await event("delivered", "in_1") is None  # inbound mail never gets delivery events


# -- idempotency -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_webhook_event_is_only_ever_seen_once(repo, db):
    assert await repo.record_webhook_event(provider="resend", provider_event_id="evt_1") is True
    assert await repo.record_webhook_event(provider="resend", provider_event_id="evt_1") is False
    assert await repo.record_webhook_event(provider="RESEND", provider_event_id=" evt_1 ") is False
    # Same raw id from another provider is a different event.
    assert await repo.record_webhook_event(provider="vapi", provider_event_id="evt_1") is True
    await db.commit()
    stored = set((await db.scalars(select(SeenWebhookEvent.event_id))).all())
    assert stored == {"resend:evt_1", "vapi:evt_1"}


@pytest.mark.asyncio
async def test_a_rolled_back_event_can_be_retried(repo, db):
    assert await repo.record_webhook_event(provider="resend", provider_event_id="evt_2") is True
    await db.rollback()  # processing failed, so the marker must not survive
    assert await repo.record_webhook_event(provider="resend", provider_event_id="evt_2") is True


@pytest.mark.asyncio
async def test_a_webhook_event_needs_a_provider_and_an_id(repo):
    for provider, event_id in [("resend", "  "), ("", "evt"), (None, "evt"), ("resend", None)]:
        with pytest.raises(MailerValidationError):
            await repo.record_webhook_event(provider=provider, provider_event_id=event_id)


# -- leads -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lead_lookup_and_status_history_are_tenant_scoped(repo, db):
    user, other = uuid4(), uuid4()
    lead = Lead(id=uuid4(), user_id=user, hubspot_connection_id=uuid4(),
                hubspot_contact_id="hs-1", email="lead@example.com")
    db.add(lead)
    await db.flush()

    assert (await repo.get_lead(user_id=user, lead_id=lead.id)).email == "lead@example.com"
    assert await repo.get_lead(user_id=other, lead_id=lead.id) is None

    row = await repo.record_status_change(
        user_id=user, lead_id=lead.id, previous_status="CONTACTING",
        new_status="DO_NOT_CONTACT", source="AI", reason="asked to unsubscribe",
    )
    assert (row.new_status, row.source) == ("DO_NOT_CONTACT", "AI")

    with pytest.raises(MailerTenantError):
        await repo.record_status_change(
            user_id=other, lead_id=lead.id, new_status="INTERESTED", source="AI"
        )
    with pytest.raises(MailerValidationError):
        await repo.record_status_change(
            user_id=user, lead_id=lead.id, new_status="INTERESTED", source="ROBOT"
        )


# -- Postgres-only statements ----------------------------------------------------------


class _RecordingSession:
    def __init__(self, dialect_name):
        self.dialect_name = dialect_name
        self.statements = []

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name=self.dialect_name))

    async def execute(self, statement, params=None):
        self.statements.append((str(statement), params))


@pytest.mark.asyncio
async def test_conversations_are_serialized_with_an_advisory_lock_on_postgres_only():
    postgres = _RecordingSession("postgresql")
    await MailerRepository(postgres)._advisory_lock("some-key")
    (statement, params), = postgres.statements
    assert "pg_advisory_xact_lock(hashtextextended(" in statement
    assert params == {"key": "some-key"}

    sqlite = _RecordingSession("sqlite")
    await MailerRepository(sqlite)._advisory_lock("some-key")
    assert sqlite.statements == []


def test_the_idempotency_insert_is_race_safe_on_postgres():
    stmt = _webhook_event_insert("postgresql", event_id="resend:e1", source="resend")
    assert "ON CONFLICT (event_id) DO NOTHING" in str(stmt.compile(dialect=postgresql.dialect()))
    with pytest.raises(NotImplementedError):
        _webhook_event_insert("mysql", event_id="resend:e1", source="resend")
