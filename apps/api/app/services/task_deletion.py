"""Remove a teaching task together with everything that hangs off it.

The tables carry no database-level cascade (SQLite installs never had it, and
the PostgreSQL path shares the same models), so the walk over dependent rows
lives here rather than being repeated by whichever route needs it.
"""

from pathlib import Path
import shutil

from sqlmodel import Session, select

from app.models import (
    AbilityIndicator,
    CourseGoal,
    CourseProject,
    CourseReviewNotice,
    ExportRecord,
    LessonGenerationItem,
    LessonGenerationRun,
    LessonPlan,
    LessonRevisionCandidate,
    OutlineRevisionCandidate,
    OutlineRow,
    OutlineSectionSet,
    PostClassReflection,
    ScheduleCandidateSession,
    ScheduleImportCandidate,
    ScheduleSessionRecord,
    SessionMaterial,
    SourceConfirmation,
    TaskMaterialAsset,
    TeachingTask,
)

# Rows that point at the task directly. Order does not matter without foreign
# keys, but keeping the list explicit means a new table has to be added here
# on purpose rather than being silently orphaned.
TASK_OWNED_MODELS = (
    CourseGoal,
    CourseProject,
    AbilityIndicator,
    ScheduleSessionRecord,
    TaskMaterialAsset,
    ExportRecord,
    CourseReviewNotice,
    OutlineRow,
    LessonPlan,
    SessionMaterial,
    PostClassReflection,
    OutlineRevisionCandidate,
)


def delete_teaching_task(session: Session, task: TeachingTask, file_root: Path) -> None:
    """Delete the task's rows, commit, then drop its files.

    Files go last and only after the commit: a half-deleted directory next to
    a still-existing task would be worse than a few orphaned files.
    """
    task_id = task.id
    assert task_id is not None

    candidates = session.exec(
        select(ScheduleImportCandidate).where(ScheduleImportCandidate.task_id == task_id)
    ).all()
    for candidate in candidates:
        _delete_where(session, ScheduleCandidateSession, ScheduleCandidateSession.candidate_id == candidate.id)
        session.delete(candidate)

    runs = session.exec(select(LessonGenerationRun).where(LessonGenerationRun.task_id == task_id)).all()
    for run in runs:
        _delete_where(session, LessonGenerationItem, LessonGenerationItem.run_id == run.id)
        session.delete(run)

    plans = session.exec(select(LessonPlan).where(LessonPlan.task_id == task_id)).all()
    for plan in plans:
        _delete_where(session, LessonRevisionCandidate, LessonRevisionCandidate.lesson_plan_id == plan.id)

    for model in TASK_OWNED_MODELS:
        _delete_where(session, model, model.task_id == task_id)

    for keyed_by_task in (SourceConfirmation, OutlineSectionSet):
        row = session.get(keyed_by_task, task_id)
        if row is not None:
            session.delete(row)

    session.delete(task)
    session.commit()

    shutil.rmtree(file_root / str(task_id), ignore_errors=True)


def _delete_where(session: Session, model, condition) -> None:
    for item in session.exec(select(model).where(condition)).all():
        session.delete(item)
