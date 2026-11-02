"""Add managed retreat images."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0005_retreat_images"
down_revision = "0004_sales_schedule"
branch_labels = None
depends_on = None


def upgrade():
    if inspect(op.get_bind()).has_table("retreat_images"): return
    op.create_table(
        "retreat_images",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("retreat_id", sa.Integer(), sa.ForeignKey("retreats.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("alt_text", sa.String(length=180), nullable=False, server_default="RETUNORI retreat image"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_retreat_images_retreat_id", "retreat_images", ["retreat_id"])


def downgrade():
    op.drop_index("ix_retreat_images_retreat_id", table_name="retreat_images")
    op.drop_table("retreat_images")
