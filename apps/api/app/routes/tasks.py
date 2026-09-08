from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple
import json
import os
from tempfile import NamedTemporaryFile
from urllib.parse import quote
import threading
from contextlib import contextmanager

from docx import Document
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlmodel import Session, select

from app.auth import get_current_user
from app.db import get_session
from app.models import (
    AbilityIndicator,
    AiModelConfig,
    CourseProject,
    CourseGoal,
    CourseReviewNotice,
    ExportRecord,
    LessonPlan,
    Major,
    OutlineRow,
    OutlineRevisionCandidate,
    OutlineSectionSet,
    PostClassReflection,
    ScheduleSessionRecord,
    ScheduleCandidateSession,
    ScheduleImportCandidate,
    SessionMaterial,
    SourceConfirmation,
    TaskMaterialAsset,
    TeachingTask,
    User,
)
from app.schemas import (
    CourseReadinessRead,
    LessonPlanRead,
    LessonPlanUpdate,
    OutlineRowRead,
    OutlineRowUpdate,
    OutlineRevisionCandidateRead,
    OutlineRevisionRequest,
    ParseSummary,
    PostClassReflectionRead,
    PostClassReflectionUpsert,
    SessionMaterialGenerate,
    SessionMaterialRead,
    SessionMaterialUpdate,
    SessionWorkspaceRead,
    ExportRecordRead,
    WorkbenchPushRead,
    SourceReviewRead,
    ScheduleCandidateRead,
    ScheduleRemapRequest,
    TeachingTaskCreate,
    TeachingTaskRead,
    TeachingTaskUpdate,
)
from app.services.ai_outline_generation import (
    OutlineEvidenceError,
    OutlineValidationError,
    build_outline_evidence,
    generate_ai_outline,
)
from app.services.ai_outline_sections import (
    OutlineSections,
    OutlineSectionsError,
    build_sections_evidence,
    generate_outline_sections,
    sections_from_dict,
    sections_to_dict,
)
from app.services.course_standard_assessment import CourseAssessments, read_course_assessments
from app.services.course_standard_parser import parse_course_standard
from app.services.course_standard_resources import CourseResources, read_course_resources
from app.services.course_readiness import build_course_readiness
from app.services.course_progress import summarize_course_sessions
from app.services.docx_exporter import OutlineTemplateError, fill_lesson_docx, fill_outline_docx
from app.services.export_history import export_history, record_export
from app.services.lesson_generator import generate_lesson_plans
from app.services.lesson_evidence import canonical_code
from app.services.academic_term import normalize_term
from app.services.lesson_template_filler import LessonTemplateError
from app.services.openai_compatible import ModelProviderError
from app.services.workbench_import import (
    WorkbenchError,
    owned_by,
    push_document,
    workbench_from_env,
)
from app.services.outline_revision import OutlineRevisionError, generate_outline_revision
from app.services.outline_template_filler import template_marks_generated_sections
from app.services.post_class_reflection import (
    build_adjustment_block,
    generate_adjustment_suggestion,
    remove_adjustment_block,
)
from app.services.schedule_parser import ScheduleParseError, analyze_schedule, parse_schedule
from app.services.schedule_candidate import (
    ScheduleCandidateError,
    apply_schedule_candidate,
    build_parse_meta,
    parse_meta,
    replace_candidate_sessions,
    schedule_candidate_read,
)
from app.services.session_material_exporter import export_session_material_docx
from app.services.session_material_ai import SessionMaterialValidationError, generate_ai_session_material
from app.services.source_validation import build_source_review
from app.services.talent_plan_parser import parse_talent_plan
from app.services.task_deletion import delete_teaching_task
from app.services.task_material_store import (
    MaterialUploadError,
    active_asset,
    replace_active_asset,
    validate_upload_filename,
    write_unique_asset,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])
DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
TASK_FILE_DIR = Path(os.getenv("TASK_FILE_DIR", os.getenv("UPLOAD_DIR", "uploads"))) / "task-files"
TEMPLATE_FILES = {
    "outline": "outline_template.docx",
    "lesson": "lesson_template.docx",
}
# What the workbench files as a deliverable. Session materials and the uploaded
# source documents stay here until there is a reason for them to travel.
PUSHABLE_ARTIFACTS = {
    "lesson": "整门课教案",
    "outline": "课程实施大纲",
}
FIELD_NAMES_ZH = {
    "course_name": "课程名称",
    "class_name": "班级",
    "major": "专业",
    "location": "上课地点",
    "total_hours": "课程总学时",
    "hours_per_session": "每次课学时",
}


@router.post("", response_model=TeachingTaskRead)
def create_task(
    payload: TeachingTaskCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    data = payload.model_dump()
    # 学期要拿来分组排序，收在这一层而不是只收在表单上——直接调 API 的路径同样会写库
    data["term"] = normalize_term(data["term"])
    major_id = data.get("major_id")
    if major_id is not None:
        major = session.get(Major, major_id)
        if major is None or not major.is_active:
            raise HTTPException(status_code=400, detail="Major not found")
        data["major"] = major.name
    if current_user.role == "teacher":
        data["teacher_name"] = current_user.name
    task = TeachingTask(**data, owner_id=current_user.id)
    session.add(task)
    session.commit()
    session.refresh(task)
    return _task_read(task, session)


@router.get("", response_model=list[TeachingTaskRead])
def list_tasks(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict]:
    query = select(TeachingTask).order_by(TeachingTask.created_at.desc())
    if current_user.role != "admin":
        query = query.where(TeachingTask.owner_id == current_user.id)
    tasks = session.exec(query).all()
    return [_task_read(task, session) for task in tasks]


@router.patch("/{task_id}", response_model=TeachingTaskRead)
def update_task(
    task_id: int,
    payload: TeachingTaskUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    task = _get_task_or_404(task_id, session, current_user)
    data = payload.model_dump(exclude_unset=True)
    if "term" in data:
        data["term"] = normalize_term(data["term"])
    if data.get("major_id") is not None:
        major = session.get(Major, data["major_id"])
        if major is None or not major.is_active:
            raise HTTPException(status_code=400, detail="Major not found")
        data["major"] = major.name
    # Same rule as creation: a teacher's courses carry their own name.
    if current_user.role == "teacher":
        data.pop("teacher_name", None)
    for name in ("course_name", "class_name", "major", "location"):
        if name in data and not str(data[name]).strip():
            raise HTTPException(status_code=400, detail=f"{FIELD_NAMES_ZH[name]}不能为空")
    for name in ("total_hours", "hours_per_session"):
        if name in data and (data[name] is None or data[name] < 1):
            raise HTTPException(status_code=400, detail=f"{FIELD_NAMES_ZH[name]}必须大于 0")
    for name, value in data.items():
        setattr(task, name, value.strip() if isinstance(value, str) else value)
    session.add(task)
    session.commit()
    session.refresh(task)
    return _task_read(task, session)


@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Response:
    task = _get_task_or_404(task_id, session, current_user)
    delete_teaching_task(session, task, TASK_FILE_DIR)
    return Response(status_code=204)


@router.get("/{task_id}/readiness", response_model=CourseReadinessRead)
def get_course_readiness(
    task_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    task = _get_task_or_404(task_id, session, current_user)
    materials = session.exec(select(TaskMaterialAsset).where(TaskMaterialAsset.task_id == task_id)).all()
    goals = session.exec(select(CourseGoal).where(CourseGoal.task_id == task_id)).all()
    projects = session.exec(select(CourseProject).where(CourseProject.task_id == task_id)).all()
    indicators = session.exec(select(AbilityIndicator).where(AbilityIndicator.task_id == task_id)).all()
    schedule = session.exec(
        select(ScheduleSessionRecord)
        .where(ScheduleSessionRecord.task_id == task_id)
        .order_by(ScheduleSessionRecord.session_no)
    ).all()
    outline_rows = session.exec(select(OutlineRow).where(OutlineRow.task_id == task_id)).all()
    notices = session.exec(
        select(CourseReviewNotice).where(
            CourseReviewNotice.task_id == task_id,
            CourseReviewNotice.resolved_at == None,  # noqa: E711
        )
    ).all()
    ai_config = session.exec(
        select(AiModelConfig).where(
            AiModelConfig.enabled == True,  # noqa: E712
            AiModelConfig.connection_status == "connected",
        )
    ).first()
    pending = session.exec(
        select(ScheduleImportCandidate)
        .where(ScheduleImportCandidate.task_id == task_id, ScheduleImportCandidate.status == "pending")
        .order_by(ScheduleImportCandidate.created_at.desc())
    ).first()
    uploader_ids = {asset.uploaded_by_id for asset in materials}
    uploader_names = {
        user.id: user.name
        for user in session.exec(select(User).where(User.id.in_(uploader_ids))).all()
        if user.id is not None
    } if uploader_ids else {}
    legacy_templates = {
        kind for kind in ("outline", "lesson") if _task_template_path(task_id, kind).exists()
    }
    result = build_course_readiness(
        task=task,
        materials=materials,
        goals=goals,
        projects=projects,
        indicators=indicators,
        confirmation=session.get(SourceConfirmation, task_id),
        schedule=schedule,
        outline_rows=outline_rows,
        ai_config=ai_config,
        notices=notices,
        legacy_templates=legacy_templates,
        pending_schedule=pending,
        uploader_names=uploader_names,
    )
    payload = asdict(result)
    payload["source_review"] = _source_review(task_id, session).model_dump()
    payload["pending_schedule"] = schedule_candidate_read(session, pending) if pending is not None else None
    payload["review_notices"] = [
        {"id": item.id, "artifact_type": item.artifact_type, "reason": item.reason, "created_at": item.created_at}
        for item in notices
    ]
    return payload


@router.post("/{task_id}/review-notices/{notice_id}/resolve")
def resolve_course_review_notice(
    task_id: int,
    notice_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    _get_task_or_404(task_id, session, current_user)
    notice = session.get(CourseReviewNotice, notice_id)
    if notice is None or notice.task_id != task_id:
        raise HTTPException(status_code=404, detail="复核提示不存在")
    if notice.resolved_at is not None:
        raise HTTPException(status_code=409, detail="该复核提示已经处理")
    notice.resolved_at = datetime.now(timezone.utc)
    session.add(notice)
    session.commit()
    return {"status": "resolved"}


@router.post("/{task_id}/course-standard", response_model=ParseSummary)
async def upload_course_standard(
    task_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ParseSummary:
    _get_task_or_404(task_id, session, current_user)
    try:
        suffix = validate_upload_filename("course_standard", file.filename or "")
    except MaterialUploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    content = await file.read()
    temp_path = _save_content_to_temp(content, suffix)
    try:
        parsed = parse_course_standard(temp_path)
    finally:
        temp_path.unlink(missing_ok=True)

    if not parsed.goals:
        raise HTTPException(status_code=400, detail="Course standard goals are required")
    # Without projects the outline can never be generated, and there is no
    # manual entry path. Say so now instead of marking the material "ready"
    # and failing at generation time.
    if not parsed.projects:
        raise HTTPException(
            status_code=400,
            detail=(
                "课程标准里未识别到教学项目表：需要一张表头含「项目名称」「教学内容」「参考课时」的表格，"
                "参考课时写成总数（12）或理论/实践（8/4），请检查后重新上传"
            ),
        )

    assert current_user.id is not None
    asset_path = write_unique_asset(TASK_FILE_DIR, task_id, "course_standard", suffix, content)

    try:
        _delete_existing(session, CourseGoal, task_id)
        _delete_existing(session, CourseProject, task_id)
        for goal in parsed.goals:
            session.add(
                CourseGoal(
                    task_id=task_id,
                    code=goal.code,
                    description=goal.description,
                    ability_codes=" ".join(goal.ability_codes),
                )
            )
        for sequence_no, project in enumerate(parsed.projects, start=1):
            session.add(
                CourseProject(
                    task_id=task_id,
                    sequence_no=sequence_no,
                    name=project.name,
                    description=project.description,
                    teaching_content=project.teaching_content,
                    suggested_methods=project.suggested_methods,
                    course_goal_codes=" ".join(project.course_goal_codes),
                    ability_codes=" ".join(project.ability_codes),
                    reference_hours=project.reference_hours,
                    practice_hours=project.practice_hours,
                )
            )
        replace_active_asset(
            session,
            TaskMaterialAsset(
                task_id=task_id,
                kind="course_standard",
                original_filename=file.filename or "course-standard.docx",
                storage_path=str(asset_path),
                size_bytes=len(content),
                uploaded_by_id=current_user.id,
                summary_json=json.dumps({"goals_count": len(parsed.goals), "projects_count": len(parsed.projects)}),
            ),
        )
        _mark_artifacts_for_review(session, task_id, "课程标准已更新，请复核基于旧资料生成的内容")
        _delete_existing(session, SourceConfirmation, task_id)
        session.commit()
    except Exception:
        session.rollback()
        asset_path.unlink(missing_ok=True)
        raise
    return ParseSummary(task_id=task_id, goals_count=len(parsed.goals), projects_count=len(parsed.projects))


@router.post("/{task_id}/talent-plan", response_model=ParseSummary)
async def upload_talent_plan(
    task_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ParseSummary:
    _get_task_or_404(task_id, session, current_user)
    try:
        suffix = validate_upload_filename("talent_plan", file.filename or "")
    except MaterialUploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    content = await file.read()
    temp_path = _save_content_to_temp(content, suffix)
    try:
        parsed = parse_talent_plan(temp_path)
    finally:
        temp_path.unlink(missing_ok=True)

    if not parsed.indicators:
        raise HTTPException(status_code=400, detail="Talent plan indicators are required")

    assert current_user.id is not None
    asset_path = write_unique_asset(TASK_FILE_DIR, task_id, "talent_plan", suffix, content)

    try:
        _delete_existing(session, AbilityIndicator, task_id)
        for indicator in parsed.indicators:
            session.add(
                AbilityIndicator(
                    task_id=task_id,
                    code=indicator.code,
                    category=indicator.category,
                    group_code=indicator.group_code,
                    description=indicator.description,
                )
            )
        replace_active_asset(
            session,
            TaskMaterialAsset(
                task_id=task_id,
                kind="talent_plan",
                original_filename=file.filename or "talent-plan.docx",
                storage_path=str(asset_path),
                size_bytes=len(content),
                uploaded_by_id=current_user.id,
                summary_json=json.dumps({"indicators_count": len(parsed.indicators)}),
            ),
        )
        _mark_artifacts_for_review(session, task_id, "人才培养方案已更新，请复核能力指标引用")
        _delete_existing(session, SourceConfirmation, task_id)
        session.commit()
    except Exception:
        session.rollback()
        asset_path.unlink(missing_ok=True)
        raise
    return ParseSummary(task_id=task_id, indicators_count=len(parsed.indicators))


@router.get("/{task_id}/sources/review", response_model=SourceReviewRead)
def review_sources(
    task_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> SourceReviewRead:
    _get_task_or_404(task_id, session, current_user)
    return _source_review(task_id, session)


@router.post("/{task_id}/sources/confirm", response_model=SourceReviewRead)
def confirm_sources(
    task_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> SourceReviewRead:
    _get_task_or_404(task_id, session, current_user)
    review = _source_review(task_id, session)
    if not review.can_confirm:
        detail = "Course goals and ability indicators are required"
        if review.unknown_codes:
            detail = f"Unknown ability codes: {', '.join(review.unknown_codes)}"
        raise HTTPException(status_code=400, detail=detail)

    confirmation = session.get(SourceConfirmation, task_id)
    assert current_user.id is not None
    if confirmation is None:
        confirmation = SourceConfirmation(task_id=task_id, confirmed_by_id=current_user.id)
    else:
        confirmation.confirmed_by_id = current_user.id
        confirmation.confirmed_at = datetime.now(timezone.utc)
    session.add(confirmation)
    session.commit()
    return _source_review(task_id, session)


@router.post("/{task_id}/schedule", response_model=ParseSummary)
async def upload_schedule(
    task_id: int,
    file: UploadFile = File(...),
    teaching_class: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ParseSummary:
    task = _get_task_or_404(task_id, session, current_user)
    suffix = Path(file.filename or "").suffix.lower() or ".xlsx"
    temp_path = await _save_upload_to_temp(file, suffix)
    try:
        parsed = parse_schedule(
            temp_path,
            course_name=task.course_name,
            teaching_class=teaching_class or None,
        )
    except ScheduleParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        temp_path.unlink(missing_ok=True)

    _delete_existing(session, ScheduleSessionRecord, task_id)
    for index, parsed_session in enumerate(parsed, start=1):
        session.add(
            ScheduleSessionRecord(
                task_id=task_id,
                session_no=index,
                week_no=parsed_session.week_no,
                date_text=parsed_session.date_text,
                weekday=parsed_session.weekday,
                periods=parsed_session.periods,
                course_name=parsed_session.course_name,
                class_name=parsed_session.class_name,
                location=parsed_session.location,
                hours=parsed_session.hours,
            )
        )
    session.commit()
    return ParseSummary(task_id=task_id, sessions_count=len(parsed))


@router.post("/{task_id}/templates/{kind}")
async def upload_template(
    task_id: int,
    kind: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict[str, int | str]:
    _get_task_or_404(task_id, session, current_user)
    asset_kind = f"{kind}_template"
    try:
        suffix = validate_upload_filename(asset_kind, file.filename or "")
    except MaterialUploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    content = await file.read()
    assert current_user.id is not None
    target_path = write_unique_asset(TASK_FILE_DIR, task_id, asset_kind, suffix, content)
    try:
        replace_active_asset(
            session,
            TaskMaterialAsset(
                task_id=task_id,
                kind=asset_kind,
                original_filename=file.filename or f"{kind}-template.docx",
                storage_path=str(target_path),
                size_bytes=len(content),
                uploaded_by_id=current_user.id,
            ),
        )
        session.commit()
    except Exception:
        session.rollback()
        target_path.unlink(missing_ok=True)
        raise
    return {"task_id": task_id, "kind": kind, "filename": file.filename or target_path.name, "size": len(content)}


def _mapping_from_form(raw: str | None) -> dict[str, int] | None:
    if not raw:
        return None
    try:
        mapping = json.loads(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="列对应关系不是合法的 JSON") from exc
    if not isinstance(mapping, dict):
        raise HTTPException(status_code=400, detail="列对应关系必须是字段到列号的映射")
    return {str(key): int(value) for key, value in mapping.items()}


def _analyze_or_400(
    path: Path,
    *,
    header_row: int | None,
    mapping: dict[str, int] | None,
    course_name: str | None,
    teaching_class: str | None = None,
):
    try:
        return analyze_schedule(
            path,
            header_row=header_row,
            mapping=mapping,
            course_name=course_name,
            teaching_class=teaching_class,
        )
    except ScheduleParseError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "message": str(exc),
                "detected_headers": exc.detected_headers,
                "missing_fields": exc.missing_fields,
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{task_id}/schedule-candidates", response_model=ScheduleCandidateRead)
async def upload_schedule_candidate(
    task_id: int,
    file: UploadFile = File(...),
    header_row: int | None = Form(None),
    mapping: str | None = Form(None),
    course_name: str | None = Form(None),
    teaching_class: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    task = _get_task_or_404(task_id, session, current_user)
    try:
        suffix = validate_upload_filename("schedule", file.filename or "")
    except MaterialUploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    content = await file.read()
    column_mapping = _mapping_from_form(mapping)
    course_filter = course_name if course_name is not None else task.course_name
    class_filter = teaching_class or ""
    temp_path = _save_content_to_temp(content, suffix)
    try:
        analysis = _analyze_or_400(
            temp_path,
            header_row=header_row,
            mapping=column_mapping,
            course_name=course_filter,
            teaching_class=class_filter or None,
        )
    finally:
        temp_path.unlink(missing_ok=True)
    if not analysis.sessions:
        raise HTTPException(status_code=400, detail=_no_sessions_detail(analysis, course_filter))
    assert current_user.id is not None
    asset_path = write_unique_asset(TASK_FILE_DIR, task_id, "schedule_candidate", suffix, content)
    pending = session.exec(
        select(ScheduleImportCandidate).where(
            ScheduleImportCandidate.task_id == task_id,
            ScheduleImportCandidate.status == "pending",
        )
    ).all()
    for item in pending:
        item.status = "discarded"
        session.add(item)
    candidate = ScheduleImportCandidate(
        task_id=task_id,
        original_filename=file.filename or "schedule.xlsx",
        storage_path=str(asset_path),
        uploaded_by_id=current_user.id,
        parse_meta_json=build_parse_meta(analysis, course_filter or "", class_filter),
    )
    session.add(candidate)
    session.flush()
    assert candidate.id is not None
    replace_candidate_sessions(session, candidate, analysis.sessions)
    session.commit()
    session.refresh(candidate)
    return schedule_candidate_read(session, candidate)


@router.post("/{task_id}/schedule-candidates/{candidate_id}/remap", response_model=ScheduleCandidateRead)
def remap_schedule_candidate(
    task_id: int,
    candidate_id: int,
    payload: ScheduleRemapRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    task = _get_task_or_404(task_id, session, current_user)
    candidate = session.get(ScheduleImportCandidate, candidate_id)
    if candidate is None or candidate.task_id != task_id:
        raise HTTPException(status_code=404, detail="课表候选不存在")
    if candidate.status != "pending":
        raise HTTPException(status_code=409, detail="该课表候选已经处理，无法重新识别")
    stored = Path(candidate.storage_path)
    if not stored.exists():
        raise HTTPException(status_code=409, detail="原始课表文件已丢失，请重新上传")
    course_filter = payload.course_name if payload.course_name is not None else task.course_name
    # There is no task-level teaching class, so an omitted one means "keep what
    # was chosen last time" rather than "clear the filter".
    class_filter = (
        payload.teaching_class
        if payload.teaching_class is not None
        else parse_meta(candidate).get("teaching_class", "")
    )
    analysis = _analyze_or_400(
        stored,
        header_row=payload.header_row,
        mapping=payload.mapping,
        course_name=course_filter,
        teaching_class=class_filter or None,
    )
    if not analysis.sessions:
        raise HTTPException(status_code=400, detail="按当前列对应关系解析不出任何课次")
    candidate.parse_meta_json = build_parse_meta(analysis, course_filter or "", class_filter)
    replace_candidate_sessions(session, candidate, analysis.sessions)
    session.add(candidate)
    session.commit()
    session.refresh(candidate)
    return schedule_candidate_read(session, candidate)


@router.post("/{task_id}/schedule-candidates/{candidate_id}/confirm", response_model=ScheduleCandidateRead)
def confirm_schedule_candidate(
    task_id: int,
    candidate_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    _get_task_or_404(task_id, session, current_user)
    candidate = session.get(ScheduleImportCandidate, candidate_id)
    if candidate is None or candidate.task_id != task_id:
        raise HTTPException(status_code=404, detail="课表候选不存在")
    assert current_user.id is not None
    try:
        return apply_schedule_candidate(session, candidate, current_user.id)
    except ScheduleCandidateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{task_id}/schedule-candidates/{candidate_id}/discard", response_model=ScheduleCandidateRead)
def discard_schedule_candidate(
    task_id: int,
    candidate_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    _get_task_or_404(task_id, session, current_user)
    candidate = session.get(ScheduleImportCandidate, candidate_id)
    if candidate is None or candidate.task_id != task_id:
        raise HTTPException(status_code=404, detail="课表候选不存在")
    if candidate.status != "pending":
        raise HTTPException(status_code=409, detail="该课表候选已经处理")
    candidate.status = "discarded"
    session.add(candidate)
    session.commit()
    session.refresh(candidate)
    return schedule_candidate_read(session, candidate)


@router.post("/{task_id}/outline/generate", response_model=list[OutlineRowRead])
def generate_outline(
    task_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[OutlineRow]:
    task = _get_task_or_404(task_id, session, current_user)
    if session.get(SourceConfirmation, task_id) is None:
        raise HTTPException(status_code=400, detail="Confirm course sources before generating outline")
    existing = session.exec(select(OutlineRow).where(OutlineRow.task_id == task_id)).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="课程实施大纲已存在，请使用单次课局部优化")
    with _outline_generation_guard(task_id):
        return _generate_outline_rows(task_id, task, session)


_OUTLINE_GENERATION_IN_PROGRESS: set[int] = set()
_OUTLINE_GENERATION_LOCK = threading.Lock()


@contextmanager
def _outline_generation_guard(task_id: int):
    """One outline generation per course at a time.

    The model call takes minutes, and the request has been seen to outlive the
    proxy timeout: the browser reported failure, the teacher clicked again, and
    both requests -- each having found no rows when it looked -- wrote a full
    set. Two 第 1 次课 in the outline then became two lesson plans per session.
    The check above cannot see a request still in flight; this can.
    """
    with _OUTLINE_GENERATION_LOCK:
        if task_id in _OUTLINE_GENERATION_IN_PROGRESS:
            raise HTTPException(
                status_code=409,
                detail="课程实施大纲正在生成中（上一次请求仍在处理），请等待一两分钟后刷新页面查看，不要重复点击",
            )
        _OUTLINE_GENERATION_IN_PROGRESS.add(task_id)
    try:
        yield
    finally:
        with _OUTLINE_GENERATION_LOCK:
            _OUTLINE_GENERATION_IN_PROGRESS.discard(task_id)


def _generate_outline_rows(task_id: int, task: TeachingTask, session: Session) -> list[OutlineRow]:
    config = session.exec(
        select(AiModelConfig)
        .where(
            AiModelConfig.enabled == True,  # noqa: E712
            AiModelConfig.connection_status == "connected",
        )
        .order_by(AiModelConfig.id)
    ).first()
    if config is None:
        raise HTTPException(status_code=409, detail="AI 模型尚未配置、测试并启用，请联系管理员")
    projects = session.exec(
        select(CourseProject).where(CourseProject.task_id == task_id).order_by(CourseProject.sequence_no)
    ).all()
    if not projects:
        raise HTTPException(status_code=409, detail="课程标准中没有可拆分的教学项目，请补充资料或人工填写")
    goals = session.exec(select(CourseGoal).where(CourseGoal.task_id == task_id).order_by(CourseGoal.code)).all()
    indicators = session.exec(
        select(AbilityIndicator).where(AbilityIndicator.task_id == task_id).order_by(AbilityIndicator.id)
    ).all()
    schedule_records = session.exec(
        select(ScheduleSessionRecord)
        .where(ScheduleSessionRecord.task_id == task_id)
        .order_by(ScheduleSessionRecord.session_no)
    ).all()
    if not schedule_records:
        raise HTTPException(status_code=409, detail="请先上传并确认课表")
    try:
        evidence = build_outline_evidence(task, projects, goals, indicators, schedule_records)
        generated_rows = generate_ai_outline(config, evidence)
    except (OutlineEvidenceError, OutlineValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModelProviderError as exc:
        raise HTTPException(status_code=502, detail="AI 生成课程实施大纲失败，请稍后重试") from exc

    # Look again after the model call: the guard above is per process, and a
    # second worker or a restart in between would not have seen this request.
    if session.exec(select(OutlineRow).where(OutlineRow.task_id == task_id)).first() is not None:
        raise HTTPException(
            status_code=409,
            detail="生成期间课程实施大纲已由另一次请求写入，本次结果未保存。请刷新页面查看现有大纲",
        )
    rows: list[OutlineRow] = []
    for row in generated_rows:
        model = OutlineRow(task_id=task_id, **row.__dict__)
        session.add(model)
        rows.append(model)
    session.commit()
    for row in rows:
        session.refresh(row)
    return rows


@router.get("/{task_id}/outline", response_model=list[OutlineRowRead])
def list_outline_rows(
    task_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict]:
    _get_task_or_404(task_id, session, current_user)
    rows = session.exec(
        select(OutlineRow).where(OutlineRow.task_id == task_id).order_by(OutlineRow.session_no)
    ).all()
    reflections = session.exec(
        select(PostClassReflection).where(PostClassReflection.task_id == task_id)
    ).all()
    recorded_ids = {item.outline_row_id for item in reflections}
    adjusted_ids = {
        item.target_outline_row_id
        for item in reflections
        if item.status == "applied" and item.target_outline_row_id is not None
    }
    return [
        {
            **row.model_dump(),
            "post_class_recorded": row.id in recorded_ids,
            "has_previous_adjustment": row.id in adjusted_ids,
        }
        for row in rows
    ]


@router.put("/{task_id}/outline/{row_id}", response_model=OutlineRowRead)
def update_outline_row(
    task_id: int,
    row_id: int,
    payload: OutlineRowUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> OutlineRow:
    _get_task_or_404(task_id, session, current_user)
    row = session.get(OutlineRow, row_id)
    if row is None or row.task_id != task_id:
        raise HTTPException(status_code=404, detail="Outline row not found")
    _validate_outline_code_selection(task_id, payload.course_goal_codes, payload.ability_codes, session)
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.post(
    "/{task_id}/outline/{row_id}/revision-candidates",
    response_model=OutlineRevisionCandidateRead,
)
def create_outline_revision_candidate(
    task_id: int,
    row_id: int,
    payload: OutlineRevisionRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> OutlineRevisionCandidate:
    _get_task_or_404(task_id, session, current_user)
    row = _get_outline_row_or_404(task_id, row_id, session)
    config = session.exec(
        select(AiModelConfig)
        .where(
            AiModelConfig.enabled == True,  # noqa: E712
            AiModelConfig.connection_status == "connected",
        )
        .order_by(AiModelConfig.id)
    ).first()
    if config is None:
        raise HTTPException(status_code=409, detail="AI 模型尚未配置、测试并启用，请联系管理员")
    previous_row = session.exec(
        select(OutlineRow)
        .where(OutlineRow.task_id == task_id, OutlineRow.session_no < row.session_no)
        .order_by(OutlineRow.session_no.desc())
    ).first()
    next_row = session.exec(
        select(OutlineRow)
        .where(OutlineRow.task_id == task_id, OutlineRow.session_no > row.session_no)
        .order_by(OutlineRow.session_no)
    ).first()
    try:
        proposed = generate_outline_revision(
            config,
            row,
            previous_row,
            next_row,
            payload.field_name,
            payload.instruction,
        )
    except OutlineRevisionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModelProviderError as exc:
        raise HTTPException(status_code=502, detail="AI 局部优化失败，请稍后重试") from exc
    original = _outline_revision_content(row, payload.field_name)
    assert current_user.id is not None
    candidate = OutlineRevisionCandidate(
        task_id=task_id,
        outline_row_id=row_id,
        field_name=payload.field_name,
        original_content=original,
        proposed_content=proposed,
        teacher_instruction=payload.instruction,
        source_updated_at=row.updated_at,
        created_by_id=current_user.id,
    )
    session.add(candidate)
    session.commit()
    session.refresh(candidate)
    return candidate


@router.post(
    "/{task_id}/outline-revision-candidates/{candidate_id}/accept",
    response_model=OutlineRevisionCandidateRead,
)
def accept_outline_revision_candidate(
    task_id: int,
    candidate_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> OutlineRevisionCandidate:
    _get_task_or_404(task_id, session, current_user)
    candidate = _get_outline_revision_candidate_or_404(task_id, candidate_id, session)
    row = _get_outline_row_or_404(task_id, candidate.outline_row_id, session)
    if candidate.status != "pending":
        raise HTTPException(status_code=409, detail="该候选内容已经处理")
    if candidate.source_updated_at != row.updated_at:
        raise HTTPException(status_code=409, detail="原课程实施大纲已被修改，请重新生成候选内容")
    _apply_outline_revision(row, candidate.field_name, candidate.proposed_content)
    row.updated_at = datetime.now(timezone.utc)
    candidate.status = "accepted"
    session.add(row)
    session.add(candidate)
    session.commit()
    session.refresh(candidate)
    return candidate


@router.post(
    "/{task_id}/outline-revision-candidates/{candidate_id}/reject",
    response_model=OutlineRevisionCandidateRead,
)
def reject_outline_revision_candidate(
    task_id: int,
    candidate_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> OutlineRevisionCandidate:
    _get_task_or_404(task_id, session, current_user)
    candidate = _get_outline_revision_candidate_or_404(task_id, candidate_id, session)
    if candidate.status != "pending":
        raise HTTPException(status_code=409, detail="该候选内容已经处理")
    candidate.status = "rejected"
    session.add(candidate)
    session.commit()
    session.refresh(candidate)
    return candidate


@router.post("/{task_id}/lessons/generate", response_model=list[LessonPlanRead])
def generate_lessons(
    task_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[LessonPlan]:
    task = _get_task_or_404(task_id, session, current_user)
    outline_rows = session.exec(
        select(OutlineRow).where(OutlineRow.task_id == task_id).order_by(OutlineRow.session_no)
    ).all()
    if not outline_rows:
        raise HTTPException(status_code=400, detail="Outline rows are required")

    active_reflections = session.exec(
        select(PostClassReflection).where(
            PostClassReflection.task_id == task_id,
            PostClassReflection.status == "applied",
        )
    ).all()
    generated_plans = generate_lesson_plans(task, outline_rows)
    _delete_existing(session, LessonPlan, task_id)
    lessons: list[LessonPlan] = []
    for plan in generated_plans:
        lesson = LessonPlan(task_id=task_id, **plan.__dict__)
        session.add(lesson)
        lessons.append(lesson)
    task.status = "completed"
    session.add(task)
    session.commit()
    for lesson in lessons:
        session.refresh(lesson)
    lesson_by_outline = {lesson.outline_row_id: lesson for lesson in lessons}
    outline_by_id = {row.id: row for row in outline_rows}
    for reflection in active_reflections:
        target_lesson = lesson_by_outline.get(reflection.target_outline_row_id)
        source_outline = outline_by_id.get(reflection.outline_row_id)
        if target_lesson is None or source_outline is None or reflection.id is None:
            reflection.status = "pending"
            reflection.applied_lesson_plan_id = None
            reflection.applied_block_marker = ""
        else:
            target_lesson.teaching_process = build_adjustment_block(
                target_lesson.teaching_process,
                reflection.id,
                f"第 {source_outline.session_no} 次课",
                reflection.suggestion_text,
            )
            reflection.applied_lesson_plan_id = target_lesson.id
            reflection.applied_block_marker = f"post-class-reflection:{reflection.id}"
            session.add(target_lesson)
        session.add(reflection)
    if active_reflections:
        session.commit()
        for lesson in lessons:
            session.refresh(lesson)
    return lessons


@router.get("/{task_id}/lessons", response_model=list[LessonPlanRead])
def list_lessons(
    task_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[LessonPlan]:
    _get_task_or_404(task_id, session, current_user)
    return session.exec(
        select(LessonPlan).where(LessonPlan.task_id == task_id).order_by(LessonPlan.session_no)
    ).all()


@router.put("/{task_id}/lessons/{lesson_id}", response_model=LessonPlanRead)
def update_lesson(
    task_id: int,
    lesson_id: int,
    payload: LessonPlanUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> LessonPlan:
    _get_task_or_404(task_id, session, current_user)
    lesson = session.get(LessonPlan, lesson_id)
    if lesson is None or lesson.task_id != task_id:
        raise HTTPException(status_code=404, detail="Lesson plan not found")
    for key, value in payload.model_dump().items():
        setattr(lesson, key, value)
    session.add(lesson)
    session.commit()
    session.refresh(lesson)
    return lesson


@router.get("/{task_id}/sessions/{outline_row_id}", response_model=SessionWorkspaceRead)
def get_session_workspace(
    task_id: int,
    outline_row_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    _get_task_or_404(task_id, session, current_user)
    outline = _get_outline_row_or_404(task_id, outline_row_id, session)
    lesson = session.exec(
        select(LessonPlan).where(
            LessonPlan.task_id == task_id,
            LessonPlan.outline_row_id == outline_row_id,
        )
    ).first()
    materials = session.exec(
        select(SessionMaterial)
        .where(
            SessionMaterial.task_id == task_id,
            SessionMaterial.outline_row_id == outline_row_id,
        )
        .order_by(SessionMaterial.created_at)
    ).all()
    reflection = session.exec(
        select(PostClassReflection).where(
            PostClassReflection.task_id == task_id,
            PostClassReflection.outline_row_id == outline_row_id,
        )
    ).first()
    next_outline = _get_next_outline_row(task_id, outline, session)
    next_lesson_exists = False
    if next_outline is not None:
        next_lesson_exists = session.exec(
            select(LessonPlan).where(
                LessonPlan.task_id == task_id,
                LessonPlan.outline_row_id == next_outline.id,
            )
        ).first() is not None
    return {
        "outline": outline,
        "lesson": lesson,
        "materials": materials,
        "reflection": reflection,
        "next_outline": next_outline,
        "next_lesson_exists": next_lesson_exists,
    }


@router.put(
    "/{task_id}/sessions/{outline_row_id}/reflection",
    response_model=PostClassReflectionRead,
)
def upsert_reflection(
    task_id: int,
    outline_row_id: int,
    payload: PostClassReflectionUpsert,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> PostClassReflection:
    _get_task_or_404(task_id, session, current_user)
    outline = _get_outline_row_or_404(task_id, outline_row_id, session)
    existing = session.exec(
        select(PostClassReflection).where(
            PostClassReflection.task_id == task_id,
            PostClassReflection.outline_row_id == outline_row_id,
        )
    ).first()
    if existing is not None and existing.status == "applied":
        raise HTTPException(status_code=409, detail="Revert the applied adjustment before editing")

    suggestion = generate_adjustment_suggestion(
        payload.progress_status,
        payload.mastery_level,
        payload.classroom_effect,
        payload.note,
    )
    next_outline = _get_next_outline_row(task_id, outline, session)
    assert current_user.id is not None
    reflection = existing or PostClassReflection(
        task_id=task_id,
        outline_row_id=outline_row_id,
        owner_user_id=current_user.id,
        progress_status=payload.progress_status,
        mastery_level=payload.mastery_level,
        classroom_effect=payload.classroom_effect,
    )
    for key, value in payload.model_dump().items():
        setattr(reflection, key, value)
    reflection.suggestion_type = suggestion.suggestion_type
    reflection.suggestion_text = suggestion.text
    reflection.suggested_minutes = suggestion.suggested_minutes
    reflection.target_outline_row_id = next_outline.id if next_outline else None
    reflection.status = "pending"
    reflection.applied_lesson_plan_id = None
    reflection.applied_block_marker = ""
    reflection.updated_at = datetime.now(timezone.utc)
    reflection.applied_at = None
    reflection.reverted_at = None
    session.add(reflection)
    session.commit()
    session.refresh(reflection)
    return reflection


@router.delete("/{task_id}/reflections/{reflection_id}", status_code=204)
def delete_reflection(
    task_id: int,
    reflection_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Response:
    _get_task_or_404(task_id, session, current_user)
    reflection = _get_reflection_or_404(task_id, reflection_id, session)
    if reflection.status == "applied":
        raise HTTPException(status_code=409, detail="Revert the applied adjustment before deleting")
    session.delete(reflection)
    session.commit()
    return Response(status_code=204)


@router.post("/{task_id}/reflections/{reflection_id}/apply", response_model=LessonPlanRead)
def apply_reflection(
    task_id: int,
    reflection_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> LessonPlan:
    _get_task_or_404(task_id, session, current_user)
    reflection = _get_reflection_or_404(task_id, reflection_id, session)
    if reflection.target_outline_row_id is None:
        raise HTTPException(status_code=409, detail="This is the final session")
    lesson = _get_lesson_by_outline(task_id, reflection.target_outline_row_id, session)
    if lesson is None:
        raise HTTPException(status_code=409, detail="Generate the next lesson plan before applying")
    if reflection.status == "applied":
        return lesson
    if reflection.suggestion_type == "none":
        raise HTTPException(status_code=409, detail="This reflection does not require an adjustment")
    source = _get_outline_row_or_404(task_id, reflection.outline_row_id, session)
    assert reflection.id is not None
    lesson.teaching_process = build_adjustment_block(
        lesson.teaching_process,
        reflection.id,
        f"第 {source.session_no} 次课",
        reflection.suggestion_text,
    )
    reflection.status = "applied"
    reflection.applied_lesson_plan_id = lesson.id
    reflection.applied_block_marker = f"post-class-reflection:{reflection.id}"
    reflection.applied_at = datetime.now(timezone.utc)
    reflection.reverted_at = None
    session.add(lesson)
    session.add(reflection)
    session.commit()
    session.refresh(lesson)
    return lesson


@router.post("/{task_id}/reflections/{reflection_id}/revert", response_model=LessonPlanRead)
def revert_reflection(
    task_id: int,
    reflection_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> LessonPlan:
    _get_task_or_404(task_id, session, current_user)
    reflection = _get_reflection_or_404(task_id, reflection_id, session)
    if reflection.target_outline_row_id is None:
        raise HTTPException(status_code=409, detail="This reflection has no target session")
    lesson = _get_lesson_by_outline(task_id, reflection.target_outline_row_id, session)
    if lesson is None:
        raise HTTPException(status_code=409, detail="The target lesson plan is not available")
    if reflection.status == "applied":
        lesson.teaching_process = remove_adjustment_block(lesson.teaching_process, reflection_id)
        reflection.status = "reverted"
        reflection.applied_lesson_plan_id = None
        reflection.applied_block_marker = ""
        reflection.reverted_at = datetime.now(timezone.utc)
        session.add(lesson)
        session.add(reflection)
        session.commit()
        session.refresh(lesson)
    return lesson


@router.post(
    "/{task_id}/sessions/{outline_row_id}/materials/generate",
    response_model=SessionMaterialRead,
)
def generate_material(
    task_id: int,
    outline_row_id: int,
    payload: SessionMaterialGenerate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> SessionMaterial:
    task = _get_task_or_404(task_id, session, current_user)
    config = session.exec(
        select(AiModelConfig)
        .where(
            AiModelConfig.enabled == True,  # noqa: E712
            AiModelConfig.connection_status == "connected",
        )
        .order_by(AiModelConfig.id)
    ).first()
    if config is None:
        raise HTTPException(status_code=409, detail="AI 模型尚未配置、测试并启用，请联系管理员")
    outline = _get_outline_row_or_404(task_id, outline_row_id, session)
    lesson = session.exec(
        select(LessonPlan).where(
            LessonPlan.task_id == task_id,
            LessonPlan.outline_row_id == outline_row_id,
        )
    ).first()
    try:
        generated = generate_ai_session_material(config, task, outline, lesson, payload)
    except SessionMaterialValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModelProviderError as exc:
        raise HTTPException(status_code=502, detail="AI 生成失败，请稍后重试") from exc
    assert current_user.id is not None
    material = SessionMaterial(
        task_id=task_id,
        outline_row_id=outline_row_id,
        owner_user_id=current_user.id,
        generation_method="ai",
        **asdict(generated),
    )
    session.add(material)
    session.commit()
    session.refresh(material)
    return material


@router.put("/{task_id}/materials/{material_id}", response_model=SessionMaterialRead)
def update_material(
    task_id: int,
    material_id: int,
    payload: SessionMaterialUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> SessionMaterial:
    _get_task_or_404(task_id, session, current_user)
    material = _get_material_or_404(task_id, material_id, session)
    for key, value in payload.model_dump().items():
        setattr(material, key, value)
    material.updated_at = datetime.now(timezone.utc)
    session.add(material)
    session.commit()
    session.refresh(material)
    return material


@router.delete("/{task_id}/materials/{material_id}", status_code=204)
def delete_material(
    task_id: int,
    material_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Response:
    _get_task_or_404(task_id, session, current_user)
    material = _get_material_or_404(task_id, material_id, session)
    session.delete(material)
    session.commit()
    return Response(status_code=204)


@router.post("/{task_id}/materials/{material_id}/export")
def export_material_docx(
    task_id: int,
    material_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Response:
    task = _get_task_or_404(task_id, session, current_user)
    material = _get_material_or_404(task_id, material_id, session)
    outline = _get_outline_row_or_404(task_id, material.outline_row_id, session)
    with NamedTemporaryFile(delete=False, suffix=".docx") as output_file:
        output_path = Path(output_file.name)
    try:
        export_session_material_docx(output_path, task, outline, material)
        content = output_path.read_bytes()
    finally:
        output_path.unlink(missing_ok=True)

    filename = f"{task.course_name}_第{outline.session_no}次课_{material.title}.docx"
    assert current_user.id is not None
    record_export(
        session,
        root=TASK_FILE_DIR,
        task_id=task_id,
        artifact_type="session_material",
        filename=filename,
        content=content,
        exported_by_id=current_user.id,
        source_summary=f"第 {outline.session_no} 次课 · {material.title}",
        session_no=outline.session_no,
    )
    return _docx_download(content, filename)


@router.get("/{task_id}/exports", response_model=list[ExportRecordRead])
def list_exports(
    task_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[dict]:
    _get_task_or_404(task_id, session, current_user)
    return export_history(session, task_id)


@router.get("/{task_id}/exports/{export_id}/download")
def download_export(
    task_id: int,
    export_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Response:
    _get_task_or_404(task_id, session, current_user)
    record = session.get(ExportRecord, export_id)
    if record is None or record.task_id != task_id:
        raise HTTPException(status_code=404, detail="导出记录不存在")
    stored = Path(record.storage_path)
    if not stored.exists():
        raise HTTPException(status_code=410, detail="该导出文件已不在服务器上，请重新导出")
    return _docx_download(stored.read_bytes(), record.filename)


@router.post("/{task_id}/exports/{export_id}/push-to-workbench", response_model=WorkbenchPushRead)
def push_export_to_workbench(
    task_id: int,
    export_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    task = _get_task_or_404(task_id, session, current_user)
    try:
        workbench = workbench_from_env()
    except WorkbenchError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    # Not "this is not yours": whose workbench it is, is nobody else's business.
    if not owned_by(workbench, current_user.employee_no):
        raise HTTPException(status_code=404, detail="本部署未配置工作台回流")
    record = session.get(ExportRecord, export_id)
    if record is None or record.task_id != task_id:
        raise HTTPException(status_code=404, detail="导出记录不存在")
    kind = PUSHABLE_ARTIFACTS.get(record.artifact_type)
    if kind is None:
        raise HTTPException(
            status_code=400,
            detail="只有" + "和".join(PUSHABLE_ARTIFACTS.values()) + "可以回流到工作台",
        )
    stored = Path(record.storage_path)
    if not stored.exists():
        raise HTTPException(status_code=410, detail="该导出文件已不在服务器上，请重新导出")

    try:
        result = push_document(
            workbench,
            # Names the course and the kind, not this export: re-pushing a
            # better version replaces the record instead of stacking up beside
            # it, and the outline never overwrites the lesson plans.
            external_id=f"task-{task_id}-{record.artifact_type}",
            title=f"{task.course_name} {kind}",
            filename=record.filename,
            content=stored.read_bytes(),
            course_name=task.course_name,
            # 学期单独送一份。它本来就在 note 里，但那是拼给人读的一整串，
            # 工作台没法拿它分组或排序 —— 一门课教了几个学期，正是要分开看的东西。
            term=task.term,
            finished_at=record.created_at.date().isoformat(),
            note=f"{task.term} · {task.class_name} · {record.source_summary}"[:1000],
        )
    except WorkbenchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return result


@router.post("/{task_id}/lessons/export")
async def export_lessons_docx(
    task_id: int,
    file: UploadFile | None = File(default=None),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Response:
    task = _get_task_or_404(task_id, session, current_user)
    lessons = session.exec(
        select(LessonPlan).where(LessonPlan.task_id == task_id).order_by(LessonPlan.session_no)
    ).all()
    if not lessons:
        raise HTTPException(status_code=400, detail="Lesson plans are required")

    outline_rows = session.exec(
        select(OutlineRow).where(OutlineRow.task_id == task_id).order_by(OutlineRow.session_no)
    ).all()
    outline_by_id = {row.id: row for row in outline_rows}
    schedules = session.exec(
        select(ScheduleSessionRecord)
        .where(ScheduleSessionRecord.task_id == task_id)
        .order_by(ScheduleSessionRecord.session_no)
    ).all()
    schedule_by_session = {item.session_no: item for item in schedules}
    contexts = []
    for lesson in lessons:
        outline = outline_by_id.get(lesson.outline_row_id)
        schedule = schedule_by_session.get(lesson.session_no)
        contexts.append(
            {
                "week_no": outline.week_no if outline else "",
                "weekday": outline.weekday if outline else "",
                "periods": outline.periods if outline else "",
                "class_name": schedule.class_name if schedule else task.class_name,
                "location": schedule.location if schedule else task.location,
                "teaching_methods": outline.teaching_methods if outline else "",
                "pre_task": outline.pre_task if outline else "",
                "post_task": outline.post_task if outline else "",
            }
        )

    template = await _resolve_template_path(task_id, "lesson", file, session)
    with NamedTemporaryFile(delete=False, suffix=".docx") as output_file:
        output_path = Path(output_file.name)
    try:
        fill_lesson_docx(
            template.path,
            output_path,
            {
                "课程名称": task.course_name,
                "任课教师": task.teacher_name,
                "授课班级": task.class_name,
                "上课地点": task.location,
                "适用专业": task.major,
            },
            lessons,
            contexts=contexts,
        )
        content = output_path.read_bytes()
    except LessonTemplateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        output_path.unlink(missing_ok=True)

    filename = f"{task.course_name}_教案.docx"
    assert current_user.id is not None
    record_export(
        session,
        root=TASK_FILE_DIR,
        task_id=task_id,
        artifact_type="lesson",
        filename=filename,
        content=content,
        exported_by_id=current_user.id,
        template_filename=template.filename,
        source_summary=f"{len(lessons)} 份教案",
    )
    return _docx_download(content, filename)


@router.post("/{task_id}/outline/export")
async def export_outline_docx(
    task_id: int,
    file: UploadFile | None = File(default=None),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Response:
    task = _get_task_or_404(task_id, session, current_user)
    rows = session.exec(
        select(OutlineRow).where(OutlineRow.task_id == task_id).order_by(OutlineRow.session_no)
    ).all()
    if not rows:
        raise HTTPException(status_code=400, detail="Outline rows are required")

    template = await _resolve_template_path(task_id, "outline", file, session)
    # A template that marks nothing needs no body written and no model call; a
    # teacher's own finished outline is exactly that case.
    marked = template_marks_generated_sections(Document(str(template.path)))
    sections = _outline_sections(task, session) if marked else None
    resources, assessments = _course_standard_copies(task_id, session) if marked else (None, None)

    with NamedTemporaryFile(delete=False, suffix=".docx") as output_file:
        output_path = Path(output_file.name)
    try:
        fill_outline_docx(
            template.path,
            output_path,
            {
                "课程名称": task.course_name,
                "任课教师": task.teacher_name,
                "授课班级": task.class_name,
                "授课计划文本": _outline_rows_to_text(rows),
            },
            rows,
            sections=sections,
            resources=resources,
            assessments=assessments,
        )
        content = output_path.read_bytes()
    except OutlineTemplateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        output_path.unlink(missing_ok=True)

    filename = f"{task.course_name}_课程实施大纲.docx"
    confirmed = session.get(SourceConfirmation, task_id) is not None
    assert current_user.id is not None
    record_export(
        session,
        root=TASK_FILE_DIR,
        task_id=task_id,
        artifact_type="outline",
        filename=filename,
        content=content,
        exported_by_id=current_user.id,
        template_filename=template.filename,
        source_summary=f"{len(rows)} 行课程实施大纲，课程依据{'已确认' if confirmed else '未确认'}",
    )
    return _docx_download(content, filename)


@router.post("/{task_id}/outline/sections/regenerate")
def regenerate_outline_sections(
    task_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> dict:
    """Write the outline's prose again, for a teacher who wants a different take."""
    task = _get_task_or_404(task_id, session, current_user)
    return sections_to_dict(_outline_sections(task, session, regenerate=True))


def _outline_sections(task: TeachingTask, session: Session, regenerate: bool = False) -> OutlineSections:
    """The outline's body, written once and then kept.

    Written at export rather than beside 学习进程 so that each request carries a
    single model call -- the schedule alone already takes about 160 seconds on a
    full course, and two of those in one request would sit on the 300 秒 ceiling.
    """
    assert task.id is not None
    stored = session.get(OutlineSectionSet, task.id)
    if stored is not None and not regenerate:
        try:
            return sections_from_dict(json.loads(stored.payload_json))
        except (ValueError, TypeError, KeyError):
            # A set written by an older shape is worth regenerating, not shipping.
            pass

    config = session.exec(
        select(AiModelConfig)
        .where(
            AiModelConfig.enabled == True,  # noqa: E712
            AiModelConfig.connection_status == "connected",
        )
        .order_by(AiModelConfig.id)
    ).first()
    if config is None:
        raise HTTPException(status_code=409, detail="AI 模型尚未配置、测试并启用，请联系管理员")
    projects = session.exec(
        select(CourseProject).where(CourseProject.task_id == task.id).order_by(CourseProject.sequence_no)
    ).all()
    goals = session.exec(select(CourseGoal).where(CourseGoal.task_id == task.id).order_by(CourseGoal.code)).all()
    indicators = session.exec(
        select(AbilityIndicator).where(AbilityIndicator.task_id == task.id).order_by(AbilityIndicator.id)
    ).all()
    try:
        evidence = build_sections_evidence(task, projects, goals, indicators)
        sections = generate_outline_sections(config, evidence)
    except OutlineSectionsError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModelProviderError as exc:
        raise HTTPException(status_code=502, detail="AI 生成大纲正文失败，请稍后重试") from exc

    record = stored if stored is not None else OutlineSectionSet(task_id=task.id, payload_json="")
    record.payload_json = json.dumps(sections_to_dict(sections), ensure_ascii=False)
    record.generated_at = datetime.now(timezone.utc)
    session.add(record)
    session.commit()
    return sections


def _course_standard_copies(task_id: int, session: Session) -> tuple[CourseResources, CourseAssessments]:
    """五、学习资源 and 六、考核方式 are copied out of the standard, never written."""
    asset = active_asset(session, task_id, "course_standard")
    if asset is None or not Path(asset.storage_path).exists():
        return CourseResources(), CourseAssessments()
    standard = Document(str(asset.storage_path))
    return read_course_resources(standard), read_course_assessments(standard)


def _split_codes(value: str) -> list[str]:
    return list(
        dict.fromkeys(
            canonical_code(code)
            for code in value.replace("，", " ").replace(",", " ").split()
            if canonical_code(code)
        )
    )


def _validate_outline_code_selection(
    task_id: int,
    goal_value: str,
    ability_value: str,
    session: Session,
) -> None:
    selected_goals = _split_codes(goal_value)
    selected_abilities = _split_codes(ability_value)
    if not selected_goals or not selected_abilities:
        raise HTTPException(status_code=422, detail="课程目标和能力指标至少各选择一项")
    goals = session.exec(select(CourseGoal).where(CourseGoal.task_id == task_id)).all()
    goals_by_code = {canonical_code(goal.code): goal for goal in goals}
    unknown_goals = sorted(set(selected_goals) - set(goals_by_code))
    if unknown_goals:
        raise HTTPException(status_code=422, detail=f"包含未知课程目标：{', '.join(unknown_goals)}")
    allowed_abilities: set[str] = set()
    for goal_code in selected_goals:
        allowed_abilities.update(_split_codes(goals_by_code[goal_code].ability_codes))
    indicator_codes = {
        canonical_code(indicator.code)
        for indicator in session.exec(select(AbilityIndicator).where(AbilityIndicator.task_id == task_id)).all()
    }
    invalid = sorted(set(selected_abilities) - allowed_abilities | (set(selected_abilities) - indicator_codes))
    if invalid:
        raise HTTPException(
            status_code=422,
            detail=f"能力代码与所选课程目标或人才培养方案不匹配：{', '.join(invalid)}",
        )


def _outline_revision_content(row: OutlineRow, field_name: str) -> str:
    if field_name in {"topic", "teaching_content", "teaching_methods"}:
        return str(getattr(row, field_name))
    fields = ["pre_task", "in_class_task", "post_task"] if field_name == "tasks" else [
        "topic",
        "teaching_content",
        "ideological_point",
        "teaching_methods",
        "pre_task",
        "in_class_task",
        "post_task",
    ]
    return json.dumps({field: getattr(row, field) for field in fields}, ensure_ascii=False)


def _apply_outline_revision(row: OutlineRow, field_name: str, proposed_content: str) -> None:
    if field_name in {"topic", "teaching_content", "teaching_methods"}:
        setattr(row, field_name, proposed_content)
        return
    values = json.loads(proposed_content)
    fields = ["pre_task", "in_class_task", "post_task"] if field_name == "tasks" else [
        "topic",
        "teaching_content",
        "ideological_point",
        "teaching_methods",
        "pre_task",
        "in_class_task",
        "post_task",
    ]
    for field in fields:
        setattr(row, field, values[field])


def _get_outline_revision_candidate_or_404(
    task_id: int,
    candidate_id: int,
    session: Session,
) -> OutlineRevisionCandidate:
    candidate = session.get(OutlineRevisionCandidate, candidate_id)
    if candidate is None or candidate.task_id != task_id:
        raise HTTPException(status_code=404, detail="课程实施大纲候选内容不存在")
    return candidate


def _no_sessions_detail(analysis, course_filter: str | None) -> dict:
    """Name the courses the sheet does hold, so the teacher can pick one.

    An empty result almost always means the course record and the registrar
    spell the course differently; the bare 「没有可用课次」 left teachers
    guessing at that.
    """
    names = list(analysis.course_names)
    if names and course_filter:
        message = (
            f"课表里没有和「{course_filter}」对应的课次。"
            f"课表中识别到的课程：{'、'.join(names)}。"
            "可以直接选择其中一门导入，或先把课程名称改成一致后重新上传。"
        )
    elif names:
        message = "课表中没有可用课次，请检查节次列是否为空。"
    else:
        message = "课表中没有可用课次，未识别到任何课程，请确认这是教务系统导出的课表。"
    return {
        "message": message,
        "detected_headers": analysis.detected_headers,
        "missing_fields": [],
        "course_names": names,
    }


def _get_task_or_404(task_id: int, session: Session, current_user: User) -> TeachingTask:
    task = session.get(TeachingTask, task_id)
    if task is None or (current_user.role != "admin" and task.owner_id != current_user.id):
        raise HTTPException(status_code=404, detail="Teaching task not found")
    return task


def _get_outline_row_or_404(task_id: int, outline_row_id: int, session: Session) -> OutlineRow:
    row = session.get(OutlineRow, outline_row_id)
    if row is None or row.task_id != task_id:
        raise HTTPException(status_code=404, detail="Outline row not found")
    return row


def _get_next_outline_row(task_id: int, row: OutlineRow, session: Session) -> OutlineRow | None:
    return session.exec(
        select(OutlineRow)
        .where(OutlineRow.task_id == task_id, OutlineRow.session_no > row.session_no)
        .order_by(OutlineRow.session_no)
    ).first()


def _get_reflection_or_404(
    task_id: int,
    reflection_id: int,
    session: Session,
) -> PostClassReflection:
    reflection = session.get(PostClassReflection, reflection_id)
    if reflection is None or reflection.task_id != task_id:
        raise HTTPException(status_code=404, detail="Post-class reflection not found")
    return reflection


def _get_lesson_by_outline(
    task_id: int,
    outline_row_id: int,
    session: Session,
) -> LessonPlan | None:
    return session.exec(
        select(LessonPlan).where(
            LessonPlan.task_id == task_id,
            LessonPlan.outline_row_id == outline_row_id,
        )
    ).first()


def _get_material_or_404(task_id: int, material_id: int, session: Session) -> SessionMaterial:
    material = session.get(SessionMaterial, material_id)
    if material is None or material.task_id != task_id:
        raise HTTPException(status_code=404, detail="Session material not found")
    return material


def _task_read(task: TeachingTask, session: Session) -> dict:
    task_id = task.id
    assert task_id is not None
    course_goals_count = len(session.exec(select(CourseGoal).where(CourseGoal.task_id == task_id)).all())
    ability_indicators_count = len(
        session.exec(select(AbilityIndicator).where(AbilityIndicator.task_id == task_id)).all()
    )
    sources_confirmed = session.get(SourceConfirmation, task_id) is not None
    schedule_records = session.exec(
        select(ScheduleSessionRecord)
        .where(ScheduleSessionRecord.task_id == task_id)
        .order_by(ScheduleSessionRecord.session_no)
    ).all()
    progress = summarize_course_sessions(schedule_records)
    outline_rows_count = len(session.exec(select(OutlineRow).where(OutlineRow.task_id == task_id)).all())
    lesson_plans_count = len(session.exec(select(LessonPlan).where(LessonPlan.task_id == task_id)).all())
    return {
        "id": task_id,
        "owner_id": task.owner_id,
        "major_id": task.major_id,
        "term": task.term,
        "major": task.major,
        "class_name": task.class_name,
        "course_name": task.course_name,
        "teacher_name": task.teacher_name,
        "location": task.location,
        "total_hours": task.total_hours,
        "hours_per_session": task.hours_per_session,
        "status": task.status,
        "course_standard_uploaded": course_goals_count > 0,
        "talent_plan_uploaded": ability_indicators_count > 0,
        "sources_confirmed": sources_confirmed,
        "schedule_uploaded": bool(schedule_records),
        "outline_template_uploaded": active_asset(session, task_id, "outline_template") is not None or _task_template_path(task_id, "outline").exists(),
        "lesson_template_uploaded": active_asset(session, task_id, "lesson_template") is not None or _task_template_path(task_id, "lesson").exists(),
        "outline_rows_count": outline_rows_count,
        "lesson_plans_count": lesson_plans_count,
        "session_count": progress.session_count,
        "completed_sessions_count": progress.completed_sessions_count,
        "next_session_no": progress.next_session_no,
        "next_session_date": progress.next_session_date,
        "next_session_weekday": progress.next_session_weekday,
        "next_session_periods": progress.next_session_periods,
    }


def _source_review(task_id: int, session: Session) -> SourceReviewRead:
    goals = session.exec(
        select(CourseGoal).where(CourseGoal.task_id == task_id).order_by(CourseGoal.code)
    ).all()
    indicators = session.exec(
        select(AbilityIndicator).where(AbilityIndicator.task_id == task_id).order_by(AbilityIndicator.id)
    ).all()
    review = build_source_review(
        goals,
        indicators,
        confirmed=session.get(SourceConfirmation, task_id) is not None,
    )
    return SourceReviewRead(task_id=task_id, **asdict(review))


async def _save_upload_to_temp(file: UploadFile, suffix: str) -> Path:
    content = await file.read()
    return _save_content_to_temp(content, suffix)


def _save_content_to_temp(content: bytes, suffix: str) -> Path:
    with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(content)
        return Path(temp_file.name)


def _docx_download(content: bytes, filename: str) -> Response:
    return Response(
        content=content,
        media_type=DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


class ResolvedTemplate(NamedTuple):
    path: Path
    filename: str


async def _resolve_template_path(task_id: int, kind: str, file: UploadFile | None, session: Session) -> ResolvedTemplate:
    target_path = _task_template_path(task_id, kind)
    if file is not None:
        content = await file.read()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(content)
        return ResolvedTemplate(target_path, file.filename or target_path.name)
    asset = active_asset(session, task_id, f"{kind}_template")
    if asset is not None and Path(asset.storage_path).exists():
        return ResolvedTemplate(Path(asset.storage_path), asset.original_filename)
    if target_path.exists():
        return ResolvedTemplate(target_path, target_path.name)
    raise HTTPException(status_code=400, detail=f"{kind} template is required")


def _task_template_path(task_id: int, kind: str) -> Path:
    filename = TEMPLATE_FILES.get(kind)
    if filename is None:
        raise HTTPException(status_code=404, detail="Template kind not found")
    return TASK_FILE_DIR / str(task_id) / filename


def _delete_existing(session: Session, model, task_id: int) -> None:
    existing = session.exec(select(model).where(model.task_id == task_id)).all()
    for item in existing:
        session.delete(item)
    session.flush()


def _mark_artifacts_for_review(session: Session, task_id: int, reason: str) -> None:
    artifact_models = {
        "outline": OutlineRow,
        "lesson": LessonPlan,
        "material": SessionMaterial,
    }
    for artifact_type, model in artifact_models.items():
        if session.exec(select(model).where(model.task_id == task_id)).first() is None:
            continue
        existing = session.exec(
            select(CourseReviewNotice).where(
                CourseReviewNotice.task_id == task_id,
                CourseReviewNotice.artifact_type == artifact_type,
                CourseReviewNotice.resolved_at == None,  # noqa: E711
            )
        ).first()
        if existing is None:
            session.add(CourseReviewNotice(task_id=task_id, artifact_type=artifact_type, reason=reason))


def _outline_rows_to_text(rows: list[OutlineRow]) -> str:
    return "\n".join(
        f"第 {row.session_no} 次课 {row.date_text} 周{row.week_no} {row.periods}："
        f"{row.teaching_content}（{row.course_goal_codes} / {row.ability_codes}）"
        for row in rows
    )
