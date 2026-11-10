import hashlib
import io
import warnings

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.models import ReferenceImage, User
from app.schemas import ImageRead
from app.security import admin_user, audit

router = APIRouter(prefix="/reference-images", tags=["Visual references"])


@router.post("", status_code=201, response_model=ImageRead)
async def upload(
    request: Request, actor: User = Depends(admin_user), db: Session = Depends(get_db)
):
    if request.headers.get("content-type", "").split(";")[0] != "image/png":
        raise HTTPException(415, "Envie o recorte do botão em PNG.")
    body = await request.body()
    if len(body) > 250_000:
        raise HTTPException(413, "O recorte PNG deve ter até 250 KB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(io.BytesIO(body))
            if (
                image.format != "PNG"
                or not 8 <= image.width <= 1200
                or not 8 <= image.height <= 1200
            ):
                raise ValueError
            image.load()
            cleaned = io.BytesIO()
            image.convert("RGB").save(cleaned, format="PNG")
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise HTTPException(
            422, "Imagem inválida: use um recorte PNG de 8 a 1200 pixels por dimensão."
        ) from None
    raw = cleaned.getvalue()
    digest = hashlib.sha256(raw).hexdigest()
    item = db.scalar(select(ReferenceImage).where(ReferenceImage.sha256 == digest))
    if not item:
        item = ReferenceImage(
            sha256=digest, width=image.width, height=image.height, created_by=actor.id
        )
        db.add(item)
        db.flush()
        settings.assets_dir.mkdir(parents=True, exist_ok=True)
        (settings.assets_dir / f"{item.id}.png").write_bytes(raw)
        audit(db, actor, "reference_image.created", item.id)
        db.commit()
    return {"id": item.id, "width": item.width, "height": item.height}


@router.get("/{image_id}")
def get_image(image_id: str, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    item = db.get(ReferenceImage, image_id)
    if not item:
        raise HTTPException(404, "Imagem não encontrada.")
    path = settings.assets_dir / f"{item.id}.png"
    if not path.is_file():
        raise HTTPException(404, "Arquivo de referência indisponível.")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store"})
