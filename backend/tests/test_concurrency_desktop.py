import sys
from types import SimpleNamespace

import pytest
from sqlalchemy.orm.exc import StaleDataError

from app.models import Execution
from app.services.provisioning import transition
from app.worker import claim
from tests.helpers import automation, platform, submit


def test_terminal_state_cannot_be_overwritten_by_stale_callback(admin, factory):
    target = platform(admin)
    automation(admin, target["id"])
    submit(admin, [target])
    execution_id = claim(factory)
    with factory() as db:
        transition(db, db.get(Execution, execution_id), "running", "Started")
        db.commit()
    with factory() as first, factory() as second:
        current = first.get(Execution, execution_id)
        stale = second.get(Execution, execution_id)
        transition(first, current, "succeeded", "Finished")
        first.commit()
        with pytest.raises(StaleDataError):
            transition(second, stale, "failed", "Late failure")
            second.commit()
        second.rollback()
    with factory() as db:
        assert db.get(Execution, execution_id).status == "succeeded"


def test_desktop_context_mismatch_prevents_mouse_action(monkeypatch):
    from app.runners.desktop import run
    from app.runners.visual import RunnerError

    clicks = []
    fake = SimpleNamespace(
        size=lambda: (1920, 1080),
        click=lambda *args: clicks.append(args),
        FailSafeException=type("FailSafeException", (Exception,), {}),
        PyAutoGUIException=type("PyAutoGUIException", (Exception,), {}),
    )
    monkeypatch.setitem(sys.modules, "pyautogui", fake)
    monkeypatch.setitem(
        sys.modules, "pygetwindow", SimpleNamespace(getActiveWindowTitle=lambda: "Unrelated window")
    )
    with pytest.raises(RunnerError, match="screen_context_mismatch"):
        run(
            {
                "automation": [
                    {
                        "action": "click_point",
                        "screen_context": {
                            "x": 10,
                            "y": 20,
                            "width": 1920,
                            "height": 1080,
                            "window": "Pilot app",
                        },
                    }
                ]
            },
            lambda *_: None,
        )
    assert not clicks
