from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlmodel import Session, select

from app.models import TaskMaterialAsset


ALLOWED_SUFFIXES: dict[str, tuple[str, ...]] = {
    "talent_plan": (".docx",),
    "course_standard": (".docx",),
    # The registrar exports the old OLE2 .xls, not .xlsx.
    "schedule": (".xlsx", ".xls"),
    "outline_template": (".docx",),
    "lesson_template": (".docx",),
}


class MaterialUploadError(ValueError):
    pass


def validate_upload_filename(kind: str, filename: str) -> str:
    allowed = ALLOWED_SUFFIXES.get(kind)
    if allowed is None:
        raise MaterialUploadError("不支持的课程资料类型")
    suffix = Path(filename).suffix.lower()
    if suffix not in allowed:
        raise MaterialUploadError(f"该资料仅支持 {'、'.join(allowed)} 文件")
    return suffix


def write_unique_asset(root: Path, task_id: int, kind: str, suffix: str, content: bytes) -> Path:
    path = root / str(task_id) / "assets" / kind / f"{uuid4().hex}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path.resolve()


def active_asset(session: Session, task_id: int, kind: str) -> TaskMaterialAsset | None:
    return session.exec(
        select(TaskMaterialAsset)
        .where(TaskMaterialAsset.task_id == task_id, TaskMaterialAsset.kind == kind)
        .order_by(TaskMaterialAsset.updated_at.desc())
    ).first()


def replace_active_asset(session: Session, asset: TaskMaterialAsset) -> None:
    existing = session.exec(
        select(TaskMaterialAsset).where(
            TaskMaterialAsset.task_id == asset.task_id,
            TaskMaterialAsset.kind == asset.kind,
        )
    ).all()
    for item in existing:
        session.delete(item)
    asset.updated_at = datetime.now(timezone.utc)
    session.add(asset)
