"""Add scheduled sales windows."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0004_sales_schedule"
down_revision = "0003_seo_metadata"
branch_labels = None
depends_on = None


def upgrade():
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("retreats")}
    if "sales_opens_at" not in columns: op.add_column("retreats", sa.Column("sales_opens_at", sa.DateTime(), nullable=True))
    if "sales_closes_at" not in columns: op.add_column("retreats", sa.Column("sales_closes_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("retreats", "sales_closes_at")
    op.drop_column("retreats", "sales_opens_at")
