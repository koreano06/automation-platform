import time

from app.models import Execution
from app.runners.visual import RunnerError
from app.services.provisioning import add_event


def execution_control(execution_id, factory, *, timeout=300):
    def check(index, phase):
        if phase == "pause":
            with factory() as db:
                row = db.get(Execution, execution_id)
                if row.cancel_requested:
                    raise RunnerError("execution_cancelled", step=index)
                row.awaiting_operator = True
                pause_timeout = min(
                    timeout, row.snapshot["automation"][index - 1].get("timeout_seconds", timeout)
                )
                add_event(db, row, "Aguardando confirmação do operador para continuar.", step=index)
                db.commit()
            deadline = time.monotonic() + pause_timeout
            while time.monotonic() < deadline:
                with factory() as db:
                    row = db.get(Execution, execution_id)
                    if row.cancel_requested or row.status == "cancelled":
                        raise RunnerError("execution_cancelled", step=index)
                    if not row.awaiting_operator:
                        return
                time.sleep(0.25)
            raise RunnerError("operator_timeout", step=index)
        with factory() as db:
            row = db.get(Execution, execution_id)
            if row.cancel_requested or row.status == "cancelled":
                raise RunnerError("execution_cancelled", step=index)

    return check
