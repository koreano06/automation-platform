from datetime import UTC, datetime
from typing import ClassVar
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def new_id() -> str:
    return str(uuid4())


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    username: Mapped[str] = mapped_column(String(120), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (CheckConstraint("role IN ('admin', 'operator')", name="ck_user_role"),)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    user: Mapped[User] = relationship()


class Platform(Base):
    __tablename__ = "platforms"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    mode: Mapped[str] = mapped_column(String(30), default="simulation")
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fields: Mapped[list["PlatformField"]] = relationship(
        cascade="all, delete-orphan", order_by="PlatformField.position"
    )
    __table_args__ = (
        Index(
            "uq_platform_name_live",
            "name",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        CheckConstraint(
            "mode IN ('simulation', 'power_automate', 'local_browser', 'local_desktop')",
            name="ck_platform_mode",
        ),
    )


class PlatformField(Base):
    __tablename__ = "platform_fields"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    platform_id: Mapped[str] = mapped_column(
        ForeignKey("platforms.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(60))
    label: Mapped[str] = mapped_column(String(120))
    field_type: Mapped[str] = mapped_column(String(20))
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    options: Mapped[list] = mapped_column(JSON, default=list)
    position: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (
        UniqueConstraint("platform_id", "key", name="uq_platform_field"),
        CheckConstraint(
            "field_type IN ('text', 'email', 'integer', 'select')", name="ck_field_type"
        ),
    )


class AutomationDefinition(Base):
    __tablename__ = "automation_definitions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    platform_id: Mapped[str] = mapped_column(ForeignKey("platforms.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    steps: Mapped[list["AutomationStep"]] = relationship(
        cascade="all, delete-orphan", order_by="AutomationStep.position"
    )
    __table_args__ = (
        UniqueConstraint("platform_id", "version", name="uq_platform_version"),
        CheckConstraint(
            "status IN ('draft', 'validated', 'archived')", name="ck_automation_status"
        ),
    )


class AutomationStep(Base):
    __tablename__ = "automation_steps"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    automation_id: Mapped[str] = mapped_column(
        ForeignKey("automation_definitions.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(30))
    locator: Mapped[str] = mapped_column(String(500), default="")
    value: Mapped[str] = mapped_column(String(500), default="")
    data_ref: Mapped[str] = mapped_column(String(80), default="")
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)
    success_condition: Mapped[str] = mapped_column(String(500), default="")
    screen_context: Mapped[dict] = mapped_column(JSON, default=dict)
    button_text: Mapped[str] = mapped_column(String(120), default="")
    reference_image_id: Mapped[str | None] = mapped_column(
        ForeignKey("reference_images.id"), nullable=True
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.9)
    on_match: Mapped[str] = mapped_column(String(20), default="finish_success")
    skip_steps: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (
        UniqueConstraint("automation_id", "position", name="uq_step_position"),
        CheckConstraint("timeout_seconds BETWEEN 1 AND 300", name="ck_step_timeout"),
        CheckConstraint(
            "action IN ('open_page', 'locate', 'fill', 'click', 'click_point', 'assert', 'click_image', 'click_button', 'assert_image', 'wait_image', 'if_exists', 'pause')",
            name="ck_step_action",
        ),
    )


class ProvisioningRequest(Base):
    __tablename__ = "provisioning_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(120))
    payload_hash: Mapped[str] = mapped_column(String(64))
    employee: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="queued")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    executions: Mapped[list["Execution"]] = relationship(order_by="Execution.created_at")
    __table_args__ = (
        UniqueConstraint("requested_by", "idempotency_key", name="uq_request_idempotency"),
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'partially_succeeded', 'failed')",
            name="ck_request_status",
        ),
    )


class Execution(Base):
    __tablename__ = "executions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    request_id: Mapped[str] = mapped_column(ForeignKey("provisioning_requests.id"), index=True)
    platform_id: Mapped[str] = mapped_column(ForeignKey("platforms.id"))
    platform: Mapped[Platform] = relationship()
    automation_id: Mapped[str] = mapped_column(ForeignKey("automation_definitions.id"))
    platform_name: Mapped[str] = mapped_column(String(120))
    mode: Mapped[str] = mapped_column(String(30))
    snapshot: Mapped[dict] = mapped_column(JSON)
    employee_key: Mapped[str] = mapped_column(String(254))
    active_lock: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    external_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    awaiting_operator: Mapped[bool] = mapped_column(Boolean, default=False)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    __mapper_args__: ClassVar[dict] = {"version_id_col": lock_version}
    events: Mapped[list["ExecutionEvent"]] = relationship(
        cascade="all, delete-orphan", order_by="ExecutionEvent.sequence"
    )
    __table_args__ = (
        UniqueConstraint("request_id", "platform_id", name="uq_request_platform"),
        UniqueConstraint("platform_id", "employee_key", "active_lock", name="uq_active_employee"),
        CheckConstraint(
            "status IN ('queued', 'dispatching', 'running', 'succeeded', 'failed', 'cancelled')",
            name="ck_execution_status",
        ),
        Index("ix_execution_queue", "status", "created_at"),
    )


class ExecutionEvent(Base):
    __tablename__ = "execution_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    execution_id: Mapped[str] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    external_event_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    step: Mapped[int | None] = mapped_column(Integer, nullable=True)
    level: Mapped[str] = mapped_column(String(20), default="info")
    message: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (
        UniqueConstraint("execution_id", "sequence", name="uq_event_sequence"),
        UniqueConstraint("execution_id", "external_event_id", name="uq_external_event"),
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str] = mapped_column(String(120))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Account(Base):
    """Simulation ledger; stores no passwords and makes repeat processing idempotent."""

    __tablename__ = "simulated_accounts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    platform_id: Mapped[str] = mapped_column(ForeignKey("platforms.id"))
    employee_key: Mapped[str] = mapped_column(String(254))
    execution_id: Mapped[str] = mapped_column(ForeignKey("executions.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint("platform_id", "employee_key", name="uq_simulated_account"),)


class ReferenceImage(Base):
    __tablename__ = "reference_images"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    version: Mapped[str] = mapped_column(String(30))
    build_id: Mapped[str] = mapped_column(String(12))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    job_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    job_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)


class StepTest(Base):
    __tablename__ = "step_tests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    platform_id: Mapped[str] = mapped_column(ForeignKey("platforms.id"))
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    mode: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    preview_only: Mapped[bool] = mapped_column(Boolean, default=True)
    snapshot: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed')", name="ck_step_test_status"
        ),
    )


class DiagnosticArtifact(Base):
    __tablename__ = "diagnostic_artifacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    execution_id: Mapped[str | None] = mapped_column(
        ForeignKey("executions.id"), nullable=True, index=True
    )
    step_test_id: Mapped[str | None] = mapped_column(
        ForeignKey("step_tests.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
