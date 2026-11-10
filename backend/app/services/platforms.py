from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    AutomationDefinition,
    AutomationStep,
    Execution,
    Platform,
    PlatformField,
    ReferenceImage,
    StepTest,
    User,
)
from app.models.domain import utcnow
from app.schemas import AutomationInput, PlatformInput
from app.security import audit


def platform_or_404(db: Session, platform_id: str) -> Platform:
    item = db.get(Platform, platform_id)
    if not item or item.deleted_at is not None:
        raise HTTPException(404, "Plataforma não encontrada.")
    return item


def delete_platform(db: Session, platform_id: str, user: User):
    item = platform_or_404(db, platform_id)
    item.active = False
    item.deleted_at = utcnow()
    db.flush()
    pending = db.scalar(
        select(Execution.id)
        .where(
            Execution.platform_id == item.id,
            Execution.status.in_(["queued", "dispatching", "running"]),
        )
        .limit(1)
    )
    if pending:
        raise HTTPException(
            409, "Aguarde ou cancele as execuções pendentes antes de excluir a plataforma."
        )
    if db.scalar(
        select(StepTest.id)
        .where(StepTest.platform_id == item.id, StepTest.status.in_(["queued", "running"]))
        .limit(1)
    ):
        raise HTTPException(409, "Aguarde os testes de etapas antes de excluir a plataforma.")
    for definition in db.scalars(
        select(AutomationDefinition).where(AutomationDefinition.platform_id == item.id)
    ):
        definition.status = "archived"
    audit(db, user, "platform.deleted", item.id)
    db.commit()


def platform_read(item: Platform) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "active": item.active,
        "mode": item.mode,
        "config": item.config,
        "created_at": item.created_at,
        "fields": [
            {
                "id": field.id,
                "key": field.key,
                "label": field.label,
                "field_type": field.field_type,
                "required": field.required,
                "options": field.options,
                "position": field.position,
            }
            for field in item.fields
        ],
    }


def save_platform(db: Session, payload: PlatformInput, user: User, item: Platform | None = None):
    if not item:
        item = Platform(name=payload.name)
        db.add(item)
    item.name, item.description = payload.name, payload.description
    item.active, item.mode = payload.active, payload.mode
    item.config = payload.config.model_dump()
    item.fields.clear()
    db.flush()
    item.fields = [
        PlatformField(**field.model_dump(), position=i + 1)
        for i, field in enumerate(payload.fields)
    ]
    # Any configuration edit requires revalidating the automation.
    for definition in db.scalars(
        select(AutomationDefinition).where(
            AutomationDefinition.platform_id == item.id, AutomationDefinition.status == "validated"
        )
    ):
        definition.status = "draft"
    audit(db, user, "platform.saved", item.id)
    db.commit()
    return platform_read(item)


def automation_read(item: AutomationDefinition):
    return {
        "id": item.id,
        "platform_id": item.platform_id,
        "name": item.name,
        "version": item.version,
        "status": item.status,
        "created_at": item.created_at,
        "steps": [
            {
                "position": step.position,
                "action": step.action,
                "locator": step.locator,
                "value": step.value,
                "data_ref": step.data_ref,
                "timeout_seconds": step.timeout_seconds,
                "success_condition": step.success_condition,
                "button_text": step.button_text,
                "reference_image_id": step.reference_image_id,
                "confidence": step.confidence,
                "on_match": step.on_match,
                "skip_steps": step.skip_steps,
                "screen_context": step.screen_context or None,
            }
            for step in item.steps
        ],
    }


def create_automation(db: Session, platform_id: str, payload: AutomationInput, user: User):
    platform_or_404(db, platform_id)
    version = (
        db.scalar(
            select(func.max(AutomationDefinition.version)).where(
                AutomationDefinition.platform_id == platform_id
            )
        )
        or 0
    ) + 1
    item = AutomationDefinition(
        platform_id=platform_id, name=payload.name, version=version, created_by=user.id
    )
    item.steps = [
        AutomationStep(
            **step.model_dump(exclude={"screen_context"}),
            screen_context=step.screen_context.model_dump() if step.screen_context else {},
            position=i + 1,
        )
        for i, step in enumerate(payload.steps)
    ]
    db.add(item)
    db.flush()
    audit(db, user, "automation.version_created", item.id, version=version)
    db.commit()
    return automation_read(item)


def validate_automation(db: Session, automation_id: str, user: User):
    item = db.get(AutomationDefinition, automation_id)
    if not item:
        raise HTTPException(404, "Automação não encontrada.")
    platform = platform_or_404(db, item.platform_id)
    if not platform.active:
        raise HTTPException(409, "Ative a plataforma antes de validar.")
    available_refs = {
        "employee.name",
        "employee.email",
        "employee.department",
        "employee.employee_id",
    }
    available_refs |= {f"platform.{field.key}" for field in platform.fields}
    for step in item.steps:
        if (
            step.action == "if_exists"
            and step.on_match == "skip_next"
            and step.position + step.skip_steps >= len(item.steps)
        ):
            raise HTTPException(422, "O salto não pode remover a confirmação final do fluxo.")
        if (
            step.data_ref
            and step.data_ref not in available_refs
            and not step.data_ref.startswith("credential.")
        ):
            raise HTTPException(422, f"Referência inválida na etapa {step.position}.")
        if step.reference_image_id and not db.get(ReferenceImage, step.reference_image_id):
            raise HTTPException(422, "Imagem de referência não encontrada.")
        if platform.mode == "local_browser" and step.action == "fill" and not step.locator:
            raise HTTPException(422, "Preenchimento no navegador exige seletor.")
        if platform.mode == "local_desktop" and step.action in {
            "open_page",
            "locate",
            "click",
            "assert",
            "click_button",
        }:
            raise HTTPException(
                422, "Desktop usa imagem, click point, preenchimento e confirmação por imagem."
            )
        if (
            platform.mode == "local_desktop"
            and step.action == "if_exists"
            and not step.reference_image_id
        ):
            raise HTTPException(422, "Condições desktop exigem imagem de referência.")
        if (
            platform.mode == "local_desktop"
            or (
                platform.mode == "local_browser"
                and step.action in {"click_point", "click_image", "assert_image", "wait_image"}
            )
        ) and not step.screen_context:
            raise HTTPException(422, "Execução visual exige resolução e janela de referência.")
    if not item.steps or item.steps[-1].action not in {"assert", "assert_image"}:
        raise HTTPException(422, "A última etapa precisa confirmar o resultado.")
    if platform.mode == "power_automate" and not all(
        [
            settings.power_automate_url.get_secret_value(),
            settings.power_automate_callback_secret.get_secret_value(),
        ]
    ):
        raise HTTPException(409, "Configure a integração Power Automate antes de validar.")
    for other in db.scalars(
        select(AutomationDefinition).where(
            AutomationDefinition.platform_id == platform.id,
            AutomationDefinition.id != item.id,
            AutomationDefinition.status == "validated",
        )
    ):
        other.status = "archived"
    item.status = "validated"
    audit(db, user, "automation.validated", item.id, version=item.version)
    db.commit()
    warnings = (
        ["Click point depende da resolução e da janela; mudanças de interface exigem revisão."]
        if any(step.action == "click_point" for step in item.steps)
        else []
    )
    if platform.mode == "power_automate":
        warnings.append(
            "Validação estrutural. A validação operacional requer execução no destino real."
        )
    if platform.mode.startswith("local_"):
        warnings.append(
            "Executor real requer dependências opcionais e LOCAL_RUNNER_ENABLED=true na máquina de execução."
        )
    return {"automation": automation_read(item), "warnings": warnings}
