import io
import time
from urllib.parse import urlsplit

from PIL import Image

from app.core.config import settings
from app.runners.visual import RunnerError, match_button, reference_image, resolve_data


def run(snapshot, on_step, control=None):
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import expect, sync_playwright
    except ImportError:
        raise RunnerError("runner_dependencies_missing") from None
    if not settings.local_allowed_hosts:
        raise RunnerError("allowed_hosts_not_configured")
    steps = snapshot["automation"]
    contexts = [step["screen_context"] for step in steps if step.get("screen_context")]
    viewport = (
        {"width": contexts[0]["width"], "height": contexts[0]["height"]}
        if contexts
        else {"width": 1280, "height": 720}
    )
    index, action, target = 0, None, None

    def check(phase="before"):
        if control:
            control(index + 1, phase)

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=settings.browser_headless)
        except PlaywrightError:
            raise RunnerError("browser_not_installed_or_unavailable") from None
        context = browser.new_context(viewport=viewport, service_workers="block")
        page = context.new_page()

        def restrict(route):
            url = urlsplit(route.request.url)
            if (
                url.scheme in {"data", "blob", "about"}
                or url.hostname in settings.local_allowed_hosts
            ):
                route.continue_()
            else:
                route.abort()

        context.route("**/*", restrict)

        def image_target(step, wait=True):
            deadline = time.monotonic() + (step["timeout_seconds"] if wait else 0)
            while True:
                check()
                try:
                    template = reference_image(step)
                    with Image.open(io.BytesIO(page.screenshot())) as screen:
                        x, y = match_button(screen, template, step["confidence"])
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
                page.set_default_timeout(step["timeout_seconds"] * 1000)
                preview = snapshot.get("preview_only") and index == snapshot.get("preview_index")
                if action == "open_page":
                    if urlsplit(step["value"]).hostname not in settings.local_allowed_hosts:
                        raise RunnerError("host_not_allowed")
                    response = page.goto(step["value"], wait_until="domcontentloaded")
                    if response and response.status >= 400:
                        raise RunnerError(
                            "destination_access_denied"
                            if response.status in {401, 403}
                            else "destination_http_error"
                        )
                    target = {"x": 0, "y": 0, **viewport}
                elif action in {"locate", "fill", "click", "assert", "click_button"}:
                    locator = (
                        page.get_by_role("button", name=step["button_text"], exact=True)
                        if action == "click_button"
                        else page.locator(step["locator"])
                    )
                    locator.wait_for(state="visible")
                    target = locator.bounding_box()
                    if not preview:
                        if action == "fill":
                            locator.fill(resolve_data(snapshot, step["data_ref"]))
                        elif action in {"click", "click_button"}:
                            locator.click()
                        elif action == "assert":
                            expect(locator).to_contain_text(
                                step["success_condition"], timeout=step["timeout_seconds"] * 1000
                            )
                elif action == "click_point":
                    ctx = step["screen_context"]
                    if page.viewport_size != {"width": ctx["width"], "height": ctx["height"]}:
                        raise RunnerError("screen_context_mismatch")
                    target = {"x": ctx["x"], "y": ctx["y"], "width": 1, "height": 1}
                    if not preview:
                        page.mouse.click(ctx["x"], ctx["y"])
                elif action in {"click_image", "assert_image", "wait_image"}:
                    target = image_target(step)
                    if action == "click_image" and not preview:
                        page.mouse.click(
                            target["x"] + target["width"] / 2, target["y"] + target["height"] / 2
                        )
                elif action == "if_exists":
                    if step.get("reference_image_id"):
                        try:
                            target = image_target(step, wait=False)
                        except RunnerError as error:
                            if str(error) != "button_not_found":
                                raise
                        matched = target is not None
                    else:
                        locator = page.locator(step["locator"])
                        matched = locator.count() > 0 and locator.first.is_visible()
                        if matched:
                            target = locator.first.bounding_box()
                    if matched and not preview:
                        if step.get("on_match", "finish_success") == "finish_success":
                            on_step(index + 1, action)
                            return {
                                "code": "condition_matched",
                                "step": index + 1,
                                "target": target,
                                "viewport": viewport,
                            }
                        if step.get("on_match") == "skip_next":
                            jump = step.get("skip_steps", 1)
                elif action == "pause":
                    if not preview:
                        if not control:
                            raise RunnerError("operator_intervention_required")
                        check("pause")
                else:
                    raise RunnerError("unsupported_browser_action")
                on_step(index + 1, action)
                if index == snapshot.get("preview_index"):
                    return {
                        "code": "target_detected" if preview else "step_completed",
                        "target": target,
                        "viewport": viewport,
                        "preview_only": bool(preview),
                    }
                check()
                index += 1 + jump
            return {"code": "flow_completed"}
        except RunnerError as error:
            error.step = error.step or index + 1
            error.action = error.action or action
            error.target = error.target or target
            raise
        except (PlaywrightError, OSError):
            raise RunnerError(
                "browser_action_failed", step=index + 1, action=action, target=target
            ) from None
        finally:
            context.close()
            browser.close()
