import threading
import time
from datetime import timedelta

from app.core.config import settings
from app.models import DiagnosticArtifact
from app.models.domain import utcnow
from app.services.artifacts import purge_expired
from app.services.heartbeat import WorkerPulse
from app.worker import run_once
from tests.helpers import automation, platform, submit


def test_system_status_distinguishes_offline_online_and_stale_worker(admin, operator, factory):
    before = admin.get("/system").json()
    assert before["worker"]["status"] == "offline"
    assert before["database"]["connected"]
    assert operator.get("/system").status_code == 403
    pulse = WorkerPulse(factory)
    pulse.beat()
    online = admin.get("/system").json()
    assert online["worker"]["status"] == "online"
    pulse.close()
    assert admin.get("/system").json()["worker"]["status"] == "offline"


def test_step_test_is_queued_admin_only_and_artifact_has_limited_access(admin, operator, factory):
    target = platform(admin)
    body = {
        "step": {
            "action": "click_point",
            "screen_context": {"x": 20, "y": 30, "width": 1280, "height": 720, "window": "Pilot"},
        },
        "preview_only": True,
    }
    assert operator.post(f"/platforms/{target['id']}/step-tests", json=body).status_code == 403
    response = admin.post(f"/platforms/{target['id']}/step-tests", json=body)
    assert response.status_code == 202, response.text
    item_id = response.json()["id"]
    assert response.json()["status"] == "queued"
    assert run_once(factory)
    item = admin.get(f"/step-tests/{item_id}").json()
    assert item["status"] == "succeeded" and item["result"]["simulated"]
    assert item["result"]["target"]["x"] == 20
    artifact_id = item["result"]["artifact_id"]
    assert admin.get(f"/artifacts/{artifact_id}").status_code == 200
    assert operator.get(f"/artifacts/{artifact_id}").status_code == 403
    with factory() as db:
        row = db.get(DiagnosticArtifact, artifact_id)
        row.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert admin.get(f"/artifacts/{artifact_id}").status_code == 410
    with factory() as db:
        assert purge_expired(db) == 1
    assert not (settings.artifacts_dir / f"{artifact_id}.png").exists()


def test_live_step_test_keeps_runner_opt_in_and_requires_initial_url(admin, factory):
    target = platform(admin, mode="local_browser")
    body = {"step": {"action": "click_button", "button_text": "Confirm"}, "preview_only": True}
    assert admin.post(f"/platforms/{target['id']}/step-tests", json=body).status_code == 422
    body["start_url"] = "https://pilot.invalid/"
    response = admin.post(f"/platforms/{target['id']}/step-tests", json=body)
    assert response.status_code == 202
    assert run_once(factory)
    result = admin.get(f"/step-tests/{response.json()['id']}").json()
    assert result["status"] == "failed" and result["error_code"] == "runner_disabled"


def test_pause_resume_and_cooperative_cancel(admin, operator, factory):
    target = platform(admin)
    automation(
        admin,
        target["id"],
        [
            {"action": "pause", "timeout_seconds": 5},
            {"action": "assert", "locator": "#result", "success_condition": "Ready"},
        ],
    )
    request = submit(admin, [target])
    execution_id = request["executions"][0]["id"]
    thread = threading.Thread(target=lambda: run_once(factory), daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            if admin.get(f"/executions/{execution_id}").json()["awaiting_operator"]:
                break
            time.sleep(0.05)
        assert admin.get(f"/executions/{execution_id}").json()["awaiting_operator"]
        assert operator.post(f"/executions/{execution_id}/resume").status_code == 404
        assert admin.post(f"/executions/{execution_id}/resume").status_code == 200
        thread.join(timeout=4)
        assert not thread.is_alive()
        assert admin.get(f"/executions/{execution_id}").json()["status"] == "succeeded"
        assert admin.post(f"/executions/{execution_id}/resume").status_code == 409
    finally:
        thread.join(timeout=6)


def test_sol_template_is_draft_without_invented_selectors_or_secrets(admin, operator):
    assert operator.get("/pilot-templates/sol").status_code == 403
    result = admin.get("/pilot-templates/sol").json()
    assert result["requires_configuration"]
    assert result["steps"][0]["value"] == "https://sol.pucgoias.edu.br/menu.asp"
    assert result["steps"][2]["data_ref"] == "credential.SOL_PASSWORD"
    assert not result["steps"][1]["locator"]


def test_flow_skip_cannot_remove_final_confirmation(admin):
    target = platform(admin)
    definition = automation(
        admin,
        target["id"],
        [
            {
                "action": "if_exists",
                "locator": "#existing",
                "on_match": "skip_next",
                "skip_steps": 1,
            },
            {"action": "assert", "locator": "#result", "success_condition": "Ready"},
        ],
        validate=False,
    )
    assert admin.post(f"/automations/{definition['id']}/validate").status_code == 422
