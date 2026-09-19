from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.mailer import (
    EMAIL_CHANNEL,
    Email,
    EmailConversation,
    LeadStatusHistory,
    MailerBase,
)

# Column lists from Master PRD 24.12, 24.14 and 24.16.
PRD_CONVERSATIONS = {
    "id", "user_id", "campaign_id", "lead_id", "channel", "status", "provider_thread_id",
    "outcome", "turn_count", "opened_at", "concluded_at", "created_at", "updated_at",
}
PRD_EMAILS = {
    "id", "conversation_id", "user_id", "lead_id", "direction", "from_address", "to_addresses",
    "subject", "text_body", "html_body", "provider", "provider_email_id", "internet_message_id",
    "in_reply_to", "references_header", "delivery_status", "provider_payload",
    "sent_or_received_at", "created_at",
}
PRD_LEAD_STATUS_HISTORY = {
    "id", "user_id", "lead_id", "campaign_id", "previous_status", "new_status", "reason",
    "source", "created_at",
}


def _columns(model) -> set[str]:
    return {column.name for column in model.__table__.columns}


def test_columns_match_the_master_prd_and_the_live_tables():
    assert _columns(EmailConversation) == PRD_CONVERSATIONS
    assert _columns(Email) == PRD_EMAILS
    assert _columns(LeadStatusHistory) == PRD_LEAD_STATUS_HISTORY


def test_mailer_tables_stay_out_of_the_shared_alembic_metadata():
    # Alembic autogenerate reads Base.metadata. These tables already exist in the shared
    # database, so registering them there would generate CREATE TABLE for them.
    assert set(MailerBase.metadata.tables) == {"emails", "conversations", "lead_status_history"}
    assert "emails" not in Base.metadata.tables
    assert "lead_status_history" not in Base.metadata.tables
    assert Base.metadata.tables.get("conversations") is not MailerBase.metadata.tables["conversations"]
    assert EmailConversation.__table__.metadata is MailerBase.metadata


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    MailerBase.metadata.create_all(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def test_conversation_and_emails_round_trip_with_defaults(session):
    user_id, lead_id = uuid4(), uuid4()
    conversation = EmailConversation(user_id=user_id, lead_id=lead_id)
    session.add(conversation)
    session.flush()
    session.add_all(
        [
            Email(
                conversation_id=conversation.id,
                user_id=user_id,
                lead_id=lead_id,
                direction="OUTBOUND",
                to_addresses=["lead@example.com"],
                subject="Hello",
                internet_message_id="<a@x>",
            ),
            Email(
                conversation_id=conversation.id,
                user_id=user_id,
                lead_id=lead_id,
                direction="INBOUND",
                provider_payload={"event": "email.received"},
            ),
        ]
    )
    session.commit()
    session.expire_all()

    stored = session.scalars(select(EmailConversation)).one()
    assert (stored.channel, stored.status, stored.turn_count) == (EMAIL_CHANNEL, "OPEN", 0)
    assert isinstance(stored.id, UUID)
    assert stored.opened_at is not None and stored.created_at is not None

    inbound, outbound = session.scalars(select(Email).order_by(Email.direction)).all()
    assert (inbound.direction, outbound.direction) == ("INBOUND", "OUTBOUND")
    assert outbound.to_addresses == ["lead@example.com"]
    assert outbound.provider_payload == {}
    assert inbound.to_addresses == []
    assert inbound.provider_payload == {"event": "email.received"}
    assert outbound.internet_message_id == "<a@x>"
    assert outbound.sent_or_received_at is not None
    assert outbound.conversation_id == stored.id


def test_direction_has_no_default_so_callers_must_be_explicit(session):
    session.add(Email(user_id=uuid4(), lead_id=uuid4()))
    with pytest.raises(IntegrityError):
        session.commit()


def test_lead_status_history_requires_a_new_status(session):
    session.add(LeadStatusHistory(user_id=uuid4(), lead_id=uuid4()))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    session.add(
        LeadStatusHistory(
            user_id=uuid4(), lead_id=uuid4(), previous_status="CONTACTING",
            new_status="DO_NOT_CONTACT", reason="asked to unsubscribe", source="AI",
        )
    )
    session.commit()
    assert session.scalars(select(LeadStatusHistory)).one().new_status == "DO_NOT_CONTACT"
