"""Add SEO metadata storage.

Revision ID: 0003_seo_metadata
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0003_seo_metadata"
down_revision = "0002_notification_archive"
branch_labels = None
depends_on = None

def upgrade():
    if not inspect(op.get_bind()).has_table("seo_metadata"):
        op.create_table("seo_metadata", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("retreat_id", sa.Integer(), sa.ForeignKey("retreats.id"), unique=True), sa.Column("path", sa.String(length=300), nullable=False), sa.Column("page_title", sa.String(length=180), nullable=False), sa.Column("meta_description", sa.String(length=320), nullable=False), sa.Column("social_image_url", sa.String(length=500)), sa.UniqueConstraint("path"))
        op.create_index("ix_seo_metadata_path", "seo_metadata", ["path"], unique=True)

def downgrade():
    op.drop_index("ix_seo_metadata_path", table_name="seo_metadata")
    op.drop_table("seo_metadata")
