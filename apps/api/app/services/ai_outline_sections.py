"""Generate the prose and tables of the outline that are not the schedule.

The schedule was the only generated part; the rest of the document came through
from whatever template was uploaded. This writes 课程介绍, 预期学习成果,
学习内容's 重点/难点, 学习方法 and 学习要求.

Three things deliberately are **not** generated:

- 学习内容表's first four columns. The course standard already states each
  project's name, content, suggested methods and reference hours -- asking the
  model to write them again invites it to drift from the document the hours are
  checked against. Only 教学重点/难点 is written here.
- 五、学习资源. Book titles and platform addresses are fact, and a model states
  them fluently and wrongly. See `course_standard_resources`.
- 六、考核方式. The standard states the assessment split outright and it is the
  split the 教务 record checks; it is copied across, merges and 合计 row
  included. See `course_standard_assessment`.
"""

from dataclasses import asdict, dataclass

from pydantic import BaseModel, Field, ValidationError

from app.models import AiModelConfig
from app.services.openai_compatible import OpenAICompatibleClient


SYSTEM_PROMPT = """你是高职院校课程实施大纲撰写助手。依据给定的课程标准信息，返回一个 JSON 对象，字段如下：
course_summary（课程简介，150-400 字，写这门课学什么、怎么学、学完能做什么）
teaching_strategy（教学策略，一行，列出采用的教学模式，不超过 80 字）
prerequisites（先修要求，一行，列出先修课程或应具备的基础，不超过 80 字）
learning_outcomes（预期学习成果，3-8 条，每条以「动词+对象」开头，写学生学完能做到什么，每条不超过 60 字）
unit_key_points（每个教学单元的重点难点，键必须是给定的 unit_names 里的名称，值形如「重点：xxx\\n难点：yyy」）
study_advice（学习方法和学时建议，100-300 字）
academic_integrity（学术诚信规定，一行）
attendance（出勤和缺课补习规定，一行）
classroom_discipline（课堂纪律与礼仪，一到三句）
assignment_requirements（学习任务和作业要求，一到三句）

硬性要求：
- unit_key_points 的键必须与 unit_names 完全一致，不多不少，不得改写名称。
- 只依据给定信息撰写，不得编造教材、文献、网址、企业名或数据。
- 若输入中出现 previous_attempt_error，说明上一次不合格，必须据此修正后重新返回。"""


class OutlineSectionsError(ValueError):
    pass


@dataclass(frozen=True)
class OutlineSectionsEvidence:
    course_name: str
    total_hours: int
    unit_names: list[str]
    projects: list[dict]
    goals: dict[str, dict]

    def to_prompt_payload(self) -> dict:
        return {
            "course_name": self.course_name,
            "total_hours": self.total_hours,
            "unit_names": self.unit_names,
            "projects": self.projects,
            "goals": self.goals,
        }


class AiOutlineSectionsPayload(BaseModel):
    course_summary: str = Field(min_length=1, max_length=4000)
    teaching_strategy: str = Field(min_length=1, max_length=500)
    prerequisites: str = Field(min_length=1, max_length=500)
    learning_outcomes: list[str] = Field(min_length=1, max_length=12)
    unit_key_points: dict[str, str]
    study_advice: str = Field(min_length=1, max_length=3000)
    academic_integrity: str = Field(min_length=1, max_length=1000)
    attendance: str = Field(min_length=1, max_length=1000)
    classroom_discipline: str = Field(min_length=1, max_length=2000)
    assignment_requirements: str = Field(min_length=1, max_length=2000)


@dataclass(frozen=True)
class LearningUnit:
    name: str
    teaching_content: str
    teaching_methods: str
    key_points: str
    hours: int


@dataclass(frozen=True)
class OutlineSections:
    course_summary: str
    teaching_strategy: str
    prerequisites: str
    learning_outcomes: list[str]
    learning_units: list[LearningUnit]
    study_advice: str
    academic_integrity: str
    attendance: str
    classroom_discipline: str
    assignment_requirements: str


def sections_to_dict(sections: OutlineSections) -> dict:
    return asdict(sections)


def sections_from_dict(payload: dict) -> OutlineSections:
    """Read back what `sections_to_dict` stored.

    A stored set that no longer parses is treated as absent by the caller: the
    export regenerates rather than shipping half an outline.
    """
    return OutlineSections(
        course_summary=str(payload["course_summary"]),
        teaching_strategy=str(payload["teaching_strategy"]),
        prerequisites=str(payload["prerequisites"]),
        learning_outcomes=[str(item) for item in payload["learning_outcomes"]],
        learning_units=[LearningUnit(**unit) for unit in payload["learning_units"]],
        study_advice=str(payload["study_advice"]),
        academic_integrity=str(payload["academic_integrity"]),
        attendance=str(payload["attendance"]),
        classroom_discipline=str(payload["classroom_discipline"]),
        assignment_requirements=str(payload["assignment_requirements"]),
    )


def build_sections_evidence(task, projects, goals, indicators) -> OutlineSectionsEvidence:
    if not projects:
        raise OutlineSectionsError("课程标准中没有可用的教学项目，无法撰写学习内容")
    indicator_definitions = {indicator.code: indicator.description for indicator in indicators}
    goal_definitions = {
        goal.code: {
            "description": goal.description,
            "abilities": [
                indicator_definitions[code]
                for code in str(goal.ability_codes or "").replace("，", " ").replace(",", " ").split()
                if code in indicator_definitions
            ],
        }
        for goal in goals
    }
    project_payload = [
        {
            "name": project.name,
            "description": project.description,
            "teaching_content": project.teaching_content,
            "suggested_methods": project.suggested_methods,
            "reference_hours": project.reference_hours,
        }
        for project in projects
    ]
    return OutlineSectionsEvidence(
        course_name=task.course_name,
        total_hours=task.total_hours,
        unit_names=[project.name for project in projects],
        projects=project_payload,
        goals=goal_definitions,
    )


def validate_sections_payload(payload: dict, evidence: OutlineSectionsEvidence) -> OutlineSections:
    try:
        parsed = AiOutlineSectionsPayload.model_validate(payload)
    except ValidationError as exc:
        raise OutlineSectionsError("AI 返回的大纲正文结构不完整或字段格式错误") from exc

    wanted = list(evidence.unit_names)
    returned = list(parsed.unit_key_points)
    missing = [name for name in wanted if name not in returned]
    extra = [name for name in returned if name not in wanted]
    if missing or extra:
        detail = []
        if missing:
            detail.append(f"缺少教学单元：{'、'.join(missing)}")
        if extra:
            detail.append(f"多出未知教学单元：{'、'.join(extra)}")
        raise OutlineSectionsError("；".join(detail))

    by_name = {project["name"]: project for project in evidence.projects}
    units = [
        LearningUnit(
            name=name,
            # The standard states these; the model only writes 重点/难点.
            teaching_content=str(by_name[name].get("teaching_content") or "").strip(),
            teaching_methods=str(by_name[name].get("suggested_methods") or "").strip(),
            key_points=parsed.unit_key_points[name].strip(),
            hours=int(by_name[name].get("reference_hours") or 0),
        )
        for name in wanted
    ]
    unit_hours = sum(unit.hours for unit in units)
    if unit_hours != evidence.total_hours:
        raise OutlineSectionsError(
            f"学习内容各单元参考课时之和为 {unit_hours}，课程总学时为 {evidence.total_hours}，请先核对课程标准"
        )

    return OutlineSections(
        course_summary=parsed.course_summary.strip(),
        teaching_strategy=parsed.teaching_strategy.strip(),
        prerequisites=parsed.prerequisites.strip(),
        learning_outcomes=[item.strip() for item in parsed.learning_outcomes if item.strip()],
        learning_units=units,
        study_advice=parsed.study_advice.strip(),
        academic_integrity=parsed.academic_integrity.strip(),
        attendance=parsed.attendance.strip(),
        classroom_discipline=parsed.classroom_discipline.strip(),
        assignment_requirements=parsed.assignment_requirements.strip(),
    )


def generate_outline_sections(
    config: AiModelConfig,
    evidence: OutlineSectionsEvidence,
    client_factory=OpenAICompatibleClient,
    attempts: int = 3,
) -> OutlineSections:
    """Retry with the validation message, as the schedule generator does.

    A key per teaching unit, named exactly as the standard names it, is what the
    model misses, and that is worth stating back to it rather than failing the
    export.
    """
    correction = ""
    last: OutlineSectionsError | None = None
    for _ in range(max(1, attempts)):
        prompt_payload = evidence.to_prompt_payload()
        if correction:
            prompt_payload["previous_attempt_error"] = correction
        payload = client_factory(config).generate_json(SYSTEM_PROMPT, prompt_payload)
        try:
            return validate_sections_payload(payload, evidence)
        except OutlineSectionsError as exc:
            last = exc
            correction = str(exc)
    raise last if last is not None else OutlineSectionsError("大纲正文生成失败")
