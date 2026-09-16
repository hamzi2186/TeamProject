"""Calling Engine foundation: calls and seen_webhook_events tables.

Revision ID: 0001
Revises:
Create Date: 2026-09-16 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "calls",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("lead_id", sa.Text, nullable=False),
        sa.Column("conversation_id", UUID(as_uuid=True), nullable=True),
        sa.Column("campaign_id", UUID(as_uuid=True), nullable=True),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("from_number", sa.Text, nullable=True),
        sa.Column("to_number", sa.Text, nullable=True),
        sa.Column("provider", sa.String(32), nullable=False, server_default="vapi"),
        sa.Column("provider_call_id", sa.Text, nullable=True, unique=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="QUEUED"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer, nullable=True),
        sa.Column("transcript", sa.Text, nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("outcome", sa.String(32), nullable=True),
        sa.Column("recording_url", sa.Text, nullable=True),
        sa.Column("provider_payload", JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Soft FK to shared app_users — no hard FK to allow engine independence
        sa.CheckConstraint("direction IN ('OUTBOUND','INBOUND')", name="ck_calls_direction"),
        sa.CheckConstraint(
            "status IN ('QUEUED','RINGING','IN_PROGRESS','COMPLETED','NO_ANSWER','FAILED','CANCELLED')",
            name="ck_calls_status",
        ),
        sa.CheckConstraint(
            "outcome IS NULL OR outcome IN ('INTERESTED','NOT_INTERESTED','FOLLOW_UP_REQUIRED',"
            "'NO_ANSWER','CONVERTED','DO_NOT_CONTACT','COMPLETED','FAILED')",
            name="ck_calls_outcome",
        ),
    )
    op.create_index("ix_calls_user_id", "calls", ["user_id"])
    op.create_index("ix_calls_lead_id", "calls", ["lead_id"])
    op.create_index("ix_calls_provider_call_id", "calls", ["provider_call_id"])
    op.create_index("ix_calls_campaign_id", "calls", ["campaign_id"])

    op.create_table(
        "seen_webhook_events",
        sa.Column("event_id", sa.Text, primary_key=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="vapi"),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_seen_webhook_events_source", "seen_webhook_events", ["source"])


def downgrade() -> None:
    op.drop_index("ix_seen_webhook_events_source", table_name="seen_webhook_events")
    op.drop_table("seen_webhook_events")
    op.drop_index("ix_calls_campaign_id", table_name="calls")
    op.drop_index("ix_calls_provider_call_id", table_name="calls")
    op.drop_index("ix_calls_lead_id", table_name="calls")
    op.drop_index("ix_calls_user_id", table_name="calls")
    op.drop_table("calls")
