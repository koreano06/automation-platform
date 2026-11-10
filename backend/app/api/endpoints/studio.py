from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.models import DiagnosticArtifact, StepTest, User
from app.models.domain import utcnow
from app.schemas import StepTestInput, StepTestRead
from app.security import admin_user
from app.services.step_tests import create_test

router = APIRouter(tags=["Studio tools"])


@router.post("/platforms/{platform_id}/step-tests", response_model=StepTestRead, status_code=202)
def enqueue_test(
    platform_id: str,
    payload: StepTestInput,
    user: User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    return create_test(db, platform_id, payload, user)


@router.get("/step-tests", response_model=list[StepTestRead])
def list_tests(
    limit: int = Query(20, ge=1, le=100),
    _: User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    return db.scalars(select(StepTest).order_by(StepTest.created_at.desc()).limit(limit)).all()


@router.get("/step-tests/{test_id}", response_model=StepTestRead)
def get_test(test_id: str, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    item = db.get(StepTest, test_id)
    if not item:
        raise HTTPException(404, "Teste não encontrado.")
    return item


@router.get("/artifacts/{artifact_id}")
def artifact(artifact_id: str, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    item = db.get(DiagnosticArtifact, artifact_id)
    if not item:
        raise HTTPException(404, "Evidência não encontrada.")
    if item.expires_at <= utcnow():
        raise HTTPException(410, "Evidência expirada pela política de retenção.")
    path = settings.artifacts_dir / f"{item.id}.png"
    if not path.is_file():
        raise HTTPException(404, "Arquivo indisponível.")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store"})


@router.get("/pilot-templates/sol")
def sol_template(_: User = Depends(admin_user)):
    from app.schemas import StepInput

    opening = StepInput(
        action="open_page", value="https://sol.pucgoias.edu.br/menu.asp"
    ).model_dump()
    base = StepInput(action="fill", data_ref="platform.matricula").model_dump()
    return {
        "name": "SOL · PUC Goiás",
        "mode": "local_browser",
        "description": "Piloto de login. Seletores precisam ser confirmados no navegador autorizado.",
        "requires_configuration": True,
        "inspection": "A página pública respondeu 403 / Just a moment; seletores não confirmados.",
        "fields": [
            {
                "key": "matricula",
                "label": "Matrícula",
                "field_type": "text",
                "required": True,
                "options": [],
            }
        ],
        "steps": [
            opening,
            base,
            {**base, "data_ref": "credential.SOL_PASSWORD"},
            {**base, "action": "click", "data_ref": ""},
            {**base, "action": "assert", "data_ref": "", "success_condition": ""},
        ],
    }
