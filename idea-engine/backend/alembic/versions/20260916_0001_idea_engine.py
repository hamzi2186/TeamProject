"""create idea engine report tables

Revision ID: 20260916_0001_idea
Revises: 
Create Date: 2026-09-16 16:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260916_0001_idea"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. idea_report_runs
    op.create_table(
        "idea_report_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("total_leads", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("document_path", sa.Text(), nullable=True),
        sa.Column("document_filename", sa.String(length=255), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("report_date", name="uq_idea_report_runs_date"),
    )
    op.create_index("ix_idea_report_runs_report_date", "idea_report_runs", ["report_date"])
    op.create_index("ix_idea_report_runs_status", "idea_report_runs", ["status"])

    # 2. idea_lead_report_items
    op.create_table(
        "idea_lead_report_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "report_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("idea_report_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("final_outcome", sa.String(length=64), nullable=False),
        sa.Column("approach_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("conversation_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("outcome_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("recommended_next_action", sa.Text(), nullable=True),
        sa.Column("first_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("report_run_id", "lead_id", name="uq_idea_lead_items_run_lead"),
    )
    op.create_index("ix_idea_lead_report_items_report_run_id", "idea_lead_report_items", ["report_run_id"])
    op.create_index("ix_idea_lead_report_items_lead_id", "idea_lead_report_items", ["lead_id"])
    op.create_index("ix_idea_lead_report_items_user_id", "idea_lead_report_items", ["user_id"])
    op.create_index("ix_idea_lead_report_items_final_outcome", "idea_lead_report_items", ["final_outcome"])


def downgrade() -> None:
    op.drop_table("idea_lead_report_items")
    op.drop_table("idea_report_runs")
