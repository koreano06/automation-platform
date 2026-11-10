import io

import pytest
from PIL import Image, ImageDraw

from app.core.config import settings
from app.runners.visual import RunnerError, match_button, resolve_data


def button_image():
    image = Image.new("RGB", (90, 36), "#6946cd")
    draw = ImageDraw.Draw(image)
    draw.rectangle((1, 1, 88, 34), outline="#f6e7ff", width=2)
    draw.text((13, 10), "CONFIRM", fill="white")
    return image


def test_recognition_detects_unique_button_and_rejects_missing_or_ambiguous():
    pytest.importorskip("cv2")
    template = button_image()
    screen = Image.new("RGB", (400, 200), "white")
    screen.paste(template, (80, 60))
    assert match_button(screen, template) == (125, 78)
    screen.paste(template, (230, 60))
    with pytest.raises(RunnerError, match="ambiguous_button"):
        match_button(screen, template)
    with pytest.raises(RunnerError, match="button_not_found"):
        match_button(Image.new("RGB", (400, 200), "white"), template)


def test_reference_upload_is_authenticated_and_sanitized(admin, operator, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "assets_dir", tmp_path / "assets")
    output = io.BytesIO()
    button_image().save(output, "PNG")
    assert (
        operator.post(
            "/reference-images", content=output.getvalue(), headers={"Content-Type": "image/png"}
        ).status_code
        == 403
    )
    result = admin.post(
        "/reference-images", content=output.getvalue(), headers={"Content-Type": "image/png"}
    )
    assert result.status_code == 201, result.text
    image_id = result.json()["id"]
    assert admin.get(f"/reference-images/{image_id}").status_code == 200
    assert operator.get(f"/reference-images/{image_id}").status_code == 403
    assert (
        admin.post(
            "/reference-images", content=b"not-an-image", headers={"Content-Type": "image/png"}
        ).status_code
        == 422
    )


def test_credential_reference_is_resolved_at_runtime_only(monkeypatch):
    monkeypatch.setenv("AUTOMATION_SECRET_PILOT_PASSWORD", "only-in-memory-value")
    assert (
        resolve_data({"employee": {}, "fields": {}}, "credential.PILOT_PASSWORD")
        == "only-in-memory-value"
    )
    with pytest.raises(RunnerError, match="credential_not_configured"):
        resolve_data({"employee": {}, "fields": {}}, "credential.UNKNOWN")
