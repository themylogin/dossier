"""history_checked_and_versions"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("chats", sa.Column("history_checked", sa.Boolean(), server_default=sa.text("0"), nullable=False))
    op.add_column("messages", sa.Column("edit_date", sa.Text(), nullable=True))
    op.add_column("messages", sa.Column("media_id", sa.Integer(), nullable=True))
    op.add_column("messages", sa.Column("media_replaced_at", sa.Text(), nullable=True))
    op.create_table(
        "message_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chat_id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("version_date", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("has_media", sa.Boolean(), nullable=False),
        sa.Column("media_type", sa.Text(), nullable=True),
        sa.Column("media_path", sa.Text(), nullable=True),
        sa.Column("media_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.Text(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chat_id", "message_id", "version_date"),
    )


def downgrade() -> None:
    op.drop_table("message_versions")
    with op.batch_alter_table("messages") as batch_op:
        batch_op.drop_column("media_replaced_at")
        batch_op.drop_column("media_id")
        batch_op.drop_column("edit_date")
    with op.batch_alter_table("chats") as batch_op:
        batch_op.drop_column("history_checked")
