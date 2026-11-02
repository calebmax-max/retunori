"""Add notification archive state.

Revision ID: 0002_notification_archive
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0002_notification_archive"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade():
    if "is_archived" not in {column["name"] for column in inspect(op.get_bind()).get_columns("notifications")}: op.add_column("notifications", sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()))

def downgrade():
    if "is_archived" in {column["name"] for column in inspect(op.get_bind()).get_columns("notifications")}: op.drop_column("notifications", "is_archived")
