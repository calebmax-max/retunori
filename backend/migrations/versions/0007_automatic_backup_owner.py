"""Allow system-created automatic backups."""
from alembic import op

revision = "0007_automatic_backup_owner"
down_revision = "0006_retreat_courses"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("backups") as batch:
        batch.alter_column("created_by", nullable=True)


def downgrade():
    with op.batch_alter_table("backups") as batch:
        batch.alter_column("created_by", nullable=False)
