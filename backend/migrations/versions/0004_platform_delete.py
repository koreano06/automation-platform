"""Remove platforms from active use while preserving execution history.

Revision ID: 0004_platform_delete
Revises: 0003_concurrency
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_platform_delete"
down_revision = "0003_concurrency"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table(
        "platforms", naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"}
    ) as batch:
        batch.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        batch.drop_constraint("uq_platforms_name", type_="unique")
    op.create_index(
        "uq_platform_name_live",
        "platforms",
        ["name"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade():
    duplicates = op.get_bind().scalar(
        sa.text(
            "SELECT COUNT(*) FROM (SELECT name FROM platforms GROUP BY name HAVING COUNT(*) > 1) duplicates"
        )
    )
    if duplicates:
        raise RuntimeError(
            "Há nomes reutilizados após exclusão. Resolva as duplicidades antes do downgrade."
        )
    op.drop_index("uq_platform_name_live", table_name="platforms")
    with op.batch_alter_table("platforms") as batch:
        batch.drop_column("deleted_at")
        batch.create_unique_constraint("uq_platforms_name", ["name"])
