import time

from app.runners.visual import RunnerError, match_button, reference_image, resolve_data


def run(snapshot, on_step, control=None):
    try:
        import pyautogui
        import pygetwindow
    except (ImportError, OSError):
        raise RunnerError("runner_dependencies_missing") from None
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.25
    index, action, target = 0, None, None
    steps = snapshot["automation"]

    def check(phase="before"):
        if control:
            control(index + 1, phase)

    def context_check(step):
        ctx = step.get("screen_context")
        if not ctx:
            raise RunnerError("screen_context_required")
        active = pygetwindow.getActiveWindowTitle() or ""
        if (ctx["width"], ctx["height"]) != tuple(pyautogui.size()) or ctx[
            "window"
        ].casefold() not in active.casefold():
            raise RunnerError("screen_context_mismatch")
        return ctx

    def image_target(step, wait=True):
        deadline = time.monotonic() + (step["timeout_seconds"] if wait else 0)
        while True:
            check()
            context_check(step)
            try:
                template = reference_image(step)
                x, y = match_button(pyautogui.screenshot(), template, step["confidence"])
                return {
                    "x": x - template.width // 2,
                    "y": y - template.height // 2,
                    "width": template.width,
                    "height": template.height,
                }
            except RunnerError as error:
                if str(error) != "button_not_found" or time.monotonic() >= deadline:
                    raise
                time.sleep(0.2)

    try:
        while index < len(steps):
            jump = 0
            step = steps[index]
            action, target = step["action"], None
            check()
            ctx = context_check(step)
            preview = snapshot.get("preview_only") and index == snapshot.get("preview_index")
            if action == "click_point":
                target = {"x": ctx["x"], "y": ctx["y"], "width": 1, "height": 1}
                if not preview:
                    pyautogui.click(ctx["x"], ctx["y"])
            elif action == "fill":
                if not preview:
                    from app.runners.windows_input import type_text

                    type_text(resolve_data(snapshot, step["data_ref"]))
            elif action in {"click_image", "assert_image", "wait_image", "if_exists"}:
                try:
                    target = image_target(step, wait=action != "if_exists")
                except RunnerError as error:
                    if action != "if_exists" or str(error) != "button_not_found":
                        raise
                if target and not preview:
                    if action == "click_image":
                        context_check(step)
                        pyautogui.click(
                            target["x"] + target["width"] // 2, target["y"] + target["height"] // 2
                        )
                    elif action == "if_exists":
                        if step.get("on_match", "finish_success") == "finish_success":
                            on_step(index + 1, action)
                            return {
                                "code": "condition_matched",
                                "target": target,
                                "step": index + 1,
                            }
                        if step.get("on_match") == "skip_next":
                            jump = step.get("skip_steps", 1)
            elif action == "pause":
                if not preview:
                    if not control:
                        raise RunnerError("operator_intervention_required")
                    check("pause")
            else:
                raise RunnerError("unsupported_desktop_action")
            on_step(index + 1, action)
            if index == snapshot.get("preview_index"):
                return {
                    "code": "target_detected" if preview else "step_completed",
                    "target": target,
                    "viewport": {"width": ctx["width"], "height": ctx["height"]},
                    "preview_only": bool(preview),
                }
            check()
            index += 1 + jump
        return {"code": "flow_completed"}
    except RunnerError as error:
        error.step, error.action, error.target = (
            error.step or index + 1,
            error.action or action,
            error.target or target,
        )
        raise
    except (pyautogui.FailSafeException, pyautogui.PyAutoGUIException, OSError, RuntimeError):
        raise RunnerError(
            "desktop_action_failed_or_stopped", step=index + 1, action=action
        ) from None
