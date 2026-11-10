import io
from datetime import timedelta
from uuid import UUID

from PIL import Image, ImageDraw
from sqlalchemy import select

from app.core.config import settings
from app.models import DiagnosticArtifact
from app.models.domain import new_id, utcnow


def save_diagram(db, *, execution_id=None, step_test_id=None, target=None, step=None, action=None):
    """A schematic evidence image; no screen pixels, typed values or DOM text are persisted."""
    image = Image.new("RGB", (720, 260), "#f7f5fc")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((20, 20, 700, 240), radius=14, outline="#b49bdc", width=2)
    draw.text((40, 38), "AUTOMATION - TARGET DIAGNOSTIC (SCHEMATIC)", fill="#584579")
    draw.text((40, 65), f"Step: {step or '-'}    Action: {action or '-'}", fill="#716086")
    if target:
        x, y = round(target.get("x", 0)), round(target.get("y", 0))
        width, height = round(target.get("width", 0)), round(target.get("height", 0))
        draw.rounded_rectangle(
            (240, 110, 480, 190), radius=10, fill="#e9e1f8", outline="#7954cc", width=2
        )
        draw.line((350, 150, 370, 150), fill="#7954cc", width=2)
        draw.line((360, 140, 360, 160), fill="#7954cc", width=2)
        draw.text((40, 208), f"x={x} y={y} width={width} height={height}", fill="#584579")
    else:
        draw.text(
            (40, 130),
            "No target geometry available. Review locator / image / screen context.",
            fill="#716086",
        )
    raw = io.BytesIO()
    image.save(raw, "PNG")
    item = DiagnosticArtifact(
        id=new_id(),
        execution_id=execution_id,
        step_test_id=step_test_id,
        expires_at=utcnow() + timedelta(hours=settings.artifact_retention_hours),
    )
    settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
    path = settings.artifacts_dir / f"{item.id}.png"
    path.write_bytes(raw.getvalue())
    db.add(item)
    return item.id


def purge_expired(db):
    count = 0
    for artifact in db.scalars(
        select(DiagnosticArtifact).where(DiagnosticArtifact.expires_at <= utcnow())
    ):
        path = settings.artifacts_dir / f"{UUID(artifact.id)}.png"
        path.unlink(missing_ok=True)
        db.delete(artifact)
        count += 1
    db.commit()
    return count
