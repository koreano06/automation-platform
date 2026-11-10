from fastapi import HTTPException
from sqlalchemy import select, update

from app.core.config import settings
from app.database.session import SessionLocal
from app.models import ReferenceImage, StepTest
from app.models.domain import utcnow
from app.runners.visual import RunnerError
from app.schemas import StepTestInput
from app.security import audit
from app.services.artifacts import save_diagram
from app.services.platforms import platform_or_404

SAFE_CODES = {
    "runner_disabled": "Habilite o executor local antes de testar um alvo real.",
    "destination_access_denied": "O destino bloqueou o acesso. Abra a plataforma no navegador e confira a autorização ou o desafio de acesso.",
    "host_not_allowed": "Autorize o domínio do piloto em LOCAL_ALLOWED_HOSTS.",
    "browser_action_failed": "O alvo não foi encontrado ou a ação expirou. Confira o seletor e a página inicial.",
    "button_not_found": "Imagem não encontrada. Atualize o recorte, a escala ou o contexto.",
    "ambiguous_button": "Mais de um alvo foi reconhecido; use uma referência mais específica.",
}


def create_test(db, platform_id, payload: StepTestInput, user):
    platform = platform_or_404(db, platform_id)
    if platform.mode == "power_automate":
        raise HTTPException(
            409,
            "Teste individual usa simulação ou executor local. Power Automate executa o fluxo completo.",
        )
    if (
        platform.mode == "local_browser"
        and payload.step.action == "fill"
        and not payload.step.locator
    ):
        raise HTTPException(422, "Preenchimento no navegador exige seletor.")
    if platform.mode == "local_desktop" and payload.step.action in {
        "open_page",
        "locate",
        "click",
        "assert",
        "click_button",
    }:
        raise HTTPException(
            422, "Essa ação exige modo navegador; desktop usa imagens e contexto de tela."
        )
    step = payload.step.model_dump()
    if step["reference_image_id"] and not db.get(ReferenceImage, step["reference_image_id"]):
        raise HTTPException(422, "Imagem de referência não encontrada.")
    if (
        platform.mode == "local_browser"
        and payload.step.action != "open_page"
        and not payload.start_url
    ):
        raise HTTPException(422, "Informe a URL inicial para abrir uma sessão isolada do teste.")
    if platform.mode == "local_desktop" and not payload.step.screen_context:
        raise HTTPException(422, "Informe o contexto de tela para o teste desktop.")
    if payload.step.action == "pause" and not payload.preview_only:
        raise HTTPException(409, "A pausa com intervenção deve ser testada em um fluxo completo.")
    field_keys = {field.key for field in platform.fields}
    if set(payload.fields) - field_keys:
        raise HTTPException(422, "Campos não definidos para a plataforma.")
    if not payload.preview_only and payload.step.action == "fill":
        ref = payload.step.data_ref
        if ref.startswith("employee.") and not payload.employee:
            raise HTTPException(422, "Informe os dados comuns usados pelo preenchimento.")
        if ref.startswith("platform.") and ref.partition(".")[2] not in payload.fields:
            raise HTTPException(422, "Informe o campo usado pelo preenchimento.")
    automation = [step]
    index = 0
    if platform.mode == "local_browser" and payload.step.action != "open_page":
        from app.schemas import StepInput

        automation.insert(0, StepInput(action="open_page", value=payload.start_url).model_dump())
        index = 1
    snapshot = {
        "automation": automation,
        "preview_index": index,
        "preview_only": payload.preview_only,
        "employee": payload.employee.model_dump() if payload.employee else {},
        "fields": payload.fields,
    }
    item = StepTest(
        platform_id=platform.id,
        requested_by=user.id,
        mode=platform.mode,
        preview_only=payload.preview_only,
        snapshot=snapshot,
    )
    db.add(item)
    db.flush()
    audit(
        db,
        user,
        "step_test.created",
        item.id,
        preview_only=payload.preview_only,
        action_type=payload.step.action,
    )
    db.commit()
    return item


def process_next(factory=SessionLocal, pulse=None):
    with factory() as db:
        item_id = db.scalar(
            select(StepTest.id)
            .where(StepTest.status == "queued")
            .order_by(StepTest.created_at)
            .limit(1)
        )
        if not item_id:
            return False
        changed = db.execute(
            update(StepTest)
            .where(StepTest.id == item_id, StepTest.status == "queued")
            .values(status="running", started_at=utcnow())
        )
        if changed.rowcount != 1:
            db.rollback()
            return False
        db.commit()
        item = db.get(StepTest, item_id)
        mode, snapshot = item.mode, item.snapshot
    target_step = snapshot["automation"][-1]
    if pulse:
        pulse.job_id, pulse.job_kind = item_id, "step_test"
        pulse.beat()
    error_code = None
    try:
        if mode == "simulation":
            ctx = target_step.get("screen_context")
            result = {
                "code": "simulated_target",
                "simulated": True,
                "target": {"x": ctx["x"], "y": ctx["y"], "width": 1, "height": 1} if ctx else None,
            }
        else:
            if not settings.local_runner_enabled:
                raise RunnerError("runner_disabled")
            if mode == "local_browser":
                from app.runners.browser import run
            else:
                from app.runners.desktop import run
            result = run(snapshot, lambda *_: None)
    except RunnerError as error:
        error_code = str(error)
        result = {
            "code": error_code,
            "message": SAFE_CODES.get(error_code, "Confira a configuração da etapa e do executor."),
            "target": error.target,
            "failed_step": error.step,
        }
    except Exception:  # noqa: BLE001 -- isolate driver failures without logging inputs
        error_code, result = (
            "test_internal_error",
            {
                "code": "test_internal_error",
                "message": "O teste foi interrompido. Confira o executor.",
            },
        )
    finally:
        if pulse:
            pulse.job_id, pulse.job_kind = None, None
    with factory() as db:
        item = db.get(StepTest, item_id)
        result["artifact_id"] = save_diagram(
            db,
            step_test_id=item.id,
            target=result.get("target"),
            step=1,
            action=target_step["action"],
        )
        result["schematic"] = True
        item.result, item.error_code = result, error_code
        item.status, item.finished_at = ("failed" if error_code else "succeeded"), utcnow()
        db.commit()
    return True
