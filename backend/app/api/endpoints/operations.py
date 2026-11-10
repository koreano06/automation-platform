from datetime import timedelta

from alembic.script import ScriptDirectory
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.version import BUILD_ID
from app.database.migrations import migration_config
from app.database.session import get_db
from app.models import AuditEvent, Execution, StepTest, User, WorkerHeartbeat
from app.models.domain import utcnow
from app.schemas import AuditRead
from app.security import admin_user

router = APIRouter(tags=["Operations"])


@router.get("/audit-events", response_model=list[AuditRead])
def audit_events(
    limit: int = Query(100, ge=1, le=500),
    _: User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    return [
        {
            "id": event.id,
            "actor_id": event.actor_id,
            "action": event.action,
            "resource_id": event.resource_id,
            "details": event.details,
            "created_at": event.created_at,
        }
        for event in db.scalars(
            select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)
        )
    ]


@router.get("/system")
def system(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    expected = ScriptDirectory.from_config(migration_config()).get_current_head()
    current = (
        db.scalar(text("SELECT version_num FROM alembic_version"))
        if "alembic_version" in inspect(db.get_bind()).get_table_names()
        else None
    )
    workers = db.scalars(
        select(WorkerHeartbeat).where(WorkerHeartbeat.last_seen >= utcnow() - timedelta(seconds=15))
    ).all()
    compatible = [
        worker
        for worker in workers
        if worker.version == settings.app_version and worker.build_id == BUILD_ID
    ]
    return {
        "api_version": settings.app_version,
        "build_id": BUILD_ID,
        "schema": {"current": current, "expected": expected, "up_to_date": current == expected},
        "database": {"kind": db.get_bind().dialect.name, "connected": True},
        "worker": {
            "status": "online" if compatible else "outdated" if workers else "offline",
            "active_count": len(workers),
            "last_seen": max((worker.last_seen for worker in workers), default=None),
            "busy_count": sum(bool(worker.job_id) for worker in workers),
        },
        "runner_enabled": settings.local_runner_enabled,
        "allowed_hosts": settings.local_allowed_hosts,
        "step_test_queue": db.scalar(
            select(func.count()).select_from(StepTest).where(StepTest.status == "queued")
        ),
        "integration_configured": bool(
            settings.power_automate_url.get_secret_value()
            and settings.power_automate_callback_secret.get_secret_value()
        ),
        "integration_retry_safe": settings.power_automate_idempotent,
        "max_attempts": settings.max_attempts,
        "queued_count": db.scalar(
            select(func.count()).select_from(Execution).where(Execution.status == "queued")
        ),
    }
