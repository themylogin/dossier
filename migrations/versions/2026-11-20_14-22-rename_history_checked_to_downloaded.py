"""rename_history_checked_to_downloaded"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("chats") as batch_op:
        batch_op.alter_column("history_checked", new_column_name="downloaded")


def downgrade() -> None:
    with op.batch_alter_table("chats") as batch_op:
        batch_op.alter_column("downloaded", new_column_name="history_checked")
