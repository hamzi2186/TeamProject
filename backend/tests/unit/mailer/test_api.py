"""The two read endpoints, exercised over real HTTP through the ASGI stack."""

from datetime import datetime
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from app.api.v1.routes.mailer import router
from app.auth.dependencies import AuthenticatedUser, get_current_user
from app.db.session import get_db
from app.models.lead import Lead
from app.models.mailer import EmailConversation

BASE = "/api/v1/mailer/conversations"


def build_app(db, *, user=None) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    async def session():
        yield db

    app.dependency_overrides[get_db] = session
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    return app


def as_user(user_id) -> AuthenticatedUser:
    return AuthenticatedUser(user_id=user_id, role="customer", email="me@example.com")


def client_for(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest_asyncio.fixture
async def seeded(repo, db):
    """Two tenants, each with a conversation that has a full thread."""
    async def tenant(name, subject):
        user = uuid4()
        lead = Lead(id=uuid4(), user_id=user, hubspot_connection_id=uuid4(), hubspot_contact_id=name,
                    display_name=name, email=f"{name.lower()}@lead.example")
        db.add(lead)
        await db.flush()
        campaign = uuid4()
        conversation, _ = await repo.open_conversation(user_id=user, lead_id=lead.id, campaign_id=campaign)
        await repo.update_conversation(user_id=user, conversation_id=conversation.id,
                                       status="WAITING_FOR_LEAD", outcome="INTERESTED", add_turn=True)
        for hour, direction, fields in [
            (9, "OUTBOUND", {"subject": subject, "text_body": "Hello", "delivery_status": "delivered",
                             "provider": "resend", "provider_email_id": f"re_{name}",
                             "provider_payload": {"token": "hidden"}}),
            (10, "INBOUND", {"subject": f"Re: {subject}", "text_body": "Tell me more"}),
        ]:
            await repo.add_email(conversation_id=conversation.id, user_id=user, lead_id=lead.id,
                                 direction=direction, sent_or_received_at=datetime(2026, 1, 1, hour), **fields)
        await db.commit()
        return SimpleTenant(user, lead, conversation, campaign)

    return {"ada": await tenant("Ada", "Ada subject"), "bob": await tenant("Bob", "Bob subject")}


class SimpleTenant:
    def __init__(self, user, lead, conversation, campaign):
        self.user, self.lead, self.conversation, self.campaign = user, lead, conversation, campaign


# -- who may call ----------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("path", [BASE, f"{BASE}/{uuid4()}"])
async def test_both_endpoints_require_a_login(db, path):
    async with client_for(build_app(db)) as client:
        assert (await client.get(path)).status_code == 401


# -- the list ---------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_empty_list_is_a_valid_envelope_with_zeroed_metrics(db):
    async with client_for(build_app(db, user=as_user(uuid4()))) as client:
        response = await client.get(BASE)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True and body["error"] is None and body["request_id"]
    assert body["data"] == {
        "items": [], "total": 0, "limit": 50, "offset": 0,
        "metrics": {"conversations": 0, "emails_sent": 0, "delivered": 0, "replies": 0, "bounced": 0, "interested": 0},
    }


@pytest.mark.asyncio
async def test_a_tenant_sees_only_their_own_conversations_and_numbers(db, seeded):
    async with client_for(build_app(db, user=as_user(seeded["ada"].user))) as client:
        body = (await client.get(BASE)).json()
    (row,) = body["data"]["items"]
    ada = seeded["ada"]
    assert (row["id"], row["lead_name"], row["lead_email"]) == (str(ada.conversation.id), "Ada", "ada@lead.example")
    assert (row["subject"], row["status"], row["outcome"], row["campaign_id"]) == (
        "Ada subject", "WAITING_FOR_LEAD", "INTERESTED", str(ada.campaign))
    assert (row["email_count"], row["reply_count"], row["last_direction"], row["delivery_status"]) == (
        2, 1, "INBOUND", "delivered")
    assert body["data"]["total"] == 1
    assert body["data"]["metrics"] == {"conversations": 1, "emails_sent": 1, "delivered": 1,
                                       "replies": 1, "bounced": 0, "interested": 1}
    assert "Bob" not in str(body) and "bob" not in str(body)


@pytest.mark.asyncio
async def test_filters_and_paging_narrow_the_list_and_the_total(db, seeded):
    ada = seeded["ada"]
    async with client_for(build_app(db, user=as_user(ada.user))) as client:
        assert (await client.get(BASE, params={"outcome": "INTERESTED"})).json()["data"]["total"] == 1
        assert (await client.get(BASE, params={"outcome": "NOT_INTERESTED"})).json()["data"]["items"] == []
        assert (await client.get(BASE, params={"status": "CONCLUDED"})).json()["data"]["total"] == 0
        assert (await client.get(BASE, params={"lead_id": str(ada.lead.id)})).json()["data"]["total"] == 1
        assert (await client.get(BASE, params={"lead_id": str(uuid4())})).json()["data"]["total"] == 0
        assert (await client.get(BASE, params={"campaign_id": str(ada.campaign)})).json()["data"]["total"] == 1
        paged = (await client.get(BASE, params={"limit": 1, "offset": 1})).json()["data"]
    assert (paged["items"], paged["total"], paged["limit"], paged["offset"]) == ([], 1, 1, 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"lead_id": "not-a-uuid"}])
async def test_bad_query_values_are_rejected(db, params):
    async with client_for(build_app(db, user=as_user(uuid4()))) as client:
        assert (await client.get(BASE, params=params)).status_code == 422


@pytest.mark.asyncio
async def test_another_tenants_lead_filter_finds_nothing(db, seeded):
    async with client_for(build_app(db, user=as_user(seeded["ada"].user))) as client:
        body = (await client.get(BASE, params={"lead_id": str(seeded["bob"].lead.id)})).json()
    assert body["data"]["items"] == [] and body["data"]["total"] == 0


# -- the thread ---------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_detail_returns_the_lead_and_the_whole_thread_in_order(db, seeded):
    ada = seeded["ada"]
    async with client_for(build_app(db, user=as_user(ada.user))) as client:
        response = await client.get(f"{BASE}/{ada.conversation.id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert (data["id"], data["status"], data["outcome"], data["turn_count"]) == (
        str(ada.conversation.id), "WAITING_FOR_LEAD", "INTERESTED", 1)
    assert data["lead"]["name"] == "Ada" and data["lead"]["email"] == "ada@lead.example"
    assert [(e["direction"], e["subject"], e["text_body"]) for e in data["emails"]] == [
        ("OUTBOUND", "Ada subject", "Hello"), ("INBOUND", "Re: Ada subject", "Tell me more")]
    assert data["emails"][0]["delivery_status"] == "delivered"
    assert data["emails"][0]["sent_or_received_at"].startswith("2026-01-01T09:00")


@pytest.mark.asyncio
async def test_nothing_internal_reaches_the_browser(db, seeded):
    ada = seeded["ada"]
    async with client_for(build_app(db, user=as_user(ada.user))) as client:
        text = (await client.get(f"{BASE}/{ada.conversation.id}")).text + (await client.get(BASE)).text
    for internal in ("provider_payload", "provider_email_id", "re_Ada", "hidden", "html_body", "token"):
        assert internal not in text


@pytest.mark.asyncio
async def test_another_tenants_conversation_is_indistinguishable_from_a_missing_one(db, seeded):
    bobs = seeded["bob"].conversation.id
    async with client_for(build_app(db, user=as_user(seeded["ada"].user))) as client:
        foreign = await client.get(f"{BASE}/{bobs}")
        missing = await client.get(f"{BASE}/{uuid4()}")
    assert foreign.status_code == missing.status_code == 404
    for response in (foreign, missing):
        body = response.json()
        assert (body["success"], body["data"]) == (False, None)
        assert body["error"]["code"] == "CONVERSATION_NOT_FOUND" and body["request_id"]
    assert "Bob" not in foreign.text


@pytest.mark.asyncio
async def test_a_conversation_on_another_channel_is_not_served(db, seeded):
    ada = seeded["ada"]
    sms = EmailConversation(id=uuid4(), user_id=ada.user, lead_id=ada.lead.id, channel="SMS", status="OPEN")
    db.add(sms)
    await db.commit()
    async with client_for(build_app(db, user=as_user(ada.user))) as client:
        assert (await client.get(f"{BASE}/{sms.id}")).status_code == 404
        assert (await client.get(BASE)).json()["data"]["total"] == 1


@pytest.mark.asyncio
async def test_a_malformed_conversation_id_is_a_validation_error(db):
    async with client_for(build_app(db, user=as_user(uuid4()))) as client:
        assert (await client.get(f"{BASE}/not-a-uuid")).status_code == 422


# -- request ids ------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_wellformed_request_id_is_echoed_and_a_hostile_one_is_replaced(db):
    async with client_for(build_app(db, user=as_user(uuid4()))) as client:
        echoed = (await client.get(BASE, headers={"X-Request-ID": "req-123.abc"})).json()["request_id"]
        generated = (await client.get(BASE)).json()["request_id"]
        hostile = (await client.get(BASE, headers={"X-Request-ID": "x\r\nSet-Cookie: a=b <script>"})).json()["request_id"]
        too_long = (await client.get(BASE, headers={"X-Request-ID": "a" * 200})).json()["request_id"]
    assert echoed == "req-123.abc"
    assert generated and generated != echoed
    assert "<" not in hostile and "\n" not in hostile and hostile != "x\r\nSet-Cookie: a=b <script>"
    assert len(too_long) <= 64
