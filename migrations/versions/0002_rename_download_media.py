"""Rename chats.downloads_media to chats.download_media"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("chats") as batch_op:
        batch_op.alter_column("downloads_media", new_column_name="download_media")


def downgrade() -> None:
    with op.batch_alter_table("chats") as batch_op:
        batch_op.alter_column("download_media", new_column_name="downloads_media")
