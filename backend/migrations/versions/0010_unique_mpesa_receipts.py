"""Prevent reuse of an M-Pesa receipt across payments."""
from alembic import op


revision = "0010_unique_mpesa_receipts"
down_revision = "0009_event_journal_gallery"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("uq_payments_mpesa_receipt", "payments", ["mpesa_receipt"], unique=True)


def downgrade():
    op.drop_index("uq_payments_mpesa_receipt", table_name="payments")
