"""Not null columns"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("chats", schema=None) as batch_op:
        batch_op.alter_column("name", existing_type=sa.TEXT(), nullable=False)
        batch_op.alter_column("type", existing_type=sa.TEXT(), nullable=False)
        batch_op.alter_column("tracked", existing_type=sa.BOOLEAN(), nullable=False)
        batch_op.alter_column("download_media", existing_type=sa.BOOLEAN(), nullable=False)
        batch_op.alter_column(
            "first_seen_at",
            existing_type=sa.TEXT(),
            nullable=False,
            existing_server_default=sa.text("(CURRENT_TIMESTAMP)"),
        )
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.TEXT(),
            nullable=False,
            existing_server_default=sa.text("(CURRENT_TIMESTAMP)"),
        )

    with op.batch_alter_table("messages", schema=None) as batch_op:
        batch_op.alter_column("date", existing_type=sa.TEXT(), nullable=False)
        batch_op.alter_column("text", existing_type=sa.TEXT(), nullable=False)
        batch_op.alter_column("has_media", existing_type=sa.BOOLEAN(), nullable=False)
        batch_op.alter_column(
            "created_at",
            existing_type=sa.TEXT(),
            nullable=False,
            existing_server_default=sa.text("(CURRENT_TIMESTAMP)"),
        )

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("is_bot", existing_type=sa.BOOLEAN(), nullable=False)
        batch_op.alter_column(
            "first_seen_at",
            existing_type=sa.TEXT(),
            nullable=False,
            existing_server_default=sa.text("(CURRENT_TIMESTAMP)"),
        )
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.TEXT(),
            nullable=False,
            existing_server_default=sa.text("(CURRENT_TIMESTAMP)"),
        )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "updated_at", existing_type=sa.TEXT(), nullable=True, existing_server_default=sa.text("(CURRENT_TIMESTAMP)")
        )
        batch_op.alter_column(
            "first_seen_at",
            existing_type=sa.TEXT(),
            nullable=True,
            existing_server_default=sa.text("(CURRENT_TIMESTAMP)"),
        )
        batch_op.alter_column("is_bot", existing_type=sa.BOOLEAN(), nullable=True)

    with op.batch_alter_table("messages", schema=None) as batch_op:
        batch_op.alter_column(
            "created_at", existing_type=sa.TEXT(), nullable=True, existing_server_default=sa.text("(CURRENT_TIMESTAMP)")
        )
        batch_op.alter_column("has_media", existing_type=sa.BOOLEAN(), nullable=True)
        batch_op.alter_column("text", existing_type=sa.TEXT(), nullable=True)
        batch_op.alter_column("date", existing_type=sa.TEXT(), nullable=True)

    with op.batch_alter_table("chats", schema=None) as batch_op:
        batch_op.alter_column(
            "updated_at", existing_type=sa.TEXT(), nullable=True, existing_server_default=sa.text("(CURRENT_TIMESTAMP)")
        )
        batch_op.alter_column(
            "first_seen_at",
            existing_type=sa.TEXT(),
            nullable=True,
            existing_server_default=sa.text("(CURRENT_TIMESTAMP)"),
        )
        batch_op.alter_column("download_media", existing_type=sa.BOOLEAN(), nullable=True)
        batch_op.alter_column("tracked", existing_type=sa.BOOLEAN(), nullable=True)
        batch_op.alter_column("type", existing_type=sa.TEXT(), nullable=True)
        batch_op.alter_column("name", existing_type=sa.TEXT(), nullable=True)
