from datetime import datetime
from uuid import uuid4

import pytest

from app.models.lead import Lead
from app.models.mailer import Email, EmailConversation
from app.modules.mailer.views import build_conversation_detail, build_conversation_list, lead_name


async def add_lead(db, user_id, **fields):
    lead = Lead(id=uuid4(), user_id=user_id, hubspot_connection_id=uuid4(),
                hubspot_contact_id=str(uuid4()), **{"email": "lead@example.com", **fields})
    db.add(lead)
    await db.flush()
    return lead


async def add_thread(repo, db, *, user, lead, campaign=None, emails=(), **conversation_fields):
    conversation, _ = await repo.open_conversation(user_id=user, lead_id=lead.id, campaign_id=campaign)
    if conversation_fields:
        await repo.update_conversation(user_id=user, conversation_id=conversation.id, **conversation_fields)
    for hour, direction, fields in emails:
        await repo.add_email(
            conversation_id=conversation.id, user_id=user, lead_id=lead.id, direction=direction,
            sent_or_received_at=datetime(2026, 1, 1, hour), **fields,
        )
    return conversation


# -- conversation_overview ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_overview_reports_the_first_subject_the_latest_activity_and_the_last_delivery(repo, db):
    user = uuid4()
    lead = await add_lead(db, user)
    conversation = await add_thread(repo, db, user=user, lead=lead, emails=[
        (9, "OUTBOUND", {"subject": "Opening line", "delivery_status": "delivered"}),
        (10, "INBOUND", {"subject": "Re: Opening line", "delivery_status": "received"}),
        (11, "OUTBOUND", {"subject": "Re: Opening line", "delivery_status": "bounced"}),
        (12, "INBOUND", {"subject": "Re: Re: Opening line", "delivery_status": "received"}),
    ])
    overview = (await repo.conversation_overview(user_id=user, conversation_ids=[conversation.id]))[conversation.id]
    assert overview["first_subject"] == "Opening line"
    assert (overview["email_count"], overview["reply_count"]) == (4, 2)
    assert overview["last_direction"] == "INBOUND"
    assert overview["last_activity_at"] == datetime(2026, 1, 1, 12)
    assert overview["delivery_status"] == "bounced"  # the newest email WE sent, not the newest overall


@pytest.mark.asyncio
async def test_overview_covers_a_whole_page_and_empty_threads_and_other_tenants(repo, db):
    user, other = uuid4(), uuid4()
    lead_a, lead_b, lead_c = await add_lead(db, user), await add_lead(db, user), await add_lead(db, other)
    first = await add_thread(repo, db, user=user, lead=lead_a, emails=[(9, "OUTBOUND", {"subject": "A"})])
    empty = await add_thread(repo, db, user=user, lead=lead_b)
    foreign = await add_thread(repo, db, user=other, lead=lead_c, emails=[(9, "OUTBOUND", {"subject": "SECRET"})])

    overview = await repo.conversation_overview(user_id=user, conversation_ids=[first.id, empty.id, foreign.id])
    assert overview[first.id]["first_subject"] == "A"
    assert overview[empty.id] == {"email_count": 0, "reply_count": 0, "first_subject": None,
                                  "last_direction": None, "last_activity_at": None, "delivery_status": None}
    assert overview[foreign.id]["first_subject"] is None and overview[foreign.id]["email_count"] == 0
    assert await repo.conversation_overview(user_id=user, conversation_ids=[]) == {}


# -- counts, metrics, leads ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_count_conversations_honours_the_same_filters_as_the_list(repo, db):
    user = uuid4()
    campaign = uuid4()
    lead_a, lead_b = await add_lead(db, user), await add_lead(db, user)
    await add_thread(repo, db, user=user, lead=lead_a, campaign=campaign, status="WAITING_FOR_LEAD", outcome="INTERESTED")
    await add_thread(repo, db, user=user, lead=lead_b, status="CONCLUDED", outcome="NOT_INTERESTED")
    db.add(EmailConversation(id=uuid4(), user_id=user, lead_id=lead_a.id, channel="SMS", status="OPEN"))
    await db.flush()

    assert await repo.count_conversations(user_id=user) == 2  # the SMS thread is not ours to count
    assert await repo.count_conversations(user_id=user, outcome="INTERESTED") == 1
    assert await repo.count_conversations(user_id=user, status="CONCLUDED") == 1
    assert await repo.count_conversations(user_id=user, campaign_id=campaign) == 1
    assert await repo.count_conversations(user_id=user, lead_id=lead_b.id) == 1
    assert await repo.count_conversations(user_id=uuid4()) == 0
    listed = await repo.list_conversations(user_id=user, outcome="NOT_INTERESTED")
    assert [c.lead_id for c in listed] == [lead_b.id]


@pytest.mark.asyncio
async def test_metrics_count_this_tenants_email_only(repo, db):
    user, other = uuid4(), uuid4()
    lead, foreign_lead = await add_lead(db, user), await add_lead(db, other)
    await add_thread(repo, db, user=user, lead=lead, outcome="INTERESTED", emails=[
        (9, "OUTBOUND", {"delivery_status": "delivered"}),
        (10, "INBOUND", {"delivery_status": "received"}),
        (11, "OUTBOUND", {"delivery_status": "sent"}),
    ])
    await add_thread(repo, db, user=user, lead=await add_lead(db, user), emails=[
        (9, "OUTBOUND", {"delivery_status": "bounced"}),
        (9, "OUTBOUND", {"delivery_status": "failed"}),
        (9, "OUTBOUND", {"delivery_status": "complained"}),
    ])
    await add_thread(repo, db, user=other, lead=foreign_lead, outcome="INTERESTED", emails=[
        (9, "OUTBOUND", {"delivery_status": "delivered"}),
    ])

    assert await repo.email_metrics(user_id=user) == {
        "conversations": 2, "emails_sent": 5, "delivered": 1, "replies": 1, "bounced": 3, "interested": 1,
    }
    assert await repo.email_metrics(user_id=uuid4()) == {
        "conversations": 0, "emails_sent": 0, "delivered": 0, "replies": 0, "bounced": 0, "interested": 0,
    }


@pytest.mark.asyncio
async def test_get_leads_is_tenant_scoped_and_tolerates_duplicates_and_nothing(repo, db):
    user, other = uuid4(), uuid4()
    mine, theirs = await add_lead(db, user), await add_lead(db, other)
    found = await repo.get_leads(user_id=user, lead_ids=[mine.id, mine.id, theirs.id, uuid4()])
    assert set(found) == {mine.id}
    assert await repo.get_leads(user_id=user, lead_ids=[]) == {}


# -- the assembled views -----------------------------------------------------------------------


def test_a_lead_is_named_from_the_best_field_available():
    class L:
        def __init__(self, display_name=None, first_name=None, last_name=None, email=None):
            self.display_name, self.first_name, self.last_name, self.email = display_name, first_name, last_name, email

    assert lead_name(L("Sam Lee", "S", "L", "s@x.com")) == "Sam Lee"
    assert lead_name(L(None, "Sam", "Lee", "s@x.com")) == "Sam Lee"
    assert lead_name(L(None, None, None, "s@x.com")) == "s@x.com"
    assert lead_name(L()) is None


@pytest.mark.asyncio
async def test_the_list_view_puts_every_column_the_prd_table_needs_on_each_row(repo, db):
    user, campaign = uuid4(), uuid4()
    lead = await add_lead(db, user, display_name="Sam Lee", email="sam@lead.example")
    conversation = await add_thread(repo, db, user=user, lead=lead, campaign=campaign,
                                    status="WAITING_FOR_LEAD", outcome="INTERESTED", add_turn=True,
                                    emails=[(9, "OUTBOUND", {"subject": "Hello", "delivery_status": "delivered"}),
                                            (10, "INBOUND", {"subject": "Re: Hello"})])
    view = await build_conversation_list(repo, user_id=user, limit=50, offset=0)
    (row,) = view.items
    assert (row.id, row.lead_id, row.lead_name, row.lead_email) == (conversation.id, lead.id, "Sam Lee", "sam@lead.example")
    assert (row.campaign_id, row.subject, row.status, row.outcome) == (campaign, "Hello", "WAITING_FOR_LEAD", "INTERESTED")
    assert (row.turn_count, row.email_count, row.reply_count) == (1, 2, 1)
    assert (row.last_direction, row.delivery_status) == ("INBOUND", "delivered")
    assert row.last_activity_at is not None and row.opened_at is not None and row.updated_at is not None
    assert (view.total, view.limit, view.offset) == (1, 50, 0)
    assert view.metrics.emails_sent == 1 and view.metrics.replies == 1 and view.metrics.interested == 1


@pytest.mark.asyncio
async def test_a_conversation_whose_lead_was_removed_still_lists(repo, db):
    user = uuid4()
    conversation, _ = await repo.open_conversation(user_id=user, lead_id=uuid4())
    (row,) = (await build_conversation_list(repo, user_id=user, limit=50, offset=0)).items
    assert row.id == conversation.id and row.lead_name is None and row.lead_email is None


@pytest.mark.asyncio
async def test_the_detail_view_returns_the_thread_oldest_first_without_provider_internals(repo, db):
    user = uuid4()
    lead = await add_lead(db, user, display_name="Sam Lee", website_url="https://acme.example")
    conversation = await add_thread(repo, db, user=user, lead=lead, emails=[
        (10, "INBOUND", {"subject": "Re: Hi", "text_body": "Tell me more", "from_address": "lead@example.com",
                         "provider": "resend", "provider_email_id": "in_1", "provider_payload": {"secret": "x"}}),
        (9, "OUTBOUND", {"subject": "Hi", "text_body": "Hello there", "html_body": "<p>Hello there</p>",
                         "from_address": "us@example.com", "to_addresses": ["lead@example.com"],
                         "provider": "resend", "provider_email_id": "re_1", "delivery_status": "delivered",
                         "provider_payload": {"mailer_context": {"campaign_objective": "internal"}}}),
    ])
    detail = await build_conversation_detail(repo, user_id=user, conversation_id=conversation.id)
    assert detail.lead.name == "Sam Lee" and detail.lead.website_url == "https://acme.example"
    assert [(e.direction, e.subject) for e in detail.emails] == [("OUTBOUND", "Hi"), ("INBOUND", "Re: Hi")]
    assert detail.emails[0].to_addresses == ["lead@example.com"] and detail.emails[0].delivery_status == "delivered"
    dumped = detail.model_dump_json()
    for internal in ("provider_payload", "provider_email_id", "html_body", "internet_message_id",
                     "in_1", "re_1", "mailer_context", "campaign_objective", "secret"):
        assert internal not in dumped


@pytest.mark.asyncio
async def test_an_html_only_email_is_shown_as_safe_text(repo, db):
    user = uuid4()
    lead = await add_lead(db, user)
    conversation = await add_thread(repo, db, user=user, lead=lead, emails=[
        (9, "INBOUND", {"html_body": "<div>Sounds <b>good</b></div><script>alert(1)</script><img src=x onerror=alert(2)>"}),
    ])
    (email,) = (await build_conversation_detail(repo, user_id=user, conversation_id=conversation.id)).emails
    assert email.text_body == "Sounds good"
    assert "<" not in email.text_body and "alert" not in email.text_body


@pytest.mark.asyncio
async def test_the_detail_view_hides_other_tenants_and_other_channels(repo, db):
    user, other = uuid4(), uuid4()
    lead = await add_lead(db, user)
    mine = await add_thread(repo, db, user=user, lead=lead)
    sms = EmailConversation(id=uuid4(), user_id=user, lead_id=lead.id, channel="SMS", status="OPEN")
    db.add(sms)
    await db.flush()
    assert await build_conversation_detail(repo, user_id=user, conversation_id=mine.id) is not None
    assert await build_conversation_detail(repo, user_id=other, conversation_id=mine.id) is None
    assert await build_conversation_detail(repo, user_id=user, conversation_id=sms.id) is None
    assert await build_conversation_detail(repo, user_id=user, conversation_id=uuid4()) is None
