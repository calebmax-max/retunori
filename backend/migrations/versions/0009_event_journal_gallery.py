"""Add event gallery details to journal announcements."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0009_event_journal_gallery"
down_revision = "0008_ticket_receipt_snapshot"
branch_labels = None
depends_on = None


def upgrade():
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("announcements")}
    if "retreat_id" not in columns:
        op.add_column("announcements", sa.Column("retreat_id", sa.Integer(), nullable=True))
        op.create_index("ix_announcements_retreat_id", "announcements", ["retreat_id"])
    if "expires_at" not in columns:
        op.add_column("announcements", sa.Column("expires_at", sa.DateTime(), nullable=True))
        op.create_index("ix_announcements_expires_at", "announcements", ["expires_at"])
    if "image_urls" not in columns:
        op.add_column("announcements", sa.Column("image_urls", sa.Text(), nullable=False, server_default="[]"))


def downgrade():
    op.drop_column("announcements", "image_urls")
    op.drop_index("ix_announcements_expires_at", "announcements")
    op.drop_column("announcements", "expires_at")
    op.drop_index("ix_announcements_retreat_id", "announcements")
    op.drop_column("announcements", "retreat_id")
