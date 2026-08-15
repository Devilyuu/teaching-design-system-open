from collections.abc import Sequence
from dataclasses import asdict, dataclass

from app.models import AbilityIndicator, CourseGoal, CourseProject, OutlineRow, TeachingTask


class LessonEvidenceError(ValueError):
    pass


@dataclass(frozen=True)
class LessonEvidence:
    course_name: str
    major: str
    class_name: str
    session_no: int
    date_text: str
    topic: str
    teaching_content: str
    duration_minutes: int
    teaching_methods: str
    pre_task: str
    in_class_task: str
    post_task: str
    ideological_point: str
    course_goals: dict[str, str]
    selected_course_goal_codes: list[str]
    allowed_ability_codes: dict[str, str]
    selected_ability_codes: list[str]
    previous_topic: str
    next_topic: str
    # The course standard's own wording for the project this session belongs to.
    # Without it the model only sees the outline row, which is already a lossy
    # summary of that project.
    project_name: str = ""
    project_description: str = ""
    project_teaching_content: str = ""
    project_suggested_methods: str = ""
    # Minutes the school's template fixes for each 课中 row. When present the
    # model must match this pacing exactly, otherwise rows cannot be filled.
    required_segment_minutes: tuple[int, ...] = ()

    def to_prompt_payload(self) -> dict:
        return asdict(self)


def canonical_code(value: str) -> str:
    return value.strip().replace("－", "-").replace("—", "-")


def _codes(value: str) -> list[str]:
    return list(dict.fromkeys(canonical_code(code) for code in value.split() if canonical_code(code)))


def _unique_definitions(items: list[tuple[str, str]], source_name: str) -> dict[str, str]:
    definitions: dict[str, str] = {}
    for raw_code, description in items:
        code = canonical_code(raw_code)
        if not code:
            continue
        if code in definitions and definitions[code].strip() != description.strip():
            raise LessonEvidenceError(f"{source_name}中的能力代码 {code} 定义冲突")
        definitions[code] = description.strip()
    return definitions


def build_lesson_evidence(
    task: TeachingTask,
    row: OutlineRow,
    goals: list[CourseGoal],
    indicators: list[AbilityIndicator],
    previous_row: OutlineRow | None,
    next_row: OutlineRow | None,
    projects: list[CourseProject] | None = None,
    required_segment_minutes: Sequence[int] = (),
) -> LessonEvidence:
    if not goals or not indicators:
        raise LessonEvidenceError("课程标准和人才培养方案必须先完成解析与确认")

    goal_definitions: dict[str, str] = {}
    standard_ability_codes: set[str] = set()
    for goal in goals:
        code = canonical_code(goal.code)
        if code in goal_definitions and goal_definitions[code].strip() != goal.description.strip():
            raise LessonEvidenceError(f"课程目标代码 {code} 定义冲突")
        goal_definitions[code] = goal.description.strip()
        standard_ability_codes.update(_codes(goal.ability_codes))

    indicator_definitions = _unique_definitions(
        [(indicator.code, indicator.description) for indicator in indicators],
        "人才培养方案",
    )
    missing_from_plan = standard_ability_codes - set(indicator_definitions)
    if missing_from_plan:
        raise LessonEvidenceError(
            f"课程标准中的能力代码未在人才培养方案中找到：{', '.join(sorted(missing_from_plan))}"
        )

    allowed_ability_codes = {
        code: indicator_definitions[code]
        for code in sorted(standard_ability_codes)
    }
    selected_goal_codes = _codes(row.course_goal_codes)
    unknown_goal_codes = set(selected_goal_codes) - set(goal_definitions)
    if unknown_goal_codes:
        raise LessonEvidenceError(f"课次引用了未知课程目标：{', '.join(sorted(unknown_goal_codes))}")

    selected_ability_codes = _codes(row.ability_codes)
    disallowed_ability_codes = set(selected_ability_codes) - set(allowed_ability_codes)
    if disallowed_ability_codes:
        raise LessonEvidenceError(
            f"课次能力代码未同时通过课程标准与人才培养方案校验：{', '.join(sorted(disallowed_ability_codes))}"
        )

    return LessonEvidence(
        course_name=task.course_name,
        major=task.major,
        class_name=task.class_name,
        session_no=row.session_no,
        date_text=row.date_text,
        topic=row.topic,
        teaching_content=row.teaching_content,
        duration_minutes=task.hours_per_session * 40,
        teaching_methods=row.teaching_methods,
        pre_task=row.pre_task,
        in_class_task=row.in_class_task,
        post_task=row.post_task,
        ideological_point=row.ideological_point,
        course_goals={code: goal_definitions[code] for code in selected_goal_codes},
        selected_course_goal_codes=selected_goal_codes,
        allowed_ability_codes=allowed_ability_codes,
        selected_ability_codes=selected_ability_codes,
        previous_topic=previous_row.topic if previous_row else "",
        next_topic=next_row.topic if next_row else "",
        required_segment_minutes=tuple(required_segment_minutes),
        **_project_grounding(row, projects or []),
    )


def _project_grounding(row: OutlineRow, projects: list[CourseProject]) -> dict[str, str]:
    wanted = getattr(row, "project_name", "").strip()
    if not wanted:
        return {}
    project = next((item for item in projects if item.name.strip() == wanted), None)
    if project is None:
        return {}
    return {
        "project_name": project.name.strip(),
        "project_description": project.description.strip(),
        "project_teaching_content": project.teaching_content.strip(),
        "project_suggested_methods": project.suggested_methods.strip(),
    }
