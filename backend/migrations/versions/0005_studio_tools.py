"""Worker diagnostics, step tests, flow decisions and operator controls.

Revision ID: 0005_studio_tools
Revises: 0004_platform_delete
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_studio_tools"
down_revision = "0004_platform_delete"
branch_labels = None
depends_on = None
OLD_ACTIONS = "'open_page','locate','fill','click','click_point','assert','click_image','click_button','assert_image'"
NEW_ACTIONS = OLD_ACTIONS + ",'wait_image','if_exists','pause'"


def upgrade():
    with op.batch_alter_table("automation_steps") as batch:
        batch.add_column(
            sa.Column("on_match", sa.String(20), nullable=False, server_default="finish_success")
        )
        batch.add_column(sa.Column("skip_steps", sa.Integer(), nullable=False, server_default="1"))
        batch.drop_constraint("ck_step_action", type_="check")
        batch.create_check_constraint("ck_step_action", f"action IN ({NEW_ACTIONS})")
    op.add_column(
        "executions",
        sa.Column("awaiting_operator", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "executions",
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "worker_heartbeats",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("version", sa.String(30), nullable=False),
        sa.Column("build_id", sa.String(12), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen", sa.DateTime(), nullable=False),
        sa.Column("job_id", sa.String(36), nullable=True),
        sa.Column("job_kind", sa.String(20), nullable=True),
    )
    op.create_index("ix_worker_heartbeats_last_seen", "worker_heartbeats", ["last_seen"])
    op.create_table(
        "step_tests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("platform_id", sa.String(36), sa.ForeignKey("platforms.id"), nullable=False),
        sa.Column("requested_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("mode", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("preview_only", sa.Boolean(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','failed')", name="ck_step_test_status"
        ),
    )
    op.create_index("ix_step_tests_status", "step_tests", ["status"])
    op.create_table(
        "diagnostic_artifacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("execution_id", sa.String(36), sa.ForeignKey("executions.id"), nullable=True),
        sa.Column("step_test_id", sa.String(36), sa.ForeignKey("step_tests.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_diagnostic_artifacts_execution_id", "diagnostic_artifacts", ["execution_id"]
    )
    op.create_index(
        "ix_diagnostic_artifacts_step_test_id", "diagnostic_artifacts", ["step_test_id"]
    )


def downgrade():
    connection = op.get_bind()
    if connection.scalar(
        sa.text(
            "SELECT count(*) FROM automation_steps WHERE action IN ('wait_image','if_exists','pause')"
        )
    ):
        raise RuntimeError("Exporte/converta as novas ações antes do downgrade.")
    if connection.scalar(sa.text("SELECT count(*) FROM step_tests")):
        raise RuntimeError("Há testes de etapas: exporte-os antes do downgrade.")
    op.drop_table("diagnostic_artifacts")
    op.drop_table("step_tests")
    op.drop_table("worker_heartbeats")
    with op.batch_alter_table("executions") as batch:
        batch.drop_column("cancel_requested")
        batch.drop_column("awaiting_operator")
    with op.batch_alter_table("automation_steps") as batch:
        batch.drop_constraint("ck_step_action", type_="check")
        batch.create_check_constraint("ck_step_action", f"action IN ({OLD_ACTIONS})")
        batch.drop_column("on_match")
        batch.drop_column("skip_steps")
