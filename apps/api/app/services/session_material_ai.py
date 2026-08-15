from dataclasses import asdict, dataclass
from typing import Literal, Protocol

from pydantic import BaseModel, Field, ValidationError

from app.models import AiModelConfig
from app.services.lesson_evidence import canonical_code
from app.services.openai_compatible import OpenAICompatibleClient
from app.services.session_material_generator import GeneratedSessionMaterial


SYSTEM_PROMPT = """你是高职院校教师备课助手。只能使用输入证据生成当前课次的作业或测试，不得新增、删减或改写课程目标代码和能力指标代码。返回一个 JSON 对象。
作业字段：title、task_requirements、submission_requirements、reference_points、grading_criteria、course_goal_codes、ability_codes。
测试字段：title、questions、course_goal_codes、ability_codes；questions 每项包含 number、question、points、answer、grading_notes。"""


class SessionMaterialValidationError(ValueError):
    pass


@dataclass(frozen=True)
class SessionMaterialEvidence:
    course_name: str
    major: str
    class_name: str
    session_no: int
    topic: str
    teaching_content: str
    lesson_context: dict[str, str]
    material_type: Literal["assignment", "test"]
    difficulty: str
    estimated_minutes: int
    question_count: int
    course_goal_codes: list[str]
    ability_codes: list[str]

    def to_prompt_payload(self) -> dict:
        return asdict(self)


class AssignmentPayload(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    task_requirements: str = Field(min_length=1, max_length=10000)
    submission_requirements: str = Field(min_length=1, max_length=5000)
    reference_points: str = Field(min_length=1, max_length=10000)
    grading_criteria: str = Field(min_length=1, max_length=10000)
    course_goal_codes: list[str] = Field(min_length=1)
    ability_codes: list[str] = Field(min_length=1)


class TestQuestion(BaseModel):
    number: int = Field(gt=0, le=100)
    question: str = Field(min_length=1, max_length=5000)
    points: int = Field(gt=0, le=1000)
    answer: str = Field(min_length=1, max_length=5000)
    grading_notes: str = Field(min_length=1, max_length=5000)


class TestPayload(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    questions: list[TestQuestion] = Field(min_length=1, max_length=50)
    course_goal_codes: list[str] = Field(min_length=1)
    ability_codes: list[str] = Field(min_length=1)


class JsonModelClient(Protocol):
    def generate_json(self, system_prompt: str, user_payload: dict) -> dict: ...


def _codes(value: str | list[str]) -> list[str]:
    raw_values = value if isinstance(value, list) else value.replace("，", " ").replace(",", " ").split()
    return list(dict.fromkeys(canonical_code(item) for item in raw_values if canonical_code(item)))


def _lesson_context(lesson) -> dict[str, str]:
    if lesson is None:
        return {}
    fields = ("teaching_goals", "key_points", "difficult_points", "teaching_process", "homework")
    return {field: str(getattr(lesson, field, "") or "") for field in fields}


def build_session_material_evidence(task, outline, lesson, request) -> SessionMaterialEvidence:
    return SessionMaterialEvidence(
        course_name=task.course_name,
        major=task.major,
        class_name=task.class_name,
        session_no=outline.session_no,
        topic=outline.topic,
        teaching_content=outline.teaching_content,
        lesson_context=_lesson_context(lesson),
        material_type=request.material_type,
        difficulty=request.difficulty,
        estimated_minutes=request.estimated_minutes,
        question_count=request.question_count,
        course_goal_codes=_codes(outline.course_goal_codes),
        ability_codes=_codes(outline.ability_codes),
    )


def _require_exact_codes(actual: list[str], expected: list[str], label: str) -> None:
    actual_codes = _codes(actual)
    expected_codes = _codes(expected)
    unexpected = sorted(set(actual_codes) - set(expected_codes))
    missing = sorted(set(expected_codes) - set(actual_codes))
    if unexpected or missing:
        details: list[str] = []
        if unexpected:
            details.append(f"未授权：{', '.join(unexpected)}")
        if missing:
            details.append(f"缺少：{', '.join(missing)}")
        raise SessionMaterialValidationError(f"{label}代码必须与当前课次严格一致（{'；'.join(details)}）")


def _validate_assignment(payload: dict, evidence: SessionMaterialEvidence) -> GeneratedSessionMaterial:
    try:
        parsed = AssignmentPayload.model_validate(payload)
    except ValidationError as exc:
        raise SessionMaterialValidationError("AI 返回的作业结构不完整或字段格式错误") from exc
    _require_exact_codes(parsed.course_goal_codes, evidence.course_goal_codes, "课程目标")
    _require_exact_codes(parsed.ability_codes, evidence.ability_codes, "能力指标")
    return GeneratedSessionMaterial(
        material_type="assignment",
        title=parsed.title.strip(),
        content=(
            f"任务要求：\n{parsed.task_requirements.strip()}\n\n"
            f"提交要求：\n{parsed.submission_requirements.strip()}"
        ),
        reference_answer=parsed.reference_points.strip(),
        grading_criteria=parsed.grading_criteria.strip(),
        difficulty=evidence.difficulty,
        estimated_minutes=evidence.estimated_minutes,
        course_goal_codes=" ".join(evidence.course_goal_codes),
        ability_codes=" ".join(evidence.ability_codes),
        source_status="outline_and_lesson" if evidence.lesson_context else "outline_only",
    )


def _validate_test(payload: dict, evidence: SessionMaterialEvidence) -> GeneratedSessionMaterial:
    try:
        parsed = TestPayload.model_validate(payload)
    except ValidationError as exc:
        raise SessionMaterialValidationError("AI 返回的测试结构不完整或字段格式错误") from exc
    if len(parsed.questions) != evidence.question_count:
        raise SessionMaterialValidationError(
            f"测试题量必须为 {evidence.question_count} 题，当前为 {len(parsed.questions)} 题"
        )
    expected_numbers = list(range(1, evidence.question_count + 1))
    actual_numbers = sorted(question.number for question in parsed.questions)
    if actual_numbers != expected_numbers:
        raise SessionMaterialValidationError("测试题号必须从 1 开始连续且不得重复")
    _require_exact_codes(parsed.course_goal_codes, evidence.course_goal_codes, "课程目标")
    _require_exact_codes(parsed.ability_codes, evidence.ability_codes, "能力指标")
    questions = sorted(parsed.questions, key=lambda item: item.number)
    total_points = sum(question.points for question in questions)
    content = "\n\n".join(
        f"第 {question.number} 题（{question.points} 分）\n{question.question.strip()}" for question in questions
    )
    answers = "\n\n".join(
        f"第 {question.number} 题\n{question.answer.strip()}" for question in questions
    )
    grading = "\n\n".join(
        f"第 {question.number} 题（{question.points} 分）：{question.grading_notes.strip()}" for question in questions
    )
    return GeneratedSessionMaterial(
        material_type="test",
        title=parsed.title.strip(),
        content=content,
        reference_answer=answers,
        grading_criteria=f"总分：{total_points} 分\n\n{grading}",
        difficulty=evidence.difficulty,
        estimated_minutes=evidence.estimated_minutes,
        course_goal_codes=" ".join(evidence.course_goal_codes),
        ability_codes=" ".join(evidence.ability_codes),
        source_status="outline_and_lesson" if evidence.lesson_context else "outline_only",
    )


def validate_session_material_payload(payload: dict, evidence: SessionMaterialEvidence) -> GeneratedSessionMaterial:
    if evidence.material_type == "assignment":
        return _validate_assignment(payload, evidence)
    return _validate_test(payload, evidence)


def generate_ai_session_material(
    config: AiModelConfig,
    task,
    outline,
    lesson,
    request,
    client_factory=OpenAICompatibleClient,
) -> GeneratedSessionMaterial:
    evidence = build_session_material_evidence(task, outline, lesson, request)
    payload = client_factory(config).generate_json(SYSTEM_PROMPT, evidence.to_prompt_payload())
    return validate_session_material_payload(payload, evidence)
