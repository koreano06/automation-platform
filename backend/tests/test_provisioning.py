from datetime import timedelta

from sqlalchemy import func, select

from app.models import Account, Execution, ProvisioningRequest
from app.models.domain import utcnow
from app.worker import claim, recover_stale, run_once
from tests.helpers import automation, payload, platform, submit


def test_multiplatform_partial_failure_retry_and_no_duplicate_accounts(admin, factory):
    first, second = platform(admin, "Primeiro"), platform(admin, "Segundo", fail=True)
    automation(admin, first["id"])
    automation(admin, second["id"])
    item = submit(admin, [first, second])
    assert item["status"] == "queued"
    assert run_once(factory) and run_once(factory)
    result = admin.get(f"/provisioning-requests/{item['id']}").json()
    assert result["status"] == "partially_succeeded"
    failed = next(row for row in result["executions"] if row["status"] == "failed")
    events = admin.get(f"/executions/{failed['id']}/events").json()
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    assert admin.post(f"/executions/{failed['id']}/retry").status_code == 200
    assert run_once(factory)
    assert admin.get(f"/provisioning-requests/{item['id']}").json()["status"] == "succeeded"
    again = submit(admin, [first], "test-request-again")
    assert run_once(factory)
    result = admin.get(f"/provisioning-requests/{again['id']}").json()
    assert result["executions"][0]["result"]["code"] == "already_exists"
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(Account)) == 2


def test_idempotency_and_pending_duplicates(admin, factory):
    target = platform(admin)
    automation(admin, target["id"])
    first = submit(admin, [target])
    replay = submit(admin, [target])
    assert first["id"] == replay["id"]
    changed = payload([target], "different@example.invalid")
    assert (
        admin.post(
            "/provisioning-requests", json=changed, headers={"Idempotency-Key": "test-request-0001"}
        ).status_code
        == 409
    )
    assert (
        admin.post(
            "/provisioning-requests",
            json=payload([target]),
            headers={"Idempotency-Key": "another-request-key"},
        ).status_code
        == 409
    )
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(ProvisioningRequest)) == 1
        assert db.scalar(select(func.count()).select_from(Execution)) == 1


def test_dynamic_validation_and_unvalidated_automation(admin):
    target = platform(admin)
    assert (
        admin.post(
            "/provisioning-requests",
            json=payload([target]),
            headers={"Idempotency-Key": "validation-test"},
        ).status_code
        == 409
    )
    automation(admin, target["id"])
    invalid = payload([target])
    invalid["targets"][0]["fields"]["profile"] = "Invalid"
    assert (
        admin.post(
            "/provisioning-requests", json=invalid, headers={"Idempotency-Key": "validation-test"}
        ).status_code
        == 422
    )
    invalid["targets"][0]["fields"] = {"password": "sensitive"}
    response = admin.post(
        "/provisioning-requests", json=invalid, headers={"Idempotency-Key": "validation-test"}
    )
    assert response.status_code == 422
    assert "sensitive" not in response.text


def test_operators_only_see_own_requests(admin, operator):
    target = platform(admin)
    automation(admin, target["id"])
    item = submit(admin, [target])
    assert operator.get("/provisioning-requests").json() == []
    assert operator.get(f"/provisioning-requests/{item['id']}").status_code == 404
    assert operator.get(f"/executions/{item['executions'][0]['id']}/events").status_code == 404


def test_queue_claim_cancel_and_restart_persistence(admin, factory):
    target = platform(admin)
    automation(admin, target["id"])
    item = submit(admin, [target])
    execution_id = item["executions"][0]["id"]
    assert claim(factory) == execution_id
    assert claim(factory) is None
    # A fresh engine/session still sees the persisted dispatch state.
    from sqlalchemy.orm import sessionmaker

    from app.database.session import build_engine

    fresh_engine = build_engine(str(factory.kw["bind"].url))
    with sessionmaker(bind=fresh_engine)() as db:
        assert db.get(Execution, execution_id).status == "dispatching"
    fresh_engine.dispose()
    assert admin.post(f"/executions/{execution_id}/cancel").json()["cancel_requested"]
    other = submit(admin, [target], "cancel-request", "other@example.invalid")
    assert admin.post(f"/executions/{other['executions'][0]['id']}/cancel").status_code == 200
    assert admin.get(f"/provisioning-requests/{other['id']}").json()["status"] == "failed"


def test_stale_simulation_recovers_and_retry_preserves_correlation(admin, factory):
    target = platform(admin)
    automation(admin, target["id"])
    item = submit(admin, [target])
    execution_id = claim(factory)
    with factory() as db:
        row = db.get(Execution, execution_id)
        row.heartbeat_at = utcnow() - timedelta(hours=1)
        db.commit()
    assert recover_stale(factory) == 1
    assert run_once(factory)
    result = admin.get(f"/provisioning-requests/{item['id']}").json()["executions"][0]
    assert result["status"] == "succeeded"
    assert result["attempts"] == 2


def test_manual_generic_flow_does_not_require_employee_fields(admin, factory):
    target = platform(admin)
    definition = automation(
        admin,
        target["id"],
        [
            {"action": "click_button", "button_text": "Gerar relatório"},
            {"action": "assert", "locator": "#status", "success_condition": "Gerado"},
        ],
    )
    result = admin.post(
        f"/automations/{definition['id']}/runs",
        json={"fields": {"profile": "Colaborador"}},
        headers={"Idempotency-Key": "manual-generic-run"},
    )
    assert result.status_code == 202, result.text
    assert run_once(factory)
    assert (
        admin.get(f"/provisioning-requests/{result.json()['id']}").json()["status"] == "succeeded"
    )
