"""Tables of bot.py"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # bot.py created these tables without Alembic. if_not_exists lets this revision adopt such a database.
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chat_id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("sender_id", sa.Integer(), nullable=True),
        sa.Column("grouped_id", sa.Integer(), nullable=True),
        sa.Column("has_media", sa.Boolean(), nullable=True),
        sa.Column("media_type", sa.Text(), nullable=True),
        sa.Column("media_path", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chat_id", "message_id"),
        if_not_exists=True,
    )
    op.create_index("idx_chat_message", "messages", ["chat_id", "message_id"], if_not_exists=True)
    op.create_index("idx_date", "messages", ["date"], if_not_exists=True)
    op.create_table(
        "chats",
        sa.Column("chat_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("type", sa.Text(), nullable=True),
        sa.Column("username", sa.Text(), nullable=True),
        sa.Column("tracked", sa.Boolean(), nullable=True),
        sa.Column("downloads_media", sa.Boolean(), nullable=True),
        sa.Column("first_seen_at", sa.Text(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.Text(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("chat_id"),
        if_not_exists=True,
    )
    op.create_table(
        "users",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.Text(), nullable=True),
        sa.Column("first_name", sa.Text(), nullable=True),
        sa.Column("last_name", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("is_bot", sa.Boolean(), nullable=True),
        sa.Column("first_seen_at", sa.Text(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.Text(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("user_id"),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_table("users")
    op.drop_table("chats")
    op.drop_index("idx_date", table_name="messages")
    op.drop_index("idx_chat_message", table_name="messages")
    op.drop_table("messages")
