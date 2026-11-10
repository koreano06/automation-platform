from app.core.config import settings
from app.models import Execution
from app.runners.visual import RunnerError
from app.services.artifacts import save_diagram
from app.services.control import execution_control
from app.services.provisioning import add_event, transition

SAFE_ERRORS = {
    "runner_disabled": "Executor local desativado. Configure a máquina antes de executar.",
    "runner_dependencies_missing": "Instale as dependências opcionais do executor nesta máquina.",
    "button_not_found": "O botão não foi reconhecido. Atualize o recorte ou confira a tela.",
    "ambiguous_button": "Mais de um botão corresponde à referência. Use um recorte mais específico.",
    "screen_context_mismatch": "A resolução ou a janela não corresponde à referência. Nenhum clique foi autorizado nesta etapa.",
    "allowed_hosts_not_configured": "Configure LOCAL_ALLOWED_HOSTS para autorizar os domínios do fluxo.",
    "host_not_allowed": "O domínio de destino não foi autorizado para o executor.",
    "credential_not_configured": "Configure a credencial referenciada no ambiente do worker.",
    "destination_access_denied": "O destino bloqueou o acesso. Confira a autorização da plataforma no navegador.",
    "operator_timeout": "A confirmação do operador não chegou dentro do tempo limite.",
    "browser_not_installed_or_unavailable": "Instale o Chromium do executor e confira a sessão de execução.",
}


def execute(execution_id, factory):
    with factory() as db:
        execution = db.get(Execution, execution_id)
        if execution.cancel_requested:
            transition(db, execution, "cancelled", "Execução cancelada antes de iniciar as ações.")
            db.commit()
            return
        if not settings.local_runner_enabled:
            execution.error_code = "runner_disabled"
            transition(db, execution, "failed", SAFE_ERRORS["runner_disabled"], level="error")
            db.commit()
            return
        snapshot, mode = execution.snapshot, execution.mode
        transition(
            db, execution, "running", "Executor local iniciou as ações autorizadas do fluxo."
        )
        db.commit()

    def on_step(index, action):
        with factory() as db:
            execution = db.get(Execution, execution_id)
            from app.models.domain import utcnow

            execution.heartbeat_at = utcnow()
            add_event(db, execution, f"Ação {action} concluída.", step=index)
            db.commit()

    try:
        if mode == "local_browser":
            from app.runners.browser import run
        else:
            from app.runners.desktop import run
        outcome = run(
            snapshot,
            on_step,
            control=execution_control(
                execution_id, factory, timeout=settings.execution_timeout_seconds
            ),
        )
    except RunnerError as error:
        code = str(error)
        with factory() as db:
            execution = db.get(Execution, execution_id)
            execution.error_code = code
            artifact_id = save_diagram(
                db,
                execution_id=execution.id,
                target=error.target,
                step=error.step,
                action=error.action,
            )
            execution.result = {
                "code": "outcome_requires_review",
                "failed_step": error.step,
                "action": error.action,
                "target": error.target,
                "artifact_id": artifact_id,
                "schematic": True,
            }
            transition(
                db,
                execution,
                "cancelled" if code == "execution_cancelled" else "failed",
                "Execução interrompida a pedido do operador."
                if code == "execution_cancelled"
                else SAFE_ERRORS.get(
                    code, "A etapa não pôde ser concluída. Confira o destino e revise a automação."
                ),
                level="info" if code == "execution_cancelled" else "error",
                step=error.step,
            )
            db.commit()
        return
    with factory() as db:
        execution = db.get(Execution, execution_id)
        execution.result = outcome or {"code": "flow_completed"}
        transition(
            db,
            execution,
            "succeeded",
            "As etapas e a confirmação final foram concluídas pelo executor local.",
        )
        db.commit()
