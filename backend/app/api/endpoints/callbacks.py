import hashlib
import hmac
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.models import Execution, ExecutionEvent
from app.schemas import CallbackInput, CallbackRead
from app.services.provisioning import add_event, transition

router = APIRouter(prefix="/integrations/power-automate", tags=["Power Automate"])

SAFE_MESSAGES = {
    "running": "O destino informou progresso.",
    "succeeded": "O destino confirmou o cadastro.",
    "failed": "O destino não concluiu o cadastro. Revise o fluxo e os campos antes de tentar novamente.",
}


@router.post("/callbacks", response_model=CallbackRead)
async def callback(request: Request, db: Session = Depends(get_db)):
    secret = settings.power_automate_callback_secret.get_secret_value()
    if not secret:
        raise HTTPException(503, "Integração não configurada.")
    length = request.headers.get("content-length", "0")
    if not length.isdigit() or int(length) > 16384:
        raise HTTPException(413, "Callback muito grande.")
    body = await request.body()
    if len(body) > 16384:
        raise HTTPException(413, "Callback muito grande.")
    timestamp = request.headers.get("X-Callback-Timestamp", "")
    signature = request.headers.get("X-Callback-Signature", "")
    try:
        if abs(time.time() - int(timestamp)) > 300:
            raise ValueError
    except ValueError:
        raise HTTPException(401, "Assinatura inválida.") from None
    expected = hmac.new(
        secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(401, "Assinatura inválida.")
    try:
        payload = CallbackInput.model_validate_json(body)
    except ValidationError:
        raise HTTPException(422, "Contrato de callback inválido.") from None
    execution = db.get(Execution, payload.execution_id)
    if not execution or execution.mode != "power_automate":
        raise HTTPException(404, "Execução não encontrada.")
    # Replays never mutate the execution twice.
    if db.scalar(
        select(ExecutionEvent.id).where(
            ExecutionEvent.execution_id == execution.id,
            ExecutionEvent.external_event_id == payload.event_id,
        )
    ):
        return {"accepted": True, "replayed": True}
    if execution.external_id and execution.external_id != payload.external_id:
        raise HTTPException(409, "Correlação externa divergente.")
    if execution.status not in {"dispatching", "running"}:
        raise HTTPException(409, "Esta execução já foi encerrada.")
    execution.external_id = payload.external_id
    if execution.status == "dispatching":
        transition(db, execution, "running", "Execução reconhecida pelo destino.")
    if payload.status == "running":
        from app.models.domain import utcnow

        execution.heartbeat_at = utcnow()
        add_event(
            db,
            execution,
            SAFE_MESSAGES["running"],
            step=payload.step,
            external_event_id=payload.event_id,
        )
    else:
        if payload.status == "failed":
            execution.error_code = payload.result_code or "execution_error"
        execution.result = {
            "code": payload.result_code
            or ("account_created" if payload.status == "succeeded" else "execution_error")
        }
        transition(
            db,
            execution,
            payload.status,
            SAFE_MESSAGES[payload.status],
            level="error" if payload.status == "failed" else "info",
            step=payload.step,
            external_event_id=payload.event_id,
        )
    db.commit()
    return {"accepted": True, "replayed": False}
