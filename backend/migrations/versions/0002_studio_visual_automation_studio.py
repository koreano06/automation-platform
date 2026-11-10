"""Visual automation studio. Stop API/workers and back up before migrating.

Revision ID: 0002_studio
Revises: 0001_domain
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_studio"
down_revision = "0001_domain"
branch_labels = None
depends_on = None

OLD_ACTIONS = "'open_page', 'locate', 'fill', 'click', 'click_point', 'assert'"
NEW_ACTIONS = OLD_ACTIONS + ", 'click_image', 'click_button', 'assert_image'"


def upgrade():
    op.create_table(
        "reference_images",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    with op.batch_alter_table("automation_steps") as batch:
        batch.add_column(
            sa.Column("button_text", sa.String(120), nullable=False, server_default="")
        )
        batch.add_column(sa.Column("reference_image_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("confidence", sa.Float(), nullable=False, server_default="0.9"))
        batch.create_foreign_key(
            "fk_step_reference_image", "reference_images", ["reference_image_id"], ["id"]
        )
        batch.drop_constraint("ck_step_action", type_="check")
        batch.create_check_constraint("ck_step_action", f"action IN ({NEW_ACTIONS})")
    with op.batch_alter_table("platforms") as batch:
        batch.drop_constraint("ck_platform_mode", type_="check")
        batch.create_check_constraint(
            "ck_platform_mode",
            "mode IN ('simulation', 'power_automate', 'local_browser', 'local_desktop')",
        )


def downgrade():
    connection = op.get_bind()
    if connection.scalar(
        sa.text("SELECT count(*) FROM platforms WHERE mode IN ('local_browser', 'local_desktop')")
    ):
        raise RuntimeError("Há plataformas locais: exporte/converta os fluxos antes do downgrade.")
    if connection.scalar(
        sa.text(
            "SELECT count(*) FROM automation_steps WHERE action IN ('click_image', 'click_button', 'assert_image')"
        )
    ):
        raise RuntimeError("Há etapas visuais: exporte/converta os fluxos antes do downgrade.")
    with op.batch_alter_table("platforms") as batch:
        batch.drop_constraint("ck_platform_mode", type_="check")
        batch.create_check_constraint(
            "ck_platform_mode", "mode IN ('simulation', 'power_automate')"
        )
    with op.batch_alter_table("automation_steps") as batch:
        batch.drop_constraint("fk_step_reference_image", type_="foreignkey")
        batch.drop_constraint("ck_step_action", type_="check")
        batch.create_check_constraint("ck_step_action", f"action IN ({OLD_ACTIONS})")
        batch.drop_column("confidence")
        batch.drop_column("reference_image_id")
        batch.drop_column("button_text")
    op.drop_table("reference_images")
