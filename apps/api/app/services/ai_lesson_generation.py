from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Protocol

from docx import Document
from sqlmodel import Session, select

from app.db import engine
from app.models import (
    AbilityIndicator,
    AiModelConfig,
    CourseGoal,
    CourseProject,
    LessonGenerationItem,
    LessonGenerationRun,
    LessonPlan,
    OutlineRow,
    TaskMaterialAsset,
    TeachingTask,
)
from app.services.ai_lesson_validator import LessonValidationError, ValidatedLesson, validate_lesson_payload
from app.services.lesson_evidence import LessonEvidence, LessonEvidenceError, build_lesson_evidence
from app.services.lesson_template_filler import read_process_layout
from app.services.openai_compatible import ModelProviderError, OpenAICompatibleClient


SYSTEM_PROMPT = """你是高职院校教学设计助手。只能使用输入证据中的课程目标和能力代码。
返回一个 JSON 对象，字段必须包括 title、teaching_goals、key_points、difficult_points、
teaching_preparation、process_segments、summary、homework、course_goal_codes、ability_codes。
process_segments 每项必须含 title、minutes、teacher_activity、student_activity、assessment。
若输入中出现 required_segment_minutes，process_segments 必须与之一一对应：环节数量相同，
minutes 按顺序完全相同，不得增减或改变时长。
teaching_goals 必须是 3 到 5 条的数组，每条一个可检验的目标，不要写成一整段。
course_goal_codes 与 ability_codes 也必须是数组，长度与 teaching_goals 相同、按顺序一一对应：
第 i 条目标对应 course_goal_codes[i] 和 ability_codes[i]，各自只写这条目标真正涉及的代码。
teacher_activity、student_activity、assessment 只写课堂上真实发生的事，用教师和学生看得懂的话，
不得出现 M1、1-7-1 这类课程目标或能力指标代码，代码只放在 course_goal_codes 和 ability_codes 字段。
若输入中出现 previous_attempt_error，说明上一次回答被判定不合格，必须针对该问题修正后再返回。"""


class JsonModelClient(Protocol):
    def generate_json(self, system_prompt: str, user_payload: dict) -> dict: ...


ClientFactory = Callable[[AiModelConfig], JsonModelClient]


def create_generation_run(
    session: Session,
    task: TeachingTask,
    initiated_by_id: int,
    rows: list[OutlineRow],
) -> LessonGenerationRun:
    existing_lessons = {
        lesson.outline_row_id: lesson
        for lesson in session.exec(select(LessonPlan).where(LessonPlan.task_id == task.id)).all()
    }
    run = LessonGenerationRun(
        task_id=task.id or 0,
        initiated_by_id=initiated_by_id,
        total_items=len(rows),
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    succeeded = 0
    for row in rows:
        lesson = existing_lessons.get(row.id or 0)
        item = LessonGenerationItem(
            run_id=run.id or 0,
            outline_row_id=row.id or 0,
            lesson_plan_id=lesson.id if lesson else None,
            status="succeeded" if lesson else "pending",
        )
        succeeded += int(lesson is not None)
        session.add(item)
    run.succeeded_items = succeeded
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def _template_segment_minutes(session: Session, task_id: int) -> list[int]:
    """The pacing the uploaded lesson template fixes, or none if it has none."""
    asset = session.exec(
        select(TaskMaterialAsset)
        .where(TaskMaterialAsset.task_id == task_id, TaskMaterialAsset.kind == "lesson_template")
        .order_by(TaskMaterialAsset.updated_at.desc())
    ).first()
    if asset is None:
        return []
    path = Path(asset.storage_path)
    if not path.exists():
        return []
    try:
        return read_process_layout(Document(str(path)))
    except Exception:  # A malformed template must not block generation.
        return []


def _detached_config(config: AiModelConfig) -> AiModelConfig:
    """A plain copy worker threads can read without touching the Session."""
    return AiModelConfig(
        id=config.id,
        base_url=config.base_url,
        model_name=config.model_name,
        encrypted_api_key=config.encrypted_api_key,
        enabled=config.enabled,
        connection_status=config.connection_status,
    )


def _error_code(exc: Exception) -> str:
    if isinstance(exc, ModelProviderError):
        return "provider_error"
    if isinstance(exc, LessonValidationError):
        return "validation_error"
    if isinstance(exc, LessonEvidenceError):
        return "evidence_error"
    return "generation_error"


def _generate_one(
    config: AiModelConfig,
    evidence: LessonEvidence,
    client_factory: ClientFactory,
) -> tuple[ValidatedLesson | None, int, int, str]:
    started = monotonic()
    error_code = ""
    correction = ""
    for attempt in (1, 2):
        try:
            prompt_payload = evidence.to_prompt_payload()
            if correction:
                # Retrying with the identical prompt just reproduces the same
                # answer, so tell the model what it got wrong last time.
                prompt_payload["previous_attempt_error"] = correction
            payload = client_factory(config).generate_json(SYSTEM_PROMPT, prompt_payload)
            lesson = validate_lesson_payload(payload, evidence)
            return lesson, attempt, int((monotonic() - started) * 1000), ""
        except Exception as exc:  # The public result stores only a sanitized category.
            error_code = _error_code(exc)
            # Only our own validation messages describe a fixable output defect.
            correction = str(exc) if isinstance(exc, LessonValidationError) else ""
    return None, 2, int((monotonic() - started) * 1000), error_code


def process_generation_run(
    run_id: int | None,
    client_factory: ClientFactory = OpenAICompatibleClient,
) -> None:
    if run_id is None:
        return
    with Session(engine) as session:
        run = session.get(LessonGenerationRun, run_id)
        if run is None:
            return
        run.status = "running"
        session.add(run)
        session.commit()
        task = session.get(TeachingTask, run.task_id)
        config = session.exec(
            select(AiModelConfig).where(AiModelConfig.enabled == True).order_by(AiModelConfig.id)  # noqa: E712
        ).first()
        items = session.exec(
            select(LessonGenerationItem)
            .where(LessonGenerationItem.run_id == run_id, LessonGenerationItem.status == "pending")
            .order_by(LessonGenerationItem.id)
        ).all()
        rows = session.exec(
            select(OutlineRow).where(OutlineRow.task_id == run.task_id).order_by(OutlineRow.session_no)
        ).all()
        goals = session.exec(select(CourseGoal).where(CourseGoal.task_id == run.task_id)).all()
        indicators = session.exec(select(AbilityIndicator).where(AbilityIndicator.task_id == run.task_id)).all()
        projects = session.exec(
            select(CourseProject).where(CourseProject.task_id == run.task_id).order_by(CourseProject.sequence_no)
        ).all()
        segment_minutes = _template_segment_minutes(session, run.task_id)
        if task is None or config is None:
            for item in items:
                item.status = "failed"
                item.error_code = "configuration_error"
                session.add(item)
            _finish_run(session, run)
            return

        row_index = {row.id: index for index, row in enumerate(rows)}

        # Build every payload and commit before starting any worker. A commit
        # expires ORM instances, so a worker still holding one would trigger a
        # cross-thread refresh on this Session and die in milliseconds.
        pending: list[tuple[int, OutlineRow, LessonEvidence]] = []
        for item in items:
            index = row_index.get(item.outline_row_id)
            if index is None:
                item.status = "failed"
                item.error_code = "evidence_error"
                session.add(item)
                continue
            try:
                evidence = build_lesson_evidence(
                    task,
                    rows[index],
                    goals,
                    indicators,
                    rows[index - 1] if index > 0 else None,
                    rows[index + 1] if index + 1 < len(rows) else None,
                    projects,
                    segment_minutes,
                )
            except LessonEvidenceError:
                item.status = "failed"
                item.error_code = "evidence_error"
                session.add(item)
                continue
            item.status = "running"
            session.add(item)
            pending.append((item.id or 0, rows[index], evidence))
        settings = _detached_config(config)
        row_by_id = {row.id: row for _item_id, row, _evidence in pending}
        session.commit()

        work: dict = {}
        with ThreadPoolExecutor(max_workers=min(2, max(1, len(pending) or 1))) as executor:
            for item_id, row, evidence in pending:
                work[executor.submit(_generate_one, settings, evidence, client_factory)] = (item_id, row)

            for future in as_completed(work):
                item_id, row = work[future]
                lesson_data, attempts, duration_ms, error_code = future.result()
                item = session.get(LessonGenerationItem, item_id)
                if item is None:
                    continue
                item.attempts = attempts
                item.duration_ms = duration_ms
                item.error_code = error_code
                if lesson_data is None:
                    item.status = "failed"
                else:
                    lesson = LessonPlan(
                        task_id=run.task_id,
                        outline_row_id=row.id or 0,
                        session_no=row.session_no,
                        title=lesson_data.title,
                        duration_minutes=lesson_data.duration_minutes,
                        teaching_goals=lesson_data.teaching_goals,
                        key_points=lesson_data.key_points,
                        difficult_points=lesson_data.difficult_points,
                        teaching_preparation=lesson_data.teaching_preparation,
                        teaching_process=lesson_data.teaching_process,
                        summary=lesson_data.summary,
                        homework=lesson_data.homework,
                        course_goal_codes=lesson_data.course_goal_codes,
                        ability_codes=lesson_data.ability_codes,
                        generation_source="ai",
                        review_status="draft",
                    )
                    session.add(lesson)
                    session.commit()
                    session.refresh(lesson)
                    item.lesson_plan_id = lesson.id
                    item.status = "succeeded"
                session.add(item)
                session.commit()
        _finish_run(session, run)


def _finish_run(session: Session, run: LessonGenerationRun) -> None:
    items = session.exec(select(LessonGenerationItem).where(LessonGenerationItem.run_id == run.id)).all()
    run.succeeded_items = sum(item.status == "succeeded" for item in items)
    run.failed_items = sum(item.status == "failed" for item in items)
    if run.failed_items and run.succeeded_items:
        run.status = "completed_with_errors"
    elif run.failed_items:
        run.status = "failed"
    else:
        run.status = "completed"
    run.finished_at = datetime.now(timezone.utc)
    task = session.get(TeachingTask, run.task_id)
    if task is not None:
        task.status = "completed" if run.failed_items == 0 else "lessons_partial"
        session.add(task)
    session.add(run)
    session.commit()
