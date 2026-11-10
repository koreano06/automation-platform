class RunnerError(Exception):
    def __init__(self, code, *, step=None, action=None, target=None):
        super().__init__(code)
        self.step = step
        self.action = action
        self.target = target


def match_button(screen, template, confidence=0.9):
    """Return a unique template center; reject ambiguous/low-confidence matches."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        raise RunnerError("runner_dependencies_missing") from None
    screen_array = cv2.cvtColor(np.array(screen.convert("RGB")), cv2.COLOR_RGB2GRAY)
    template_array = cv2.cvtColor(np.array(template.convert("RGB")), cv2.COLOR_RGB2GRAY)
    height, width = template_array.shape
    if height > screen_array.shape[0] or width > screen_array.shape[1] or template_array.std() < 3:
        raise RunnerError("invalid_visual_reference")
    scores = cv2.matchTemplate(screen_array, template_array, cv2.TM_CCOEFF_NORMED)
    _, maximum, _, position = cv2.minMaxLoc(scores)
    if maximum < confidence:
        raise RunnerError("button_not_found")
    x, y = position
    scores[max(0, y - height + 1) : y + height, max(0, x - width + 1) : x + width] = -1
    if cv2.minMaxLoc(scores)[1] >= confidence:
        raise RunnerError("ambiguous_button")
    return x + width // 2, y + height // 2


def reference_image(step):
    from uuid import UUID

    from PIL import Image

    from app.core.config import settings

    try:
        image_id = str(UUID(step["reference_image_id"]))
        with Image.open(settings.assets_dir / f"{image_id}.png") as image:
            return image.convert("RGB")
    except (ValueError, OSError, KeyError, TypeError):
        raise RunnerError("reference_image_unavailable") from None


def resolve_data(snapshot, data_ref):
    import os
    import re

    if data_ref.startswith("credential."):
        key = data_ref.split(".", 1)[1]
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,60}", key):
            raise RunnerError("invalid_credential_reference")
        value = os.environ.get("AUTOMATION_SECRET_" + key.upper())
        if not value:
            raise RunnerError("credential_not_configured")
        return value
    group, _, key = data_ref.partition(".")
    values = (
        snapshot["employee"]
        if group == "employee"
        else snapshot["fields"]
        if group == "platform"
        else {}
    )
    if key not in values:
        raise RunnerError("missing_input")
    return str(values[key])
