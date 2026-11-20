"""drop_first_seen_at"""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("chats", "users"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column("first_seen_at")


def downgrade() -> None:
    for table in ("chats", "users"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(
                sa.Column("first_seen_at", sa.Text(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)
            )
