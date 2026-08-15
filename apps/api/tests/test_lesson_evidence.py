import pytest

from app.models import AbilityIndicator, CourseGoal, CourseProject, OutlineRow, TeachingTask
from app.services.lesson_evidence import LessonEvidenceError, build_lesson_evidence


def _task() -> TeachingTask:
    return TeachingTask(
        term="2026-2027 第一学期",
        major="数字媒体艺术设计",
        class_name="数艺2501",
        course_name="人工智能与创意设计",
        teacher_name="张老师",
        location="智慧教室",
        total_hours=32,
        hours_per_session=4,
    )


def _row() -> OutlineRow:
    return OutlineRow(
        id=11,
        task_id=1,
        session_no=1,
        date_text="2026-09-01",
        week_no=1,
        weekday="周二",
        periods="1-4",
        topic="AIGC创意流程",
        teaching_content="理解AIGC基础与创意设计流程",
        course_goal_codes="M1",
        ability_codes="1-3-4",
    )


def _goals() -> list[CourseGoal]:
    return [CourseGoal(task_id=1, code="M1", description="完成创意设计任务", ability_codes="1-3-4")]


def _indicators() -> list[AbilityIndicator]:
    return [
        AbilityIndicator(
            task_id=1,
            code="1-3-4",
            category="专业能力",
            group_code="1-3",
            description="能够完成创意设计",
        )
    ]


def test_builds_evidence_only_from_codes_in_both_sources():
    evidence = build_lesson_evidence(_task(), _row(), _goals(), _indicators(), None, None)

    assert evidence.allowed_ability_codes == {"1-3-4": "能够完成创意设计"}
    assert evidence.course_goals == {"M1": "完成创意设计任务"}
    assert evidence.duration_minutes == 160
    assert evidence.session_no == 1


def test_rejects_row_ability_code_not_referenced_by_course_standard():
    row = _row()
    row.ability_codes = "1-3-4 2-2-2"
    indicators = _indicators() + [
        AbilityIndicator(task_id=1, code="2-2-2", category="专业能力", group_code="2-2", description="其他能力")
    ]

    with pytest.raises(LessonEvidenceError, match="2-2-2"):
        build_lesson_evidence(_task(), row, _goals(), indicators, None, None)


def test_rejects_course_standard_code_missing_from_talent_plan():
    goals = [CourseGoal(task_id=1, code="M1", description="完成任务", ability_codes="1-3-4 9-9-9")]

    with pytest.raises(LessonEvidenceError, match="9-9-9"):
        build_lesson_evidence(_task(), _row(), goals, _indicators(), None, None)


def test_rejects_conflicting_indicator_definitions_after_code_normalization():
    indicators = _indicators() + [
        AbilityIndicator(task_id=1, code="1－3－4", category="专业能力", group_code="1-3", description="冲突定义")
    ]

    with pytest.raises(LessonEvidenceError, match="定义冲突"):
        build_lesson_evidence(_task(), _row(), _goals(), indicators, None, None)


def _projects() -> list[CourseProject]:
    return [
        CourseProject(
            task_id=1,
            sequence_no=1,
            name="项目一：AIGC 创意实践",
            description="以文创 IP 为线索完成一次完整的 AIGC 创作。",
            teaching_content="文本生成、图像生成与风格控制；Midjourney 与 Stable Diffusion 的提示词写法；成果整理与版权标注。",
            suggested_methods="案例分析 任务驱动 实训",
            course_goal_codes="M1",
            ability_codes="1-3-4",
            reference_hours=16,
            practice_hours=8,
        ),
        CourseProject(
            task_id=1,
            sequence_no=2,
            name="项目二：短视频传播",
            description="不该被选中的项目。",
            teaching_content="剪辑与配音。",
            suggested_methods="实训",
            course_goal_codes="M1",
            ability_codes="1-3-4",
            reference_hours=16,
            practice_hours=8,
        ),
    ]


def test_evidence_carries_the_project_the_session_belongs_to():
    row = _row()
    row.project_name = "项目一：AIGC 创意实践"

    evidence = build_lesson_evidence(_task(), row, _goals(), _indicators(), None, None, _projects())

    assert evidence.project_name == "项目一：AIGC 创意实践"
    assert "Midjourney" in evidence.project_teaching_content
    assert evidence.project_description.startswith("以文创 IP")
    assert evidence.project_suggested_methods == "案例分析 任务驱动 实训"


def test_evidence_omits_project_grounding_when_the_row_has_no_project():
    evidence = build_lesson_evidence(_task(), _row(), _goals(), _indicators(), None, None, _projects())

    assert evidence.project_name == ""
    assert evidence.project_teaching_content == ""


def test_project_grounding_is_optional_so_existing_callers_still_work():
    evidence = build_lesson_evidence(_task(), _row(), _goals(), _indicators(), None, None)

    assert evidence.project_teaching_content == ""
    assert evidence.topic == "AIGC创意流程"
