from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session, select

from app.auth import get_current_user
from app.db import get_session
from app.models import (
    AiModelConfig,
    LessonGenerationItem,
    LessonGenerationRun,
    LessonPlan,
    LessonRevisionCandidate,
    AbilityIndicator,
    CourseGoal,
    OutlineRow,
    SourceConfirmation,
    TeachingTask,
    User,
)
from app.schemas import (
    LessonGenerationItemRead,
    LessonGenerationRunRead,
    LessonRevisionCandidateRead,
    LessonRevisionRequest,
)
from app.services.ai_lesson_generation import create_generation_run, process_generation_run
from app.services.lesson_evidence import LessonEvidenceError, build_lesson_evidence
from app.services.lesson_revision import LessonRevisionError, generate_revision_candidate_text
from app.services.openai_compatible import ModelProviderError


router = APIRouter(prefix="/tasks", tags=["lesson-ai"])


def _task_or_404(task_id: int, session: Session, user: User) -> TeachingTask:
    task = session.get(TeachingTask, task_id)
    if task is None or (user.role != "admin" and task.owner_id != user.id):
        raise HTTPException(status_code=404, detail="Teaching task not found")
    return task


def _run_or_404(task_id: int, run_id: int, session: Session) -> LessonGenerationRun:
    run = session.get(LessonGenerationRun, run_id)
    if run is None or run.task_id != task_id:
        raise HTTPException(status_code=404, detail="Lesson generation run not found")
    return run


def _run_read(run: LessonGenerationRun, session: Session) -> LessonGenerationRunRead:
    items = session.exec(
        select(LessonGenerationItem)
        .where(LessonGenerationItem.run_id == run.id)
        .order_by(LessonGenerationItem.id)
    ).all()
    # 进度从 items 现场数，不读 run 上那两个汇总字段。
    #
    # `_finish_run()` 只在整批跑完之后写一次它们，而 20 次课要跑五六分钟——读汇总值
    # 的话，这五六分钟里界面一直显示 0/20，最后一瞬间跳到 20/20，**看上去和卡死
    # 一模一样**（2026-08-11 老师就是这么以为的，那时 18 份教案其实已经落库了）。
    #
    # 每条 item 的状态本来就是逐条提交的，而且这批行上面已经查出来了，不多一次查询。
    succeeded = sum(item.status == "succeeded" for item in items)
    failed = sum(item.status == "failed" for item in items)
    return LessonGenerationRunRead(
        id=run.id or 0,
        task_id=run.task_id,
        status=run.status,
        total_items=run.total_items,
        succeeded_items=succeeded,
        failed_items=failed,
        created_at=run.created_at,
        finished_at=run.finished_at,
        items=[LessonGenerationItemRead.model_validate(item, from_attributes=True) for item in items],
    )


@router.post("/{task_id}/lesson-generation-runs", response_model=LessonGenerationRunRead)
def start_lesson_generation_run(
    task_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> LessonGenerationRunRead:
    task = _task_or_404(task_id, session, current_user)
    if session.get(SourceConfirmation, task_id) is None:
        raise HTTPException(status_code=409, detail="请先确认课程标准与人才培养方案的对应关系")
    config = session.exec(
        select(AiModelConfig).where(
            AiModelConfig.enabled == True,  # noqa: E712
            AiModelConfig.connection_status == "connected",
        )
    ).first()
    if config is None:
        raise HTTPException(status_code=409, detail="AI 模型尚未配置、测试并启用，请联系管理员")
    active = session.exec(
        select(LessonGenerationRun).where(
            LessonGenerationRun.task_id == task_id,
            LessonGenerationRun.status.in_(["pending", "running"]),  # type: ignore[union-attr]
        )
    ).first()
    if active is not None:
        raise HTTPException(status_code=409, detail="该课程已有正在进行的教案生成任务")
    rows = session.exec(
        select(OutlineRow).where(OutlineRow.task_id == task_id).order_by(OutlineRow.session_no)
    ).all()
    if not rows:
        raise HTTPException(status_code=409, detail="请先生成并确认课程实施大纲")
    run = create_generation_run(session, task, current_user.id or 0, rows)
    background_tasks.add_task(process_generation_run, run.id)
    return _run_read(run, session)


@router.get("/{task_id}/lesson-generation-runs/{run_id}", response_model=LessonGenerationRunRead)
def get_lesson_generation_run(
    task_id: int,
    run_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> LessonGenerationRunRead:
    _task_or_404(task_id, session, current_user)
    return _run_read(_run_or_404(task_id, run_id, session), session)


@router.post(
    "/{task_id}/lesson-generation-runs/{run_id}/items/{item_id}/retry",
    response_model=LessonGenerationRunRead,
)
def retry_lesson_generation_item(
    task_id: int,
    run_id: int,
    item_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> LessonGenerationRunRead:
    _task_or_404(task_id, session, current_user)
    run = _run_or_404(task_id, run_id, session)
    item = session.get(LessonGenerationItem, item_id)
    if item is None or item.run_id != run_id:
        raise HTTPException(status_code=404, detail="Lesson generation item not found")
    if item.status != "failed":
        raise HTTPException(status_code=409, detail="只能重试失败的课次")
    item.status = "pending"
    item.attempts = 0
    item.duration_ms = 0
    item.error_code = ""
    run.status = "pending"
    run.finished_at = None
    session.add(item)
    session.add(run)
    session.commit()
    background_tasks.add_task(process_generation_run, run.id)
    session.refresh(run)
    return _run_read(run, session)


def _candidate_read(candidate: LessonRevisionCandidate) -> LessonRevisionCandidateRead:
    return LessonRevisionCandidateRead.model_validate(candidate, from_attributes=True)


def _lesson_or_404(task_id: int, lesson_id: int, session: Session) -> LessonPlan:
    lesson = session.get(LessonPlan, lesson_id)
    if lesson is None or lesson.task_id != task_id:
        raise HTTPException(status_code=404, detail="Lesson plan not found")
    return lesson


@router.post(
    "/{task_id}/lessons/{lesson_id}/revision-candidates",
    response_model=LessonRevisionCandidateRead,
)
def create_lesson_revision_candidate(
    task_id: int,
    lesson_id: int,
    payload: LessonRevisionRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> LessonRevisionCandidateRead:
    task = _task_or_404(task_id, session, current_user)
    lesson = _lesson_or_404(task_id, lesson_id, session)
    row = session.get(OutlineRow, lesson.outline_row_id)
    if row is None:
        raise HTTPException(status_code=409, detail="教案缺少对应的课程实施大纲课次")
    rows = session.exec(
        select(OutlineRow).where(OutlineRow.task_id == task_id).order_by(OutlineRow.session_no)
    ).all()
    row_index = next((index for index, item in enumerate(rows) if item.id == row.id), None)
    if row_index is None:
        raise HTTPException(status_code=409, detail="无法定位课程实施大纲课次")
    goals = session.exec(select(CourseGoal).where(CourseGoal.task_id == task_id)).all()
    indicators = session.exec(select(AbilityIndicator).where(AbilityIndicator.task_id == task_id)).all()
    config = session.exec(
        select(AiModelConfig).where(
            AiModelConfig.enabled == True,  # noqa: E712
            AiModelConfig.connection_status == "connected",
        )
    ).first()
    if config is None:
        raise HTTPException(status_code=409, detail="AI 模型尚未启用")
    try:
        evidence = build_lesson_evidence(
            task,
            row,
            goals,
            indicators,
            rows[row_index - 1] if row_index > 0 else None,
            rows[row_index + 1] if row_index + 1 < len(rows) else None,
        )
        current_content = str(getattr(lesson, payload.field_name))
        proposed = generate_revision_candidate_text(
            config,
            evidence,
            payload.field_name,
            current_content,
            payload.instruction.strip(),
        )
    except (LessonEvidenceError, LessonRevisionError, ModelProviderError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    candidate = LessonRevisionCandidate(
        lesson_plan_id=lesson.id or 0,
        field_name=payload.field_name,
        original_content=current_content,
        proposed_content=proposed,
        teacher_instruction=payload.instruction.strip(),
        created_by_id=current_user.id or 0,
    )
    session.add(candidate)
    session.commit()
    session.refresh(candidate)
    return _candidate_read(candidate)


def _candidate_or_404(task_id: int, candidate_id: int, session: Session) -> tuple[LessonRevisionCandidate, LessonPlan]:
    candidate = session.get(LessonRevisionCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Lesson revision candidate not found")
    lesson = _lesson_or_404(task_id, candidate.lesson_plan_id, session)
    return candidate, lesson


@router.post(
    "/{task_id}/lesson-revision-candidates/{candidate_id}/accept",
    response_model=LessonRevisionCandidateRead,
)
def accept_lesson_revision_candidate(
    task_id: int,
    candidate_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> LessonRevisionCandidateRead:
    _task_or_404(task_id, session, current_user)
    candidate, lesson = _candidate_or_404(task_id, candidate_id, session)
    if candidate.status != "pending":
        raise HTTPException(status_code=409, detail="候选内容已经处理")
    if str(getattr(lesson, candidate.field_name)) != candidate.original_content:
        raise HTTPException(status_code=409, detail="原教案已被修改，请重新生成候选内容")
    setattr(lesson, candidate.field_name, candidate.proposed_content)
    lesson.review_status = "reviewed"
    candidate.status = "accepted"
    session.add(lesson)
    session.add(candidate)
    session.commit()
    session.refresh(candidate)
    return _candidate_read(candidate)


@router.post(
    "/{task_id}/lesson-revision-candidates/{candidate_id}/reject",
    response_model=LessonRevisionCandidateRead,
)
def reject_lesson_revision_candidate(
    task_id: int,
    candidate_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> LessonRevisionCandidateRead:
    _task_or_404(task_id, session, current_user)
    candidate, _ = _candidate_or_404(task_id, candidate_id, session)
    if candidate.status != "pending":
        raise HTTPException(status_code=409, detail="候选内容已经处理")
    candidate.status = "rejected"
    session.add(candidate)
    session.commit()
    session.refresh(candidate)
    return _candidate_read(candidate)
