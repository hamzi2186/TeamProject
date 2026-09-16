"""Create SMS engine schema.

Revision ID: 20260916_sms_0001
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260916_sms_0001"
down_revision = None
branch_labels = ("sms_engine",)
depends_on = None

SCHEMA = "sms_engine"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True)),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True)),
        sa.Column("contact_name", sa.Text(), nullable=False),
        sa.Column("from_number", sa.String(32), nullable=False),
        sa.Column("to_number", sa.String(32), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("outcome", sa.String(32)),
        sa.Column("message_template", sa.Text(), nullable=False),
        sa.Column("campaign_objective", sa.Text(), nullable=False),
        sa.Column("knowledge_context", sa.Text(), nullable=False),
        sa.Column("agent_turn_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_agent_turns", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("concluded_at", sa.DateTime(timezone=True)),
        sa.Column("last_message_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('OPEN','CONCLUDED','UNRESOLVED')", name="ck_conversations_status_valid"),
        sa.CheckConstraint(
            "outcome IS NULL OR outcome IN ('INTERESTED','CONVERTED','FOLLOW_UP_REQUESTED',"
            "'NOT_INTERESTED','WRONG_NUMBER','DO_NOT_CONTACT','NO_RESPONSE')",
            name="ck_conversations_outcome_valid",
        ),
        sa.UniqueConstraint("user_id", "campaign_id", "lead_id", name="uq_conversations_conversation_target"),
        schema=SCHEMA,
    )
    op.create_index("ix_sms_conversations_user_id", "conversations", ["user_id"], schema=SCHEMA)
    op.create_index("ix_sms_conversations_campaign_id", "conversations", ["campaign_id"], schema=SCHEMA)
    op.create_index("ix_sms_conversations_lead_id", "conversations", ["lead_id"], schema=SCHEMA)
    op.create_index("ix_sms_conversations_last_message_at", "conversations", ["last_message_at"], schema=SCHEMA)
    op.create_index(
        "ix_sms_conversations_user_status_updated",
        "conversations",
        ["user_id", "status", "updated_at"],
        schema=SCHEMA,
    )
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True)),
        sa.Column("direction", sa.String(12), nullable=False),
        sa.Column("from_number", sa.String(32), nullable=False),
        sa.Column("to_number", sa.String(32), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("provider_message_id", sa.String(128)),
        sa.Column("delivery_status", sa.String(24), nullable=False),
        sa.Column("provider_payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("direction IN ('INBOUND','OUTBOUND')", name="ck_messages_direction_valid"),
        sa.CheckConstraint(
            "delivery_status IN ('QUEUED','SENT','DELIVERED','UNDELIVERED','FAILED','RECEIVED')",
            name="ck_messages_delivery_status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], [f"{SCHEMA}.conversations.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("provider", "provider_message_id", name="uq_messages_provider_message"),
        schema=SCHEMA,
    )
    op.create_index("ix_sms_messages_user_id", "messages", ["user_id"], schema=SCHEMA)
    op.create_index("ix_sms_messages_conversation_occurred", "messages", ["conversation_id", "occurred_at"], schema=SCHEMA)
    op.create_index("ix_sms_messages_user_lead", "messages", ["user_id", "lead_id"], schema=SCHEMA)
    op.create_table(
        "consents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True)),
        sa.Column("phone_number", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True)),
        sa.Column("opted_out_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('UNKNOWN','CONSENTED','OPTED_OUT')", name="ck_consents_status_valid"),
        sa.UniqueConstraint("user_id", "phone_number", name="uq_consents_user_phone"),
        schema=SCHEMA,
    )
    op.create_index("ix_sms_consents_user_id", "consents", ["user_id"], schema=SCHEMA)
    op.create_index("ix_sms_consents_lead_id", "consents", ["lead_id"], schema=SCHEMA)
    op.create_table(
        "provider_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("event_id", sa.String(160), nullable=False),
        sa.Column("event_type", sa.String(48), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("provider", "event_id", name="uq_provider_events_provider_event"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_sms_provider_events_user_received",
        "provider_events",
        ["user_id", "received_at"],
        schema=SCHEMA,
    )
    _secure_tables()


def _secure_tables() -> None:
    for table in ("conversations", "messages", "consents", "provider_events"):
        op.execute(f"ALTER TABLE {SCHEMA}.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_policy ON {SCHEMA}.{table} FOR ALL "
            "USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid) "
            "WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid)"
        )
    op.execute(f"REVOKE ALL ON SCHEMA {SCHEMA} FROM PUBLIC")
    op.execute(
        f"""DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
            REVOKE ALL ON SCHEMA {SCHEMA} FROM anon;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
            REVOKE ALL ON SCHEMA {SCHEMA} FROM authenticated;
          END IF;
        END $$"""
    )


def downgrade() -> None:
    op.drop_table("provider_events", schema=SCHEMA)
    op.drop_table("consents", schema=SCHEMA)
    op.drop_table("messages", schema=SCHEMA)
    op.drop_table("conversations", schema=SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA}")
