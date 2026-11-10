import hashlib
import json
import re

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    AutomationDefinition,
    Execution,
    ExecutionEvent,
    Platform,
    ProvisioningRequest,
    User,
)
from app.models.domain import utcnow
from app.schemas import RequestInput
from app.security import audit

TERMINAL = {"succeeded", "failed", "cancelled"}
TRANSITIONS = {
    "queued": {"dispatching", "cancelled"},
    "dispatching": {"running", "failed", "cancelled"},
    "running": {"succeeded", "failed", "cancelled"},
    "failed": {"queued"},
    "succeeded": set(),
    "cancelled": set(),
}


def add_event(
    db: Session,
    execution: Execution,
    message: str,
    *,
    level="info",
    step=None,
    external_event_id=None,
):
    db.flush()
    sequence = (
        db.scalar(
            select(func.max(ExecutionEvent.sequence)).where(
                ExecutionEvent.execution_id == execution.id
            )
        )
        or 0
    ) + 1
    db.add(
        ExecutionEvent(
            execution_id=execution.id,
            sequence=sequence,
            level=level,
            step=step,
            message=message,
            external_event_id=external_event_id,
        )
    )


def aggregate_request(db: Session, request_id: str):
    db.flush()
    request = db.get(ProvisioningRequest, request_id)
    states = list(db.scalars(select(Execution.status).where(Execution.request_id == request_id)))
    if all(state == "queued" for state in states):
        request.status = "queued"
    elif any(state not in TERMINAL for state in states):
        request.status = "running"
    elif all(state == "succeeded" for state in states):
        request.status = "succeeded"
    elif any(state == "succeeded" for state in states):
        request.status = "partially_succeeded"
    else:
        request.status = "failed"


def transition(db: Session, execution: Execution, target: str, message: str, **event):
    if target not in TRANSITIONS[execution.status]:
        raise HTTPException(409, "Transição de estado inválida.")
    execution.status = target
    execution.heartbeat_at = utcnow()
    if target in TERMINAL:
        execution.awaiting_operator = False
        execution.finished_at = utcnow()
        execution.active_lock = None
    if target == "queued":
        execution.cancel_requested = False
        execution.awaiting_operator = False
        execution.active_lock = True
        execution.finished_at = None
        execution.started_at = None
        execution.error_code = None
        execution.result = {}
        execution.external_id = None
    add_event(db, execution, message, **event)
    aggregate_request(db, execution.request_id)


def validate_fields(platform: Platform, values: dict):
    definitions = {field.key: field for field in platform.fields}
    if set(values) - set(definitions):
        raise HTTPException(422, "Campos não definidos para a plataforma.")
    clean = {}
    for key, field in definitions.items():
        value = values.get(key)
        if value is None or value == "":
            if field.required:
                raise HTTPException(422, f"O campo {field.label} é obrigatório.")
            continue
        if field.field_type == "integer":
            if isinstance(value, bool) or not isinstance(value, int) or abs(value) > 2**31 - 1:
                raise HTTPException(422, f"O campo {field.label} precisa ser um inteiro válido.")
        elif not isinstance(value, str) or len(value) > 500:
            raise HTTPException(
                422, f"O campo {field.label} precisa ser texto com até 500 caracteres."
            )
        if field.field_type == "email" and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise HTTPException(422, f"O campo {field.label} precisa ser um e-mail.")
        if field.field_type == "select" and value not in field.options:
            raise HTTPException(422, f"Opção inválida para {field.label}.")
        clean[key] = value
    return clean


def create_request(db: Session, payload: RequestInput, key: str, user: User):
    if not 8 <= len(key) <= 120:
        raise HTTPException(422, "Informe uma chave de idempotência entre 8 e 120 caracteres.")
    encoded = json.dumps(payload.model_dump(), sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    existing = db.scalar(
        select(ProvisioningRequest).where(
            ProvisioningRequest.requested_by == user.id, ProvisioningRequest.idempotency_key == key
        )
    )
    if existing:
        if existing.payload_hash != digest:
            raise HTTPException(409, "A chave já foi usada com outros dados.")
        return existing, True
    targets = []
    for target in payload.targets:
        platform = db.get(Platform, target.platform_id)
        if not platform or platform.deleted_at is not None:
            raise HTTPException(404, "Plataforma não encontrada.")
        if not platform.active:
            raise HTTPException(409, "A plataforma está desativada.")
        automation = db.scalar(
            select(AutomationDefinition)
            .where(
                AutomationDefinition.platform_id == platform.id,
                AutomationDefinition.status == "validated",
            )
            .order_by(AutomationDefinition.version.desc())
        )
        if not automation:
            raise HTTPException(409, "A plataforma não possui uma automação validada.")
        fields = validate_fields(platform, target.fields)
        if db.scalar(
            select(Execution.id).where(
                Execution.platform_id == platform.id,
                Execution.employee_key == payload.employee.email,
                Execution.active_lock.is_(True),
            )
        ):
            raise HTTPException(
                409, "Já há um cadastro pendente para este colaborador e plataforma."
            )
        targets.append((platform, automation, fields))
    item = ProvisioningRequest(
        requested_by=user.id,
        idempotency_key=key,
        payload_hash=digest,
        employee=payload.employee.model_dump(),
    )
    db.add(item)
    db.flush()
    for platform, automation, fields in targets:
        from app.services.platforms import automation_read

        execution = Execution(
            request_id=item.id,
            platform_id=platform.id,
            automation_id=automation.id,
            platform_name=platform.name,
            mode=platform.mode,
            employee_key=payload.employee.email,
            snapshot={
                "employee": payload.employee.model_dump(),
                "fields": fields,
                "automation": automation_read(automation)["steps"],
                "config": platform.config,
                "version": automation.version,
            },
        )
        db.add(execution)
        db.flush()
        add_event(db, execution, "Execução enfileirada.")
    audit(db, user, "request.created", item.id, platform_count=len(targets))
    for platform, _, _ in targets:
        db.refresh(platform)
        if platform.deleted_at is not None or not platform.active:
            raise HTTPException(409, "A plataforma foi removida ou desativada durante o envio.")
    db.commit()
    return item, False


def request_for_user(db: Session, request_id: str, user: User):
    item = db.get(ProvisioningRequest, request_id)
    if not item or (user.role != "admin" and item.requested_by != user.id):
        raise HTTPException(404, "Solicitação não encontrada.")
    return item


def execution_for_user(db: Session, execution_id: str, user: User):
    execution = db.get(Execution, execution_id)
    if not execution:
        raise HTTPException(404, "Execução não encontrada.")
    request_for_user(db, execution.request_id, user)
    return execution


def execution_read(execution: Execution):
    return {
        "id": execution.id,
        "awaiting_operator": execution.awaiting_operator,
        "cancel_requested": execution.cancel_requested,
        "request_id": execution.request_id,
        "platform_id": execution.platform_id,
        "platform_name": execution.platform_name,
        "mode": execution.mode,
        "status": execution.status,
        "attempts": execution.attempts,
        "external_id": execution.external_id,
        "result": execution.result,
        "error_code": execution.error_code,
        "created_at": execution.created_at,
        "started_at": execution.started_at,
        "finished_at": execution.finished_at,
        "can_retry": execution.platform.deleted_at is None
        and execution.status == "failed"
        and execution.attempts < settings.max_attempts
        and (
            execution.mode == "simulation"
            or (execution.mode == "power_automate" and settings.power_automate_idempotent)
        ),
    }


def request_read(item: ProvisioningRequest):
    return {
        "id": item.id,
        "employee": item.employee,
        "status": item.status,
        "requested_by": item.requested_by,
        "created_at": item.created_at,
        "executions": [execution_read(execution) for execution in item.executions],
    }
