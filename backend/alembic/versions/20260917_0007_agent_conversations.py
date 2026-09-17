"""Create Agent conversations and messages tables.

Revision ID: 20260917_0007
Revises: 20260916_0006
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260917_0007"
down_revision = "20260916_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "agent_conversations" not in existing_tables:
        op.create_table(
            "agent_conversations",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=True),
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
            sa.ForeignKeyConstraint(["user_id"], ["app_users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_agent_conversations_user_id",
            "agent_conversations",
            ["user_id"],
        )
        op.create_index(
            "ix_agent_conversations_user_updated",
            "agent_conversations",
            ["user_id", sa.text("updated_at DESC")],
        )

    if "agent_messages" not in existing_tables:
        op.create_table(
            "agent_messages",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column(
                "sources",
                postgresql.JSONB(),
                server_default=sa.text("'[]'::jsonb"),
                nullable=False,
            ),
            sa.Column("generation", postgresql.JSONB(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_agent_messages_role"),
            sa.ForeignKeyConstraint(
                ["conversation_id"], ["agent_conversations.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_agent_messages_conversation_id",
            "agent_messages",
            ["conversation_id"],
        )
        op.create_index(
            "ix_agent_messages_created_at",
            "agent_messages",
            ["created_at"],
        )


def downgrade() -> None:
    op.drop_index("ix_agent_messages_created_at", table_name="agent_messages")
    op.drop_index("ix_agent_messages_conversation_id", table_name="agent_messages")
    op.drop_table("agent_messages")

    op.drop_index("ix_agent_conversations_user_updated", table_name="agent_conversations")
    op.drop_index("ix_agent_conversations_user_id", table_name="agent_conversations")
    op.drop_table("agent_conversations")

