"""The endpoints TPI calls to hand us verified email events."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy import select

from app.api.v1.routes.mailer_internal import (
    get_reply_dispatcher,
    get_settings_dependency,
    router,
)
from app.db.session import get_db
from app.models.calling import SeenWebhookEvent
from app.models.lead import Lead
from app.models.mailer import Email, EmailConversation
from app.modules.mailer.adapters import MAILER_QUEUE, REPLY_TASK, CeleryReplyDispatcher
from app.modules.mailer.config import MailerSettings
from app.modules.mailer.thread import build_reply_to_address, make_reply_to_token

TOKEN, SECRET, DOMAIN = "tpi-shared-token", "reply-secret", "reply.example.com"
INBOUND = "/internal/mailer/events/inbound"
DELIVERY = "/internal/mailer/events/delivery"


class FakeDispatcher:
    def __init__(self):
        self.queued, self.fail = [], False

    async def enqueue_reply(self, *, conversation_id, inbound_email_id):
        if self.fail:
            raise ConnectionError("redis is down")
        self.queued.append((conversation_id, inbound_email_id))


def settings_with(**overrides) -> MailerSettings:
    values = {"mailer_reply_token_secret": SECRET, "mailer_reply_to_domain": DOMAIN,
              "mailer_internal_service_token": TOKEN, **overrides}
    return MailerSettings(_env_file=None, **values)


def build_app(db, dispatcher, settings) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def session():
        yield db

    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_reply_dispatcher] = lambda: dispatcher
    app.dependency_overrides[get_settings_dependency] = lambda: settings
    return app


def client_for(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test/api/v1")


AUTH = {"X-Mailer-Service-Token": TOKEN}


@pytest.fixture
def dispatcher():
    return FakeDispatcher()


@pytest_asyncio.fixture
async def http(db, dispatcher):
    async with client_for(build_app(db, dispatcher, settings_with())) as client:
        yield client


@pytest_asyncio.fixture
async def thread(repo, db):
    """A conversation we have already written to once."""
    user, campaign = uuid4(), uuid4()
    lead = Lead(id=uuid4(), user_id=user, hubspot_connection_id=uuid4(), hubspot_contact_id="hs",
                display_name="Sam Lee", email="sam@lead.example")
    db.add(lead)
    await db.flush()
    conversation, _ = await repo.open_conversation(user_id=user, lead_id=lead.id, campaign_id=campaign)
    await repo.add_email(
        conversation_id=conversation.id, user_id=user, lead_id=lead.id, direction="OUTBOUND",
        subject="Hello", text_body="Hi Sam", provider="resend", provider_email_id="re_1",
        internet_message_id="<sent-1@out.example>", delivery_status="sent",
    )
    await repo.update_conversation(user_id=user, conversation_id=conversation.id,
                                   status="WAITING_FOR_LEAD", add_turn=True)
    await db.commit()
    return conversation


def inbound_payload(conversation, text="Tell me more", event_id="evt-1", provider_email_id="in-1", **overrides):
    address = build_reply_to_address(mailbox="mailer", domain=DOMAIN,
                                     token=make_reply_to_token(conversation.id, SECRET))
    return {"provider": "resend", "event_id": event_id, "provider_email_id": provider_email_id,
            "from_address": "sam@lead.example", "to_addresses": [address], "subject": "Re: Hello",
            "text_body": text, "internet_message_id": f"<lead-{event_id}@lead.example>",
            "in_reply_to": "<sent-1@out.example>", "received_at": datetime.now(UTC).isoformat(), **overrides}


async def stored_emails(db, conversation_id):
    await db.rollback()  # drop anything uncommitted: only what the endpoint committed remains
    rows = await db.scalars(select(Email).where(Email.conversation_id == conversation_id)
                            .order_by(Email.sent_or_received_at))
    return list(rows)


# -- who may call -------------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("path", [INBOUND, DELIVERY])
@pytest.mark.parametrize(
    "headers", [{}, {"X-Mailer-Service-Token": ""}, {"X-Mailer-Service-Token": "wrong"},
                {"X-Mailer-Service-Token": TOKEN + "x"}, {"X-Mailer-Service-Token": TOKEN[:-1]},
                {"X-Mailer-Service-Token": TOKEN[:4]}, {"X-Mailer-Service-Token": TOKEN.upper()},
                {"X-Mailer-Service-Token": "tökén".encode("latin-1")},  # raw non-ASCII bytes, as a client may send
                {"X-TPI-Service-Token": TOKEN}],
)
async def test_only_a_caller_holding_the_service_token_is_let_in(http, path, headers):
    assert (await http.post(path, json={}, headers=headers)).status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("path", [INBOUND, DELIVERY])
async def test_with_no_token_configured_every_caller_is_refused(db, dispatcher, path):
    app = build_app(db, dispatcher, settings_with(mailer_internal_service_token=""))
    async with client_for(app) as client:
        for headers in ({}, {"X-Mailer-Service-Token": ""}, AUTH):
            assert (await client.post(path, json={}, headers=headers)).status_code == 503


@pytest.mark.asyncio
async def test_a_malformed_event_is_a_validation_error_not_a_crash(http):
    assert (await http.post(INBOUND, json={"from_address": "x"}, headers=AUTH)).status_code == 422
    assert (await http.post(DELIVERY, json={"event_id": "d1"}, headers=AUTH)).status_code == 422


# -- a reply arrives ----------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_reply_is_stored_committed_and_queued_for_a_worker(http, db, dispatcher, thread):
    response = await http.post(INBOUND, json=inbound_payload(thread), headers=AUTH)

    assert response.status_code == 200
    body = response.json()
    assert (body["accepted"], body["status"], body["duplicate"], body["reply_queued"]) == (True, "received", False, True)
    assert body["conversation_id"] == str(thread.id)
    emails = await stored_emails(db, thread.id)  # read back after a rollback: it was committed
    assert [e.direction for e in emails] == ["OUTBOUND", "INBOUND"]
    assert emails[1].text_body == "Tell me more" and emails[1].delivery_status == "received"
    assert dispatcher.queued == [(thread.id, emails[1].id)]


@pytest.mark.asyncio
async def test_no_model_or_provider_is_needed_to_acknowledge_a_reply(http, dispatcher, thread):
    # The app was built with none; a reply must still be accepted, quickly, and nothing sent.
    assert (await http.post(INBOUND, json=inbound_payload(thread), headers=AUTH)).status_code == 200
    assert len(dispatcher.queued) == 1


@pytest.mark.asyncio
async def test_a_reply_that_matches_nothing_is_acknowledged_but_stores_and_queues_nothing(http, db, dispatcher, thread):
    stranger = inbound_payload(thread, in_reply_to="<unknown@nowhere>",
                               to_addresses=["someone@else.example"])
    body = (await http.post(INBOUND, json=stranger, headers=AUTH)).json()
    assert (body["accepted"], body["status"], body["reply_queued"]) == (False, "unmatched", False)
    assert len(await stored_emails(db, thread.id)) == 1 and dispatcher.queued == []
    assert await db.scalar(select(SeenWebhookEvent.event_id)) is None


@pytest.mark.asyncio
async def test_a_reply_signed_with_another_secret_matches_nothing(http, thread, dispatcher):
    forged = inbound_payload(thread, in_reply_to=None, to_addresses=[
        build_reply_to_address(mailbox="mailer", domain=DOMAIN, token=make_reply_to_token(thread.id, "attacker"))])
    assert (await http.post(INBOUND, json=forged, headers=AUTH)).json()["status"] == "unmatched"
    assert dispatcher.queued == []


@pytest.mark.asyncio
async def test_a_request_to_unsubscribe_is_settled_immediately_and_nothing_is_queued(http, db, dispatcher, thread):
    body = (await http.post(INBOUND, json=inbound_payload(thread, "Please unsubscribe me"), headers=AUTH)).json()
    assert (body["accepted"], body["status"], body["reply_queued"]) == (True, "stopped", False)
    assert dispatcher.queued == []
    await db.rollback()
    conversation = await db.scalar(select(EmailConversation).where(EmailConversation.id == thread.id)
                                   .execution_options(populate_existing=True))
    assert (conversation.status, conversation.outcome) == ("CONCLUDED", "DO_NOT_CONTACT")


@pytest.mark.asyncio
async def test_the_same_event_twice_before_it_is_answered_is_queued_again_not_dropped(http, db, dispatcher, thread):
    payload = inbound_payload(thread)
    first = (await http.post(INBOUND, json=payload, headers=AUTH)).json()
    again = (await http.post(INBOUND, json=payload, headers=AUTH)).json()
    assert (first["status"], again["status"]) == ("received", "received")
    assert len(await stored_emails(db, thread.id)) == 2  # stored once
    assert len(dispatcher.queued) == 2 and dispatcher.queued[0] == dispatcher.queued[1]


@pytest.mark.asyncio
async def test_an_event_for_a_reply_that_was_already_answered_is_a_duplicate(http, db, repo, dispatcher, thread):
    payload = inbound_payload(thread)
    await http.post(INBOUND, json=payload, headers=AUTH)
    await repo.add_email(conversation_id=thread.id, user_id=thread.user_id, lead_id=thread.lead_id,
                         direction="OUTBOUND", subject="Re: Hello", text_body="Answer",
                         sent_or_received_at=datetime.now(UTC))
    await db.commit()
    body = (await http.post(INBOUND, json=payload, headers=AUTH)).json()
    assert (body["status"], body["duplicate"], body["reply_queued"]) == ("duplicate", True, False)
    assert len(dispatcher.queued) == 1


@pytest.mark.asyncio
async def test_if_the_queue_is_down_the_reply_is_kept_and_the_retry_queues_it(http, db, dispatcher, thread):
    payload = inbound_payload(thread)
    dispatcher.fail = True
    down = await http.post(INBOUND, json=payload, headers=AUTH)
    assert down.status_code == 503
    assert "redis" not in down.text.lower() and "ConnectionError" not in down.text  # no internals leaked
    assert len(await stored_emails(db, thread.id)) == 2  # the reply itself was not lost

    dispatcher.fail = False
    retry = (await http.post(INBOUND, json=payload, headers=AUTH)).json()
    assert (retry["status"], retry["reply_queued"]) == ("received", True)
    assert len(await stored_emails(db, thread.id)) == 2 and len(dispatcher.queued) == 1


# -- a delivery report arrives ----------------------------------------------------------------------


def report(status, event_id="d-1", **overrides):
    return {"provider": "resend", "event_id": event_id, "provider_email_id": "re_1", "status": status, **overrides}


@pytest.mark.asyncio
async def test_a_delivery_report_updates_the_email(http, db, thread):
    body = (await http.post(DELIVERY, json=report("delivered"), headers=AUTH)).json()
    assert (body["accepted"], body["status"]) == (True, "delivery_updated")
    assert (await stored_emails(db, thread.id))[0].delivery_status == "delivered"


@pytest.mark.asyncio
async def test_a_permanent_bounce_stops_the_conversation_and_is_not_repeated(http, db, thread):
    body = (await http.post(DELIVERY, json=report("bounced"), headers=AUTH)).json()
    assert body["status"] == "stopped"
    again = (await http.post(DELIVERY, json=report("bounced"), headers=AUTH)).json()
    assert (again["status"], again["duplicate"]) == ("duplicate", True)
    await db.rollback()
    conversation = await db.scalar(select(EmailConversation).where(EmailConversation.id == thread.id)
                                   .execution_options(populate_existing=True))
    assert (conversation.status, conversation.outcome) == ("FAILED", "FAILED")


@pytest.mark.asyncio
async def test_a_report_about_mail_we_never_sent_is_acknowledged_so_it_is_not_retried(http):
    unknown = report("delivered", event_id="d-x", provider_email_id="re_unknown")
    body = (await http.post(DELIVERY, json=unknown, headers=AUTH)).json()
    assert (body["accepted"], body["status"]) == (True, "unknown_email")


# -- queueing -------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_reply_is_queued_by_task_name_on_the_mailer_queue(monkeypatch):
    sent = {}

    def fake_send_task(name, kwargs=None, queue=None, **rest):
        sent.update(name=name, kwargs=kwargs, queue=queue, rest=rest)

    monkeypatch.setattr("app.workers.celery_app.celery_app.send_task", fake_send_task)
    conversation_id, email_id = uuid4(), uuid4()
    await CeleryReplyDispatcher().enqueue_reply(conversation_id=conversation_id, inbound_email_id=email_id)

    assert (sent["name"], sent["queue"]) == (REPLY_TASK, MAILER_QUEUE) == ("mailer.process_inbound_email", "mailer.email")
    assert sent["kwargs"] == {"conversation_id": str(conversation_id), "inbound_email_id": str(email_id)}
    assert all(isinstance(v, str) and UUID(v) for v in sent["kwargs"].values())  # JSON-safe
