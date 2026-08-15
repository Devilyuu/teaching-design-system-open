from pathlib import Path

from sqlmodel import Session, select

from app.models import ExportRecord, User


ARTIFACT_LABELS = {
    "outline": "课程实施大纲",
    "lesson": "整门课教案",
    "session_material": "课次材料",
}


def record_export(
    session: Session,
    *,
    root: Path,
    task_id: int,
    artifact_type: str,
    filename: str,
    content: bytes,
    exported_by_id: int,
    template_filename: str = "",
    source_summary: str = "",
    session_no: int | None = None,
) -> ExportRecord:
    """Retain the exported document so the teacher can trace and re-download it."""
    stored = root / str(task_id) / "exports" / artifact_type
    stored.mkdir(parents=True, exist_ok=True)
    target = stored / f"{_next_version(session, task_id, artifact_type):04d}-{filename}"
    target.write_bytes(content)
    record = ExportRecord(
        task_id=task_id,
        artifact_type=artifact_type,
        filename=filename,
        storage_path=str(target.resolve()),
        size_bytes=len(content),
        template_filename=template_filename,
        source_summary=source_summary,
        session_no=session_no,
        exported_by_id=exported_by_id,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def _next_version(session: Session, task_id: int, artifact_type: str) -> int:
    existing = session.exec(
        select(ExportRecord).where(
            ExportRecord.task_id == task_id,
            ExportRecord.artifact_type == artifact_type,
        )
    ).all()
    return len(existing) + 1


def export_history(session: Session, task_id: int) -> list[dict]:
    records = session.exec(
        select(ExportRecord)
        .where(ExportRecord.task_id == task_id)
        .order_by(ExportRecord.created_at.desc(), ExportRecord.id.desc())
    ).all()
    names = _exporter_names(session, {record.exported_by_id for record in records})
    return [
        {
            "id": record.id,
            "artifact_type": record.artifact_type,
            "artifact_label": ARTIFACT_LABELS.get(record.artifact_type, record.artifact_type),
            "filename": record.filename,
            "size_bytes": record.size_bytes,
            "template_filename": record.template_filename,
            "source_summary": record.source_summary,
            "session_no": record.session_no,
            "exported_by": names.get(record.exported_by_id, ""),
            "created_at": record.created_at,
            "available": Path(record.storage_path).exists(),
        }
        for record in records
    ]


def _exporter_names(session: Session, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    users = session.exec(select(User).where(User.id.in_(ids))).all()
    return {user.id: user.name for user in users if user.id is not None}
