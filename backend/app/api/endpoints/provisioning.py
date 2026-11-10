from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.models import ExecutionEvent, ProvisioningRequest, User
from app.schemas import EventRead, ExecutionRead, RequestInput, RequestRead
from app.security import audit, current_user
from app.services.provisioning import (
    create_request,
    execution_for_user,
    execution_read,
    request_for_user,
    request_read,
    transition,
)

router = APIRouter(tags=["Provisioning & Executions"])


@router.post("/provisioning-requests", status_code=202, response_model=RequestRead)
def submit(
    payload: RequestInput,
    response: Response,
    idempotency_key: str = Header(default=""),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    item, replay = create_request(db, payload, idempotency_key, user)
    if replay:
        response.status_code = 200
    return request_read(item)


@router.get("/provisioning-requests", response_model=list[RequestRead])
def list_requests(
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    statement = (
        select(ProvisioningRequest).order_by(ProvisioningRequest.created_at.desc()).limit(limit)
    )
    if user.role != "admin":
        statement = statement.where(ProvisioningRequest.requested_by == user.id)
    return [request_read(item) for item in db.scalars(statement)]


@router.get("/provisioning-requests/{request_id}", response_model=RequestRead)
def get_request(request_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return request_read(request_for_user(db, request_id, user))


@router.get("/executions/{execution_id}", response_model=ExecutionRead)
def get_execution(
    execution_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    return execution_read(execution_for_user(db, execution_id, user))


@router.get("/executions/{execution_id}/events", response_model=list[EventRead])
def get_events(
    execution_id: str,
    after: int = Query(0, ge=0),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    execution_for_user(db, execution_id, user)
    return db.scalars(
        select(ExecutionEvent)
        .where(ExecutionEvent.execution_id == execution_id, ExecutionEvent.sequence > after)
        .order_by(ExecutionEvent.sequence)
    ).all()


@router.post("/executions/{execution_id}/retry", response_model=ExecutionRead)
def retry(execution_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    execution = execution_for_user(db, execution_id, user)
    if execution.platform.deleted_at is not None:
        raise HTTPException(409, "A plataforma foi excluída e não aceita novas execuções.")
    if execution.status != "failed" or execution.attempts >= settings.max_attempts:
        raise HTTPException(409, "A execução não permite nova tentativa.")
    if execution.mode != "simulation" and not (
        execution.mode == "power_automate" and settings.power_automate_idempotent
    ):
        raise HTTPException(
            409, "O destino precisa garantir idempotência para repetir com segurança."
        )
    transition(db, execution, "queued", "Nova tentativa solicitada.")
    audit(db, user, "execution.retry", execution.id)
    db.commit()
    return execution_read(execution)


@router.post("/executions/{execution_id}/cancel", response_model=ExecutionRead)
def cancel(execution_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    execution = execution_for_user(db, execution_id, user)
    if execution.status in {"running", "dispatching"} and execution.mode in {
        "simulation",
        "local_browser",
        "local_desktop",
    }:
        execution.cancel_requested = True
        from app.services.provisioning import add_event

        add_event(
            db,
            execution,
            "Cancelamento solicitado; o executor interromperá no próximo ponto de controle.",
        )
        audit(db, user, "execution.cancel_requested", execution.id)
        db.commit()
        return execution_read(execution)
    if execution.status != "queued":
        raise HTTPException(409, "Somente execuções ainda na fila podem ser canceladas.")
    transition(db, execution, "cancelled", "Execução cancelada antes do despacho.")
    audit(db, user, "execution.cancel", execution.id)
    db.commit()
    return execution_read(execution)


@router.post("/executions/{execution_id}/resume", response_model=ExecutionRead)
def resume(execution_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    execution = execution_for_user(db, execution_id, user)
    if (
        execution.status != "running"
        or not execution.awaiting_operator
        or execution.cancel_requested
    ):
        raise HTTPException(409, "Esta execução não está aguardando intervenção.")
    execution.awaiting_operator = False
    from app.services.provisioning import add_event

    add_event(db, execution, "Operador autorizou a continuação do fluxo.")
    audit(db, user, "execution.resumed", execution.id)
    db.commit()
    return execution_read(execution)
