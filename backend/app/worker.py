"""Durable database queue. Run separately: python -m app.worker."""

import argparse
import logging
import time
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.database.session import SessionLocal
from app.integrations.power_automate.adapter import IntegrationError, dispatch
from app.models import Account, Execution, StepTest
from app.models.domain import utcnow
from app.services.provisioning import add_event, aggregate_request, transition

logger = logging.getLogger("automation.worker")


def recover_stale(factory=SessionLocal) -> int:
    count = 0
    with factory() as db:
        from app.services.heartbeat import live_worker_jobs

        live_jobs = live_worker_jobs(db)
        rows = db.scalars(
            select(Execution).where(
                Execution.status.in_(["dispatching", "running"]),
                Execution.heartbeat_at
                < utcnow() - timedelta(seconds=settings.execution_timeout_seconds),
            )
        ).all()
        for execution in rows:
            if execution.id in live_jobs:
                continue
            execution.error_code = (
                "timeout_outcome_unknown"
                if execution.mode != "simulation"
                else "worker_interrupted"
            )
            transition(
                db,
                execution,
                "failed",
                "Tempo limite excedido; o resultado precisa ser conferido.",
                level="error",
            )
            if execution.mode == "simulation" and execution.attempts < settings.max_attempts:
                transition(
                    db, execution, "queued", "Simulação retomada após interrupção do worker."
                )
            count += 1
        for test in db.scalars(
            select(StepTest).where(
                StepTest.status == "running",
                StepTest.started_at
                < utcnow() - timedelta(seconds=settings.execution_timeout_seconds),
            )
        ):
            if test.id not in live_jobs:
                test.status, test.error_code, test.finished_at = (
                    "failed",
                    "worker_interrupted",
                    utcnow(),
                )
        db.commit()
    return count


def claim(factory=SessionLocal) -> str | None:
    with factory() as db:
        candidate = db.scalar(
            select(Execution.id)
            .where(Execution.status == "queued")
            .order_by(Execution.created_at)
            .limit(1)
        )
        if not candidate:
            return None
        now = utcnow()
        changed = db.execute(
            update(Execution)
            .where(Execution.id == candidate, Execution.status == "queued")
            .values(
                status="dispatching",
                attempts=Execution.attempts + 1,
                started_at=now,
                heartbeat_at=now,
                lock_version=Execution.lock_version + 1,
            )
        )
        if changed.rowcount != 1:
            db.rollback()
            return None
        execution = db.get(Execution, candidate)
        add_event(db, execution, "Worker assumiu o despacho.")
        aggregate_request(db, execution.request_id)
        db.commit()
        return candidate


def simulate(execution_id: str, factory=SessionLocal):
    from app.runners.visual import RunnerError
    from app.services.control import execution_control

    control = execution_control(execution_id, factory, timeout=settings.execution_timeout_seconds)
    with factory() as db:
        execution = db.get(Execution, execution_id)
        transition(
            db, execution, "running", "Simulação iniciada; nenhuma conta externa será criada."
        )
        db.commit()
        steps = execution.snapshot["automation"]
    for index, step in enumerate(steps, 1):
        try:
            control(index, "pause" if step["action"] == "pause" else "before")
        except RunnerError as error:
            with factory() as db:
                execution = db.get(Execution, execution_id)
                execution.error_code = str(error)
                transition(
                    db,
                    execution,
                    "cancelled" if str(error) == "execution_cancelled" else "failed",
                    "Simulação interrompida pelo controle do operador.",
                    step=index,
                )
                db.commit()
            return
        with factory() as db:
            execution = db.get(Execution, execution_id)
            execution.heartbeat_at = utcnow()
            add_event(db, execution, f"Simulação: ação {step['action']} conferida.", step=index)
            db.commit()
    with factory() as db:
        execution = db.get(Execution, execution_id)
        if execution.snapshot["config"].get("simulate_failure") and execution.attempts == 1:
            execution.error_code = "simulated_transient_failure"
            transition(
                db,
                execution,
                "failed",
                "Falha de teste na primeira tentativa. É seguro repetir esta simulação.",
                level="error",
            )
        else:
            account = db.scalar(
                select(Account).where(
                    Account.platform_id == execution.platform_id,
                    Account.employee_key == execution.employee_key,
                )
            )
            if account:
                execution.result = {"code": "already_exists", "account_id": account.id}
                message = "Simulação concluída: cadastro já existente, sem duplicação."
            else:
                account = Account(
                    platform_id=execution.platform_id,
                    employee_key=execution.employee_key,
                    execution_id=execution.id,
                )
                db.add(account)
                db.flush()
                execution.result = {"code": "account_created", "account_id": account.id}
                message = "Simulação concluída: cadastro fictício criado."
            transition(db, execution, "succeeded", message)
        db.commit()


def send_external(execution_id: str, factory=SessionLocal):
    with factory() as db:
        execution = db.get(Execution, execution_id)
        try:
            external_id = dispatch(execution)
        except IntegrationError as error:
            # The adapter only raises fixed codes; never persist URL/token/response content.
            db.expire_all()
            execution = db.get(Execution, execution_id)
            if execution.status in {"dispatching", "running"}:
                execution.error_code = str(error)
                transition(
                    db,
                    execution,
                    "failed",
                    "Não foi possível confirmar o envio. Confira o destino antes de repetir.",
                    level="error",
                )
                db.commit()
            return
        db.expire_all()
        execution = db.get(Execution, execution_id)
        # A fast callback may already have completed the execution during dispatch.
        if execution.status in {"dispatching", "running"}:
            if execution.external_id and execution.external_id != external_id:
                execution.error_code = "external_correlation_mismatch"
                transition(
                    db,
                    execution,
                    "failed",
                    "O destino retornou uma correlação divergente.",
                    level="error",
                )
            else:
                execution.external_id = external_id
                if execution.status == "dispatching":
                    transition(
                        db, execution, "running", "Envio aceito; aguardando o retorno do destino."
                    )
            db.commit()


def run_once(factory=SessionLocal, pulse=None) -> bool:
    recover_stale(factory)
    from app.services.step_tests import process_next

    if process_next(factory, pulse=pulse):
        return True
    execution_id = claim(factory)
    if not execution_id:
        return False
    if pulse:
        pulse.job_id, pulse.job_kind = execution_id, "execution"
        pulse.beat()
    with factory() as db:
        mode = db.get(Execution, execution_id).mode
    try:
        if mode == "simulation":
            simulate(execution_id, factory)
        elif mode == "power_automate":
            send_external(execution_id, factory)
        else:
            from app.runners.local import execute

            execute(execution_id, factory)
    except Exception:  # noqa: BLE001 -- isolate jobs without leaking exception parameters
        # Do not format unexpected exceptions: database errors can contain PII in SQL parameters.
        logger.error("Falha interna no worker; a recuperação por timeout manterá o histórico.")
    finally:
        if pulse:
            pulse.job_id, pulse.job_kind = None, None
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    from app.database.migrations import check_schema

    check_schema()
    if args.once:
        run_once()
        return
    from app.services.heartbeat import WorkerPulse

    pulse = WorkerPulse()
    pulse.start()
    last_purge = 0
    try:
        while True:
            try:
                if time.monotonic() - last_purge > 60:
                    from app.services.artifacts import purge_expired

                    with SessionLocal() as db:
                        purge_expired(db)
                    last_purge = time.monotonic()
                processed = run_once(pulse=pulse)
            except SQLAlchemyError:
                logger.error(
                    "Persistência temporariamente indisponível; o worker tentará novamente."
                )
                processed = False
            if not processed:
                time.sleep(settings.worker_poll_seconds)
    except KeyboardInterrupt:
        pass
    finally:
        pulse.close()


if __name__ == "__main__":
    main()
