import hashlib
import hmac
import json
import time

import httpx
from pydantic import SecretStr

from app.core.config import settings
from app.worker import claim, run_once
from tests.helpers import automation, platform, submit


def signed(client, payload, secret, timestamp=None):
    raw = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = str(timestamp or int(time.time()))
    signature = hmac.new(
        secret.encode(), timestamp.encode() + b"." + raw, hashlib.sha256
    ).hexdigest()
    return client.post(
        "/integrations/power-automate/callbacks",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-Callback-Timestamp": timestamp,
            "X-Callback-Signature": signature,
        },
    )


def external_setup(admin, monkeypatch):
    secret = "test-callback-key-not-for-production"
    monkeypatch.setattr(
        settings, "power_automate_url", SecretStr("https://flow.example.invalid/trigger")
    )
    monkeypatch.setattr(settings, "power_automate_callback_secret", SecretStr(secret))
    target = platform(admin, mode="power_automate")
    automation(admin, target["id"])
    return target, secret


def test_callback_authentication_progress_replay_success_and_terminal_guard(
    admin, factory, monkeypatch
):
    target, secret = external_setup(admin, monkeypatch)
    item = submit(admin, [target])
    execution_id = claim(factory)
    event = {
        "execution_id": execution_id,
        "event_id": "event-1",
        "external_id": "flow-123",
        "status": "running",
        "step": 1,
    }
    assert admin.post("/integrations/power-automate/callbacks", json=event).status_code == 401
    assert signed(admin, event, secret, timestamp=1).status_code == 401
    assert signed(admin, event, secret).status_code == 200
    assert signed(admin, event, secret).json()["replayed"]
    event.update(event_id="event-2", status="succeeded", result_code="account_created")
    assert signed(admin, event, secret).status_code == 200
    assert admin.get(f"/provisioning-requests/{item['id']}").json()["status"] == "succeeded"
    assert signed(admin, event, secret).json()["replayed"]
    event.update(event_id="event-3", status="failed")
    assert signed(admin, event, secret).status_code == 409


def test_callback_failure_and_retry_require_destination_idempotency(admin, factory, monkeypatch):
    target, secret = external_setup(admin, monkeypatch)
    item = submit(admin, [target])
    execution_id = claim(factory)
    event = {
        "execution_id": execution_id,
        "event_id": "failure-1",
        "external_id": "flow-123",
        "status": "failed",
        "result_code": "destination_rejected",
    }
    assert signed(admin, event, secret).status_code == 200
    assert admin.get(f"/provisioning-requests/{item['id']}").json()["status"] == "failed"
    assert admin.post(f"/executions/{execution_id}/retry").status_code == 409
    monkeypatch.setattr(settings, "power_automate_idempotent", True)
    assert admin.post(f"/executions/{execution_id}/retry").status_code == 200


def test_http_adapter_keeps_correlation_and_does_not_log_secrets(admin, factory, monkeypatch):
    target, _ = external_setup(admin, monkeypatch)
    monkeypatch.setattr(
        settings, "power_automate_token", SecretStr("test-token-that-must-not-be-logged")
    )
    item = submit(admin, [target])
    sent = []

    class FakeClient:
        def __init__(self, **_):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def post(self, url, **kwargs):
            sent.append(kwargs)
            return httpx.Response(202, json={"external_id": "real-flow-abc"})

    from app.integrations.power_automate import adapter

    monkeypatch.setattr(adapter.httpx, "Client", FakeClient)
    assert run_once(factory)
    execution_id = item["executions"][0]["id"]
    assert sent[0]["json"]["execution_id"] == execution_id
    assert sent[0]["headers"]["Idempotency-Key"] == execution_id
    events = admin.get(f"/executions/{execution_id}/events").text
    assert "test-token" not in events
    assert "flow.example.invalid" not in events
    assert admin.get(f"/executions/{execution_id}").json()["status"] == "running"


def test_live_runner_stays_disabled_without_opt_in(admin, factory):
    target = platform(admin, mode="local_browser")
    automation(admin, target["id"])
    item = submit(admin, [target])
    assert run_once(factory)
    row = admin.get(f"/executions/{item['executions'][0]['id']}").json()
    assert row["status"] == "failed" and row["error_code"] == "runner_disabled"
    assert not row["can_retry"]
