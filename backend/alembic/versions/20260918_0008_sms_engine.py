"""Add the SMS Engine domain to the shared database.

Revision ID: 20260918_0008
Revises: 20260917_0007
"""

from alembic import op

revision = "20260918_0008"
down_revision = "20260917_0007"
branch_labels = None
depends_on = None

SCHEMA = "sms_engine"
TABLES = ("conversations", "messages", "consents", "provider_events")


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA}.conversations (
            id uuid PRIMARY KEY,
            user_id uuid NOT NULL,
            campaign_id uuid,
            lead_id uuid,
            contact_name text NOT NULL,
            from_number varchar(32) NOT NULL,
            to_number varchar(32) NOT NULL,
            timezone varchar(64) NOT NULL,
            status varchar(24) NOT NULL,
            outcome varchar(32),
            message_template text NOT NULL,
            campaign_objective text NOT NULL,
            knowledge_context text NOT NULL,
            agent_turn_count integer DEFAULT 0 NOT NULL,
            max_agent_turns integer DEFAULT 8 NOT NULL,
            opened_at timestamptz DEFAULT now() NOT NULL,
            concluded_at timestamptz,
            last_message_at timestamptz,
            created_at timestamptz DEFAULT now() NOT NULL,
            updated_at timestamptz DEFAULT now() NOT NULL,
            CONSTRAINT ck_sms_conversations_status
                CHECK (status IN ('OPEN', 'CONCLUDED', 'UNRESOLVED')),
            CONSTRAINT ck_sms_conversations_outcome
                CHECK (outcome IS NULL OR outcome IN (
                    'INTERESTED', 'CONVERTED', 'FOLLOW_UP_REQUESTED',
                    'NOT_INTERESTED', 'WRONG_NUMBER', 'DO_NOT_CONTACT', 'NO_RESPONSE'
                )),
            CONSTRAINT uq_sms_conversation_target UNIQUE (user_id, campaign_id, lead_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA}.messages (
            id uuid PRIMARY KEY,
            conversation_id uuid NOT NULL
                REFERENCES {SCHEMA}.conversations(id) ON DELETE CASCADE,
            user_id uuid NOT NULL,
            lead_id uuid,
            direction varchar(12) NOT NULL,
            from_number varchar(32) NOT NULL,
            to_number varchar(32) NOT NULL,
            body text NOT NULL,
            provider varchar(32) NOT NULL,
            provider_message_id varchar(128),
            delivery_status varchar(24) NOT NULL,
            provider_payload jsonb DEFAULT '{{}}'::jsonb NOT NULL,
            occurred_at timestamptz NOT NULL,
            created_at timestamptz DEFAULT now() NOT NULL,
            CONSTRAINT ck_sms_messages_direction CHECK (direction IN ('INBOUND', 'OUTBOUND')),
            CONSTRAINT ck_sms_messages_delivery_status CHECK (delivery_status IN (
                'QUEUED', 'SENT', 'DELIVERED', 'UNDELIVERED', 'FAILED', 'RECEIVED'
            )),
            CONSTRAINT uq_sms_provider_message UNIQUE (provider, provider_message_id)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA}.consents (
            id uuid PRIMARY KEY,
            user_id uuid NOT NULL,
            lead_id uuid,
            phone_number varchar(32) NOT NULL,
            status varchar(16) NOT NULL,
            source varchar(64) NOT NULL,
            recorded_at timestamptz,
            opted_out_at timestamptz,
            updated_at timestamptz DEFAULT now() NOT NULL,
            CONSTRAINT ck_sms_consents_status
                CHECK (status IN ('UNKNOWN', 'CONSENTED', 'OPTED_OUT')),
            CONSTRAINT uq_sms_user_phone UNIQUE (user_id, phone_number)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA}.provider_events (
            id uuid PRIMARY KEY,
            user_id uuid NOT NULL,
            provider varchar(32) NOT NULL,
            event_id varchar(160) NOT NULL,
            event_type varchar(48) NOT NULL,
            payload jsonb DEFAULT '{{}}'::jsonb NOT NULL,
            received_at timestamptz DEFAULT now() NOT NULL,
            processed_at timestamptz,
            CONSTRAINT uq_sms_provider_event UNIQUE (provider, event_id)
        )
        """
    )

    indexes = (
        ("ix_sms_conversations_user_id", "conversations", "user_id"),
        ("ix_sms_conversations_campaign_id", "conversations", "campaign_id"),
        ("ix_sms_conversations_lead_id", "conversations", "lead_id"),
        ("ix_sms_conversations_last_message_at", "conversations", "last_message_at"),
        (
            "ix_sms_conversations_user_status_updated",
            "conversations",
            "user_id, status, updated_at",
        ),
        ("ix_sms_messages_user_id", "messages", "user_id"),
        (
            "ix_sms_messages_conversation_occurred",
            "messages",
            "conversation_id, occurred_at",
        ),
        ("ix_sms_messages_user_lead", "messages", "user_id, lead_id"),
        ("ix_sms_consents_user_id", "consents", "user_id"),
        ("ix_sms_consents_lead_id", "consents", "lead_id"),
        (
            "ix_sms_provider_events_user_received",
            "provider_events",
            "user_id, received_at",
        ),
    )
    for name, table, columns in indexes:
        op.execute(
            f"CREATE INDEX IF NOT EXISTS {name} ON {SCHEMA}.{table} ({columns})"
        )

    for table in TABLES:
        op.execute(f"ALTER TABLE {SCHEMA}.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_policies
                    WHERE schemaname = '{SCHEMA}'
                      AND tablename = '{table}'
                      AND policyname = '{table}_tenant_policy'
                ) THEN
                    CREATE POLICY {table}_tenant_policy ON {SCHEMA}.{table} FOR ALL
                    USING (
                        user_id = NULLIF(
                            current_setting('app.current_user_id', true), ''
                        )::uuid
                    )
                    WITH CHECK (
                        user_id = NULLIF(
                            current_setting('app.current_user_id', true), ''
                        )::uuid
                    );
                END IF;
            END $$
            """
        )

    op.execute(f"REVOKE ALL ON SCHEMA {SCHEMA} FROM PUBLIC")
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                REVOKE ALL ON SCHEMA {SCHEMA} FROM anon;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                REVOKE ALL ON SCHEMA {SCHEMA} FROM authenticated;
            END IF;
        END $$
        """
    )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP TABLE IF EXISTS {SCHEMA}.{table} CASCADE")
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA}")
