import base64
import re
from urllib.parse import urlsplit
from uuid import UUID

import httpx

from app.core.config import settings


class IntegrationError(Exception):
    pass


def dispatch(execution) -> str:
    url = settings.power_automate_url.get_secret_value()
    if not url or urlsplit(url).scheme != "https":
        raise IntegrationError("integration_not_configured")
    headers = {"Idempotency-Key": execution.id}
    token = settings.power_automate_token.get_secret_value()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = {
        "execution_id": execution.id,
        "correlation_id": execution.id,
        "idempotency_key": execution.id,
        "callback_url": settings.public_api_base_url.rstrip("/")
        + "/integrations/power-automate/callbacks",
        "platform_id": execution.platform_id,
        "automation_id": execution.automation_id,
        "version": execution.snapshot["version"],
        "employee": execution.snapshot["employee"],
        "fields": execution.snapshot["fields"],
        "steps": execution.snapshot["automation"],
    }
    references = []
    total = 0
    for image_id in {
        step.get("reference_image_id") for step in execution.snapshot["automation"]
    } - {None}:
        try:
            canonical_id = str(UUID(image_id))
            raw = (settings.assets_dir / f"{canonical_id}.png").read_bytes()
        except (ValueError, OSError, TypeError):
            raise IntegrationError("reference_image_unavailable") from None
        total += len(raw)
        if total > 2_000_000:
            raise IntegrationError("visual_payload_too_large")
        references.append({"id": canonical_id, "png_base64": base64.b64encode(raw).decode("ascii")})
    payload["reference_images"] = references
    try:
        with httpx.Client(timeout=10, follow_redirects=False) as client:
            response = client.post(url, json=payload, headers=headers)
        if response.status_code not in {200, 202}:
            raise IntegrationError("dispatch_rejected")
        acknowledgement = response.json()
        if not isinstance(acknowledgement, dict):
            raise IntegrationError("invalid_acknowledgement")
        external_id = acknowledgement.get("external_id", "")
        if not isinstance(external_id, str) or not re.fullmatch(
            r"[a-zA-Z0-9._:-]{1,120}", external_id
        ):
            raise IntegrationError("invalid_acknowledgement")
        return external_id
    except (httpx.HTTPError, ValueError, TypeError):
        raise IntegrationError("dispatch_outcome_unknown") from None
