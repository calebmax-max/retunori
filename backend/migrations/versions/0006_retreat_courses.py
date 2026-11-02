"""Add retreat-specific course options."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0006_retreat_courses"
down_revision = "0005_retreat_images"
branch_labels = None
depends_on = None


def upgrade():
    if inspect(op.get_bind()).has_table("retreat_courses"): return
    op.create_table("retreat_courses", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("retreat_id", sa.Integer(), sa.ForeignKey("retreats.id", ondelete="CASCADE"), nullable=False), sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False), sa.UniqueConstraint("retreat_id", "course_id", name="uq_retreat_course"))
    op.create_index("ix_retreat_courses_retreat_id", "retreat_courses", ["retreat_id"])
    op.create_index("ix_retreat_courses_course_id", "retreat_courses", ["course_id"])


def downgrade():
    op.drop_index("ix_retreat_courses_course_id", table_name="retreat_courses")
    op.drop_index("ix_retreat_courses_retreat_id", table_name="retreat_courses")
    op.drop_table("retreat_courses")
