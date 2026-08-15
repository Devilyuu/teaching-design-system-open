import json
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models import (
    CourseReviewNotice,
    OutlineRow,
    ScheduleCandidateSession,
    ScheduleImportCandidate,
    ScheduleSessionRecord,
    TaskMaterialAsset,
)
from app.services.task_material_store import replace_active_asset


SCHEDULE_FIELDS = (
    "week_no",
    "date_text",
    "weekday",
    "periods",
    "course_name",
    "class_name",
    "location",
    "hours",
)


class ScheduleCandidateError(ValueError):
    pass


def _values(record) -> dict:
    return {field: getattr(record, field) for field in SCHEDULE_FIELDS}


def parse_meta(candidate: ScheduleImportCandidate) -> dict:
    if not candidate.parse_meta_json:
        return {}
    try:
        meta = json.loads(candidate.parse_meta_json)
    except ValueError:
        return {}
    return meta if isinstance(meta, dict) else {}


def build_parse_meta(analysis, course_filter: str = "", teaching_class: str = "") -> str:
    return json.dumps(
        {
            "header_row": analysis.header_row_index,
            "matches": [
                {
                    "field": match.field,
                    "column_index": match.column_index,
                    "header_text": match.header_text,
                    "confidence": match.confidence,
                }
                for match in analysis.matches
            ],
            "detected_headers": analysis.detected_headers,
            "unmapped_headers": analysis.unmapped_headers,
            "warnings": analysis.warnings,
            "course_names": analysis.course_names,
            "course_filter": course_filter,
            # The registrar's matrix names a teaching class per entry, and one
            # course often has two; an empty selection merges them.
            "teaching_classes": analysis.teaching_classes,
            "teaching_class": teaching_class,
        },
        ensure_ascii=False,
    )


def replace_candidate_sessions(session: Session, candidate: ScheduleImportCandidate, parsed) -> None:
    existing = session.exec(
        select(ScheduleCandidateSession).where(ScheduleCandidateSession.candidate_id == candidate.id)
    ).all()
    for item in existing:
        session.delete(item)
    for index, record in enumerate(parsed, start=1):
        session.add(ScheduleCandidateSession(candidate_id=candidate.id, session_no=index, **record.__dict__))


def schedule_candidate_read(session: Session, candidate: ScheduleImportCandidate) -> dict:
    active = session.exec(
        select(ScheduleSessionRecord)
        .where(ScheduleSessionRecord.task_id == candidate.task_id)
        .order_by(ScheduleSessionRecord.session_no)
    ).all()
    proposed = session.exec(
        select(ScheduleCandidateSession)
        .where(ScheduleCandidateSession.candidate_id == candidate.id)
        .order_by(ScheduleCandidateSession.session_no)
    ).all()
    active_by_no = {item.session_no: item for item in active}
    proposed_by_no = {item.session_no: item for item in proposed}
    changes = []
    for number in sorted(set(active_by_no) | set(proposed_by_no)):
        before = active_by_no.get(number)
        after = proposed_by_no.get(number)
        if before is None:
            changes.append({"session_no": number, "change_type": "added", "fields": list(SCHEDULE_FIELDS), "after": _values(after)})
        elif after is None:
            changes.append({"session_no": number, "change_type": "removed", "fields": list(SCHEDULE_FIELDS), "before": _values(before)})
        else:
            fields = [field for field in SCHEDULE_FIELDS if getattr(before, field) != getattr(after, field)]
            if fields:
                changes.append({"session_no": number, "change_type": "changed", "fields": fields, "before": _values(before), "after": _values(after)})
    has_outline = session.exec(select(OutlineRow).where(OutlineRow.task_id == candidate.task_id)).first() is not None
    count_mismatch = bool(active) and len(active) != len(proposed)
    blocked = has_outline and count_mismatch
    meta = parse_meta(candidate)
    return {
        "id": candidate.id,
        "task_id": candidate.task_id,
        "filename": candidate.original_filename,
        "status": candidate.status,
        "session_count": len(proposed),
        "total_hours": sum(item.hours for item in proposed),
        "added_count": sum(item["change_type"] == "added" for item in changes),
        "removed_count": sum(item["change_type"] == "removed" for item in changes),
        "changed_count": sum(item["change_type"] == "changed" for item in changes),
        "can_confirm": candidate.status == "pending" and not blocked,
        "blocking_message": "已有课程实施大纲时，新旧课次数量必须一致" if blocked else "",
        "changes": changes,
        "sessions": [{"session_no": item.session_no, **_values(item)} for item in proposed],
        "header_row": meta.get("header_row", 0),
        "matches": meta.get("matches", []),
        "detected_headers": meta.get("detected_headers", []),
        "unmapped_headers": meta.get("unmapped_headers", []),
        "warnings": meta.get("warnings", []),
        "course_names": meta.get("course_names", []),
        "course_filter": meta.get("course_filter", ""),
        "teaching_classes": meta.get("teaching_classes", []),
        "teaching_class": meta.get("teaching_class", ""),
    }


def apply_schedule_candidate(session: Session, candidate: ScheduleImportCandidate, uploaded_by_id: int) -> dict:
    if candidate.status != "pending":
        raise ScheduleCandidateError("该课表候选已经处理")
    projection = schedule_candidate_read(session, candidate)
    if not projection["can_confirm"]:
        raise ScheduleCandidateError(projection["blocking_message"] or "当前课表候选无法确认")
    proposed = session.exec(
        select(ScheduleCandidateSession)
        .where(ScheduleCandidateSession.candidate_id == candidate.id)
        .order_by(ScheduleCandidateSession.session_no)
    ).all()
    active = session.exec(select(ScheduleSessionRecord).where(ScheduleSessionRecord.task_id == candidate.task_id)).all()
    for item in active:
        session.delete(item)
    for item in proposed:
        session.add(ScheduleSessionRecord(task_id=candidate.task_id, **_values(item), session_no=item.session_no))
    outline_rows = session.exec(select(OutlineRow).where(OutlineRow.task_id == candidate.task_id)).all()
    proposed_by_no = {item.session_no: item for item in proposed}
    for row in outline_rows:
        schedule = proposed_by_no.get(row.session_no)
        if schedule is None:
            continue
        row.date_text = schedule.date_text
        row.week_no = schedule.week_no
        row.weekday = schedule.weekday
        row.periods = schedule.periods
        row.updated_at = datetime.now(timezone.utc)
        session.add(row)
    if outline_rows:
        session.add(CourseReviewNotice(task_id=candidate.task_id, artifact_type="outline", reason="课表已更新，请复核课程实施大纲日期与课次"))
    replace_active_asset(
        session,
        TaskMaterialAsset(
            task_id=candidate.task_id,
            kind="schedule",
            original_filename=candidate.original_filename,
            storage_path=candidate.storage_path,
            size_bytes=0,
            uploaded_by_id=uploaded_by_id,
            summary_json=f'{{"sessions_count": {len(proposed)}, "total_hours": {sum(item.hours for item in proposed)}}}',
        ),
    )
    candidate.status = "applied"
    session.add(candidate)
    session.commit()
    session.refresh(candidate)
    return schedule_candidate_read(session, candidate)
