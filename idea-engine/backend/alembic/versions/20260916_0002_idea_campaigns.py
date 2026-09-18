"""add campaigns column to idea lead report items

Revision ID: 20260916_0002_idea
Revises: 20260916_0001_idea
Create Date: 2026-09-18 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260916_0002_idea"
down_revision: Union[str, None] = "20260916_0001_idea"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "idea_lead_report_items",
        sa.Column(
            "campaigns",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("idea_lead_report_items", "campaigns")