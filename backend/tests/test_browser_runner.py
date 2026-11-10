import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from uuid import uuid4

import pytest

from app.core.config import settings
from app.runners.browser import run

pytestmark = pytest.mark.skipif(
    os.environ.get("PLAYWRIGHT_TESTS") != "1",
    reason="Set PLAYWRIGHT_TESTS=1 after installing Chromium",
)


@pytest.fixture
def pilot_server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            html = b"""<!doctype html><html><body style="background:#edf1f7;padding:30px">
            <label>Name<input id="name"></label><button style="background:#6d43c5;color:white;border:2px solid #372b6e;padding:14px 24px;border-radius:8px;font:700 18px Arial" onclick="document.querySelector('#result').innerText='Completed'">Confirm</button>
            <p id="result" role="status">Ready</p></body></html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(html)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


def step(action, **kwargs):
    return {
        "action": action,
        "locator": "",
        "value": "",
        "data_ref": "",
        "timeout_seconds": 3,
        "success_condition": "",
        "screen_context": None,
        "confidence": 0.9,
        **kwargs,
    }


def test_actual_browser_recognizes_button_by_accessible_name(pilot_server, monkeypatch):
    monkeypatch.setattr(settings, "local_allowed_hosts", ["127.0.0.1"])
    completed = []
    run(
        {
            "employee": {"name": "Test Person"},
            "fields": {},
            "automation": [
                step("open_page", value=pilot_server),
                step("fill", locator="#name", data_ref="employee.name"),
                step("click_button", button_text="Confirm"),
                step("assert", locator="#result", success_condition="Completed"),
            ],
        },
        lambda index, action: completed.append(action),
    )
    assert completed == ["open_page", "fill", "click_button", "assert"]


def test_actual_browser_recognizes_button_image_and_clicks(pilot_server, monkeypatch, tmp_path):
    pytest.importorskip("cv2")
    from playwright.sync_api import sync_playwright

    monkeypatch.setattr(settings, "local_allowed_hosts", ["127.0.0.1"])
    monkeypatch.setattr(settings, "assets_dir", tmp_path)
    image_id = str(uuid4())
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.goto(pilot_server)
        page.get_by_role("button", name="Confirm").screenshot(
            path=str(tmp_path / f"{image_id}.png")
        )
        browser.close()
    run(
        {
            "employee": {},
            "fields": {},
            "automation": [
                step("open_page", value=pilot_server),
                step(
                    "click_image",
                    reference_image_id=image_id,
                    screen_context={
                        "width": 1280,
                        "height": 720,
                        "x": 0,
                        "y": 0,
                        "window": "Browser",
                    },
                ),
                step("assert", locator="#result", success_condition="Completed"),
            ],
        },
        lambda *_: None,
    )


def test_preview_and_conditional_branch_do_not_click(pilot_server, monkeypatch):
    monkeypatch.setattr(settings, "local_allowed_hosts", ["127.0.0.1"])
    preview = run(
        {
            "employee": {},
            "fields": {},
            "preview_only": True,
            "preview_index": 1,
            "automation": [
                step("open_page", value=pilot_server),
                step("click_button", button_text="Confirm"),
            ],
        },
        lambda *_: None,
    )
    assert preview["code"] == "target_detected"
    assert preview["target"]["width"] > 0
    events = []
    result = run(
        {
            "employee": {},
            "fields": {},
            "automation": [
                step("open_page", value=pilot_server),
                step("if_exists", locator="#result", on_match="finish_success"),
                step("click", locator="#nonexistent"),
                step("assert", locator="#result", success_condition="Completed"),
            ],
        },
        lambda index, action: events.append((index, action)),
    )
    assert result["code"] == "condition_matched"
    assert events == [(1, "open_page"), (2, "if_exists")]


def test_skip_branch_preserves_correct_event_positions(pilot_server, monkeypatch):
    monkeypatch.setattr(settings, "local_allowed_hosts", ["127.0.0.1"])
    events = []
    result = run(
        {
            "employee": {},
            "fields": {},
            "automation": [
                step("open_page", value=pilot_server),
                step("if_exists", locator="#result", on_match="skip_next", skip_steps=1),
                step("click_button", button_text="Confirm"),
                step("assert", locator="#result", success_condition="Ready"),
            ],
        },
        lambda index, action: events.append(index),
    )
    assert result["code"] == "flow_completed"
    assert events == [1, 2, 4]


def test_browser_failure_reports_step_without_input_values(pilot_server, monkeypatch):
    from app.runners.visual import RunnerError

    monkeypatch.setattr(settings, "local_allowed_hosts", ["127.0.0.1"])
    with pytest.raises(RunnerError) as caught:
        run(
            {
                "employee": {"name": "sensitive-input-not-for-logs"},
                "fields": {},
                "automation": [
                    step("open_page", value=pilot_server),
                    step("fill", locator="#missing", data_ref="employee.name", timeout_seconds=1),
                ],
            },
            lambda *_: None,
        )
    assert caught.value.step == 2
    assert caught.value.action == "fill"
    assert "sensitive-input" not in str(caught.value)
