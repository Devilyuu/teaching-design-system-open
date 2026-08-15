from dataclasses import asdict, dataclass

from pydantic import BaseModel, Field, ValidationError

from app.models import AiModelConfig
from app.services.lesson_evidence import canonical_code
from app.services.openai_compatible import OpenAICompatibleClient
from app.services.outline_generator import GeneratedOutlineRow


SYSTEM_PROMPT = """你是高职院校课程实施大纲设计助手。根据课程项目和课次数量拆分整门课程，返回一个 JSON 对象，唯一顶层字段为 rows。不得修改课表，不得编造课程目标或能力指标代码。每行必须包含 session_no、project_name、topic、teaching_content、ideological_point、teaching_methods、pre_task、in_class_task、post_task、course_goal_codes、ability_codes。
teaching_content 只写一到两行标题式概括，点明本次课做什么，不超过 40 字，不要罗列步骤或分条细节。
in_class_task 只写一行本次课的核心任务或学生要交的作业，不超过 30 字，必须与同一行的 teaching_content 对应。
sessions 给出每次课的 hours，各次课学时可能不同。分配到同一个 project_name 的各次课 hours 之和，
必须精确等于该项目的 reference_hours，不得多也不得少。
若输入中出现 previous_attempt_error，说明上一次分配不合格，必须据此重新分配后再返回。"""


class OutlineEvidenceError(ValueError):
    pass


class OutlineValidationError(ValueError):
    pass


@dataclass(frozen=True)
class OutlineEvidence:
    course_name: str
    total_hours: int
    hours_per_session: int
    projects: list[dict]
    goals: dict[str, dict]
    sessions: list[dict]

    def to_prompt_payload(self) -> dict:
        payload = asdict(self)
        payload["sessions"] = [
            {"session_no": session["session_no"], "hours": session["hours"]}
            for session in self.sessions
        ]
        return payload


class AiOutlineRow(BaseModel):
    session_no: int = Field(gt=0, le=100)
    project_name: str = Field(min_length=1, max_length=500)
    topic: str = Field(min_length=1, max_length=500)
    teaching_content: str = Field(min_length=1, max_length=10000)
    ideological_point: str = Field(min_length=1, max_length=5000)
    teaching_methods: str = Field(min_length=1, max_length=5000)
    pre_task: str = Field(min_length=1, max_length=5000)
    in_class_task: str = Field(min_length=1, max_length=5000)
    post_task: str = Field(min_length=1, max_length=5000)
    course_goal_codes: list[str] = Field(min_length=1)
    ability_codes: list[str] = Field(min_length=1)


class AiOutlinePayload(BaseModel):
    rows: list[AiOutlineRow] = Field(min_length=1, max_length=100)


def _codes(value: str | list[str]) -> list[str]:
    values = value if isinstance(value, list) else value.replace("，", " ").replace(",", " ").split()
    return list(dict.fromkeys(canonical_code(item) for item in values if canonical_code(item)))


def build_outline_evidence(task, projects, goals, indicators, sessions) -> OutlineEvidence:
    schedule_hours = sum(session.hours for session in sessions)
    if schedule_hours != task.total_hours:
        raise OutlineEvidenceError(
            f"课表总学时为 {schedule_hours}，课程总学时为 {task.total_hours}，请先核对"
        )
    if not projects:
        raise OutlineEvidenceError("课程标准中没有可拆分的教学项目")
    project_hours = sum(project.reference_hours for project in projects)
    if project_hours != task.total_hours:
        raise OutlineEvidenceError(
            f"课程项目参考总学时为 {project_hours}，课程总学时为 {task.total_hours}，请先核对"
        )

    indicator_definitions = {indicator.code: indicator.description for indicator in indicators}
    goal_definitions: dict[str, dict] = {}
    for goal in goals:
        ability_codes = _codes(goal.ability_codes)
        goal_definitions[goal.code] = {
            "description": goal.description,
            "abilities": {
                code: indicator_definitions[code]
                for code in ability_codes
                if code in indicator_definitions
            },
        }

    project_payload = [
        {
            "name": project.name,
            "description": project.description,
            "teaching_content": project.teaching_content,
            "suggested_methods": project.suggested_methods,
            "course_goal_codes": _codes(project.course_goal_codes),
            "ability_codes": _codes(project.ability_codes),
            "reference_hours": project.reference_hours,
            "practice_hours": project.practice_hours,
        }
        for project in projects
    ]
    session_payload = [
        {
            "session_no": session.session_no,
            "week_no": session.week_no,
            "date_text": session.date_text,
            "weekday": session.weekday,
            "periods": session.periods,
            "hours": session.hours,
        }
        for session in sessions
    ]
    return OutlineEvidence(
        course_name=task.course_name,
        total_hours=task.total_hours,
        hours_per_session=task.hours_per_session,
        projects=project_payload,
        goals=goal_definitions,
        sessions=session_payload,
    )


def _validate_session_numbers(rows: list[AiOutlineRow], expected_count: int) -> None:
    if len(rows) != expected_count:
        raise OutlineValidationError(f"AI 返回的课次数量必须为 {expected_count}，当前为 {len(rows)}")
    numbers = sorted(row.session_no for row in rows)
    if numbers != list(range(1, expected_count + 1)):
        raise OutlineValidationError("课次编号必须从 1 开始连续且不得重复")


def _validate_projects(rows: list[AiOutlineRow], evidence: OutlineEvidence) -> None:
    project_by_name = {project["name"]: project for project in evidence.projects}
    unknown = sorted({row.project_name for row in rows} - set(project_by_name))
    if unknown:
        raise OutlineValidationError(f"AI 返回了未知课程项目：{', '.join(unknown)}")
    # Compare hours, not session counts: a real timetable mixes four-period and
    # eight-period sessions, so "reference_hours // hours_per_session" would
    # demand more sessions than the schedule actually has.
    hours_by_session = {session["session_no"]: session["hours"] for session in evidence.sessions}
    mismatches: list[str] = []
    for name, project in project_by_name.items():
        actual_hours = sum(
            hours_by_session.get(row.session_no, evidence.hours_per_session)
            for row in rows
            if row.project_name == name
        )
        expected_hours = project["reference_hours"]
        if actual_hours != expected_hours:
            mismatches.append(f"{name} 应分配 {expected_hours} 学时，当前为 {actual_hours} 学时")
    if mismatches:
        raise OutlineValidationError("；".join(mismatches))


def _validate_codes(row: AiOutlineRow, evidence: OutlineEvidence) -> tuple[list[str], list[str]]:
    goal_codes = _codes(row.course_goal_codes)
    unknown_goals = sorted(set(goal_codes) - set(evidence.goals))
    if unknown_goals:
        raise OutlineValidationError(f"第 {row.session_no} 次课包含未知课程目标：{', '.join(unknown_goals)}")
    allowed_abilities: set[str] = set()
    for goal_code in goal_codes:
        allowed_abilities.update(evidence.goals[goal_code]["abilities"])
    ability_codes = _codes(row.ability_codes)
    invalid_abilities = sorted(set(ability_codes) - allowed_abilities)
    if invalid_abilities:
        raise OutlineValidationError(
            f"第 {row.session_no} 次课的能力代码与所选课程目标不匹配：{', '.join(invalid_abilities)}"
        )
    return goal_codes, ability_codes


def validate_outline_payload(payload: dict, evidence: OutlineEvidence) -> list[GeneratedOutlineRow]:
    try:
        parsed = AiOutlinePayload.model_validate(payload)
    except ValidationError as exc:
        raise OutlineValidationError("AI 返回的课程实施大纲结构不完整或字段格式错误") from exc
    _validate_session_numbers(parsed.rows, len(evidence.sessions))
    _validate_projects(parsed.rows, evidence)

    generated: list[GeneratedOutlineRow] = []
    for row in sorted(parsed.rows, key=lambda item: item.session_no):
        goal_codes, ability_codes = _validate_codes(row, evidence)
        schedule = evidence.sessions[row.session_no - 1]
        generated.append(
            GeneratedOutlineRow(
                session_no=row.session_no,
                date_text=schedule["date_text"],
                week_no=schedule["week_no"],
                weekday=schedule["weekday"],
                periods=schedule["periods"],
                topic=row.topic.strip(),
                teaching_content=row.teaching_content.strip(),
                ideological_point=row.ideological_point.strip(),
                teaching_methods=row.teaching_methods.strip(),
                pre_task=row.pre_task.strip(),
                in_class_task=row.in_class_task.strip(),
                post_task=row.post_task.strip(),
                course_goal_codes=" ".join(goal_codes),
                ability_codes=" ".join(ability_codes),
                project_name=row.project_name.strip(),
            )
        )
    return generated


def generate_ai_outline(
    config: AiModelConfig,
    evidence: OutlineEvidence,
    client_factory=OpenAICompatibleClient,
    attempts: int = 3,
) -> list[GeneratedOutlineRow]:
    """Retry with the validation message: splitting sessions of mixed length so
    each project gets its exact hours is a constraint the model rarely nails
    first time, and a byte-identical prompt just reproduces the same answer."""
    correction = ""
    last: OutlineValidationError | None = None
    for _ in range(max(1, attempts)):
        prompt_payload = evidence.to_prompt_payload()
        if correction:
            prompt_payload["previous_attempt_error"] = correction
        payload = client_factory(config).generate_json(SYSTEM_PROMPT, prompt_payload)
        try:
            return validate_outline_payload(payload, evidence)
        except OutlineValidationError as exc:
            last = exc
            correction = str(exc)
    raise last if last is not None else OutlineValidationError("课程实施大纲生成失败")
