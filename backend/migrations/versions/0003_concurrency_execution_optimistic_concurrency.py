"""Execution optimistic concurrency.

Revision ID: 0003_concurrency
Revises: 0002_studio
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_concurrency"
down_revision = "0002_studio"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "executions", sa.Column("lock_version", sa.Integer(), nullable=False, server_default="1")
    )


def downgrade():
    with op.batch_alter_table("executions") as batch:
        batch.drop_column("lock_version")
