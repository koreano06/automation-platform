from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models import AutomationDefinition, Platform, User
from app.schemas import (
    AutomationInput,
    AutomationRead,
    EmployeeInput,
    PlatformInput,
    PlatformRead,
    RequestInput,
    RequestRead,
    RunInput,
    TargetInput,
    ValidationRead,
)
from app.security import admin_user, current_user
from app.services.platforms import (
    automation_read,
    create_automation,
    delete_platform,
    platform_or_404,
    platform_read,
    save_platform,
    validate_automation,
)

router = APIRouter(tags=["Platforms & Automations"])


@router.get("/platforms", response_model=list[PlatformRead])
def list_platforms(_: User = Depends(current_user), db: Session = Depends(get_db)):
    return [
        platform_read(item)
        for item in db.scalars(
            select(Platform).where(Platform.deleted_at.is_(None)).order_by(Platform.name)
        )
    ]


@router.post("/platforms", status_code=201, response_model=PlatformRead)
def add_platform(
    payload: PlatformInput, user: User = Depends(admin_user), db: Session = Depends(get_db)
):
    return save_platform(db, payload, user)


@router.get("/platforms/{platform_id}", response_model=PlatformRead)
def get_platform(platform_id: str, _: User = Depends(current_user), db: Session = Depends(get_db)):
    return platform_read(platform_or_404(db, platform_id))


@router.put("/platforms/{platform_id}", response_model=PlatformRead)
def edit_platform(
    platform_id: str,
    payload: PlatformInput,
    user: User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    return save_platform(db, payload, user, platform_or_404(db, platform_id))


@router.delete("/platforms/{platform_id}", status_code=204)
def remove_platform(
    platform_id: str, user: User = Depends(admin_user), db: Session = Depends(get_db)
):
    delete_platform(db, platform_id, user)
    return Response(status_code=204)


@router.get("/platforms/{platform_id}/automations", response_model=list[AutomationRead])
def list_automations(
    platform_id: str, _: User = Depends(admin_user), db: Session = Depends(get_db)
):
    platform_or_404(db, platform_id)
    return [
        automation_read(item)
        for item in db.scalars(
            select(AutomationDefinition)
            .where(AutomationDefinition.platform_id == platform_id)
            .order_by(AutomationDefinition.version.desc())
        )
    ]


@router.post("/platforms/{platform_id}/automations", status_code=201, response_model=AutomationRead)
def add_automation(
    platform_id: str,
    payload: AutomationInput,
    user: User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    return create_automation(db, platform_id, payload, user)


@router.post("/automations/{automation_id}/validate", response_model=ValidationRead)
def validate(automation_id: str, user: User = Depends(admin_user), db: Session = Depends(get_db)):
    return validate_automation(db, automation_id, user)


@router.post("/automations/{automation_id}/runs", status_code=202, response_model=RequestRead)
def run_flow(
    automation_id: str,
    payload: RunInput,
    idempotency_key: str = Header(default=""),
    user: User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    import hashlib

    from app.services.provisioning import create_request, request_read

    automation = db.get(AutomationDefinition, automation_id)
    if not automation:
        raise HTTPException(404, "Automação não encontrada.")
    if automation.status != "validated":
        raise HTTPException(409, "Valide esta versão antes de executar.")
    if (
        any(step.data_ref.startswith("employee.") for step in automation.steps)
        and not payload.employee
    ):
        raise HTTPException(422, "Este fluxo precisa dos dados comuns do colaborador.")
    digest = hashlib.sha256(idempotency_key.encode()).hexdigest()[:20]
    employee = payload.employee or EmployeeInput(
        name="Execução manual",
        email=f"run-{digest}@automation.invalid",
        department="Automação",
        employee_id="manual",
    )
    item, _ = create_request(
        db,
        RequestInput(
            employee=employee,
            targets=[TargetInput(platform_id=automation.platform_id, fields=payload.fields)],
        ),
        idempotency_key,
        user,
    )
    return request_read(item)
