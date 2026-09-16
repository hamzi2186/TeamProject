"""Create calling records and webhook idempotency storage.

Revision ID: 20260916_0004
Revises: 20260916_0003
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260916_0004"
down_revision = "20260916_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lead_id", sa.Text(), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column("from_number", sa.Text(), nullable=True),
        sa.Column("to_number", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(32), nullable=False, server_default="vapi"),
        sa.Column("provider_call_id", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="QUEUED"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("outcome", sa.String(32), nullable=True),
        sa.Column("recording_url", sa.Text(), nullable=True),
        sa.Column("provider_payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_calls_user_id", "calls", ["user_id"])
    op.create_index("ix_calls_lead_id", "calls", ["lead_id"])
    op.create_index("ix_calls_provider_call_id", "calls", ["provider_call_id"])
    op.create_unique_constraint("uq_calls_provider_call_id", "calls", ["provider_call_id"])
    op.create_table(
        "seen_webhook_events",
        sa.Column("event_id", sa.Text(), primary_key=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="vapi"),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_seen_webhook_events_source", "seen_webhook_events", ["source"])


def downgrade() -> None:
    op.drop_index("ix_seen_webhook_events_source", table_name="seen_webhook_events")
    op.drop_table("seen_webhook_events")
    op.drop_constraint("uq_calls_provider_call_id", "calls", type_="unique")
    op.drop_index("ix_calls_provider_call_id", table_name="calls")
    op.drop_index("ix_calls_lead_id", table_name="calls")
    op.drop_index("ix_calls_user_id", table_name="calls")
    op.drop_table("calls")
