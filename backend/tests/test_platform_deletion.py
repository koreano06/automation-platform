from app.worker import run_once
from tests.helpers import automation, payload, platform, submit


def test_delete_requires_authentication(client):
    assert client.delete("/platforms/any-id").status_code == 401


def test_admin_removes_platform_and_audits_action(admin, operator):
    item = platform(admin)
    definition = automation(admin, item["id"])
    assert admin.delete(f"/platforms/{item['id']}").status_code == 204
    assert admin.get("/platforms").json() == []
    assert operator.get("/platforms").json() == []
    assert admin.get(f"/platforms/{item['id']}").status_code == 404
    assert admin.get(f"/platforms/{item['id']}/automations").status_code == 404
    assert admin.post(f"/automations/{definition['id']}/validate").status_code == 404
    assert (
        admin.post(
            "/provisioning-requests",
            json=payload([item]),
            headers={"Idempotency-Key": "deleted-platform"},
        ).status_code
        == 404
    )
    assert admin.delete(f"/platforms/{item['id']}").status_code == 404
    assert any(
        event["action"] == "platform.deleted" and event["resource_id"] == item["id"]
        for event in admin.get("/audit-events").json()
    )
    replacement = platform(admin)
    assert replacement["id"] != item["id"]


def test_delete_requires_admin_session_and_csrf(admin, operator, client):
    item = platform(admin)
    assert operator.delete(f"/platforms/{item['id']}").status_code == 403
    csrf = admin.headers.pop("X-CSRF-Token")
    assert admin.delete(f"/platforms/{item['id']}").status_code == 403
    admin.headers["X-CSRF-Token"] = csrf
    assert admin.get(f"/platforms/{item['id']}").status_code == 200
    assert admin.delete("/platforms/not-found").status_code == 404


def test_platform_with_pending_execution_cannot_be_removed(admin):
    item = platform(admin)
    automation(admin, item["id"])
    request = submit(admin, [item])
    assert admin.delete(f"/platforms/{item['id']}").status_code == 409
    assert admin.get(f"/platforms/{item['id']}").json()["active"]
    execution_id = request["executions"][0]["id"]
    assert admin.post(f"/executions/{execution_id}/cancel").status_code == 200
    assert admin.delete(f"/platforms/{item['id']}").status_code == 204


def test_history_survives_deletion_and_failed_execution_cannot_be_retried(admin, factory):
    item = platform(admin, fail=True)
    automation(admin, item["id"])
    request = submit(admin, [item])
    assert run_once(factory)
    execution_id = request["executions"][0]["id"]
    assert admin.get(f"/executions/{execution_id}").json()["can_retry"]
    assert admin.delete(f"/platforms/{item['id']}").status_code == 204
    history = admin.get(f"/provisioning-requests/{request['id']}").json()
    assert history["executions"][0]["platform_name"] == item["name"]
    assert history["executions"][0]["status"] == "failed"
    assert not history["executions"][0]["can_retry"]
    assert admin.get(f"/executions/{execution_id}/events").json()
    assert admin.post(f"/executions/{execution_id}/retry").status_code == 409
