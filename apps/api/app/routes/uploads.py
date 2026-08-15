from pathlib import Path
import os

from fastapi import APIRouter, File, UploadFile

router = APIRouter(prefix="/uploads", tags=["uploads"])
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))


@router.post("")
async def upload_file(file: UploadFile = File(...)) -> dict[str, int | str]:
    UPLOAD_DIR.mkdir(exist_ok=True)
    target = UPLOAD_DIR / file.filename
    content = await file.read()
    target.write_bytes(content)
    return {"filename": file.filename, "size": len(content)}
