"""Add immutable M-Pesa receipt snapshot to tickets."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0008_ticket_receipt_snapshot"
down_revision = "0007_automatic_backup_owner"
branch_labels = None
depends_on = None


def upgrade():
    if "mpesa_receipt_snapshot" not in {column["name"] for column in inspect(op.get_bind()).get_columns("tickets")}: op.add_column("tickets", sa.Column("mpesa_receipt_snapshot", sa.String(length=120), nullable=True))


def downgrade():
    op.drop_column("tickets", "mpesa_receipt_snapshot")
