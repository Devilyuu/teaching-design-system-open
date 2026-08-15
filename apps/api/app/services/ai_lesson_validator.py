from dataclasses import dataclass
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, ValidationError

from app.services.lesson_evidence import LessonEvidence, canonical_code


class LessonValidationError(ValueError):
    pass


def _joined(value):
    """Models routinely return these prose fields as a JSON array of lines."""
    if isinstance(value, list):
        return "\n".join(str(item).strip() for item in value if str(item).strip())
    return value


Prose = Annotated[str, BeforeValidator(_joined)]


def _as_list(value):
    """A model may answer with one string where a list was asked for."""
    return value if isinstance(value, list) else [value]


class ProcessSegment(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    minutes: int = Field(gt=0, le=600)
    teacher_activity: Prose = Field(min_length=1, max_length=5000)
    student_activity: Prose = Field(min_length=1, max_length=5000)
    assessment: Prose = Field(min_length=1, max_length=2000)


class AiLessonPayload(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    teaching_goals: Prose = Field(min_length=1, max_length=10000)
    key_points: Prose = Field(min_length=1, max_length=5000)
    difficult_points: Prose = Field(min_length=1, max_length=5000)
    teaching_preparation: Prose = Field(min_length=1, max_length=5000)
    process_segments: list[ProcessSegment] = Field(min_length=1, max_length=30)
    summary: Prose = Field(min_length=1, max_length=5000)
    homework: Prose = Field(min_length=1, max_length=5000)
    course_goal_codes: Annotated[list, BeforeValidator(_as_list)] = Field(min_length=1)
    ability_codes: Annotated[list, BeforeValidator(_as_list)] = Field(min_length=1)


@dataclass(frozen=True)
class ValidatedLesson:
    title: str
    duration_minutes: int
    teaching_goals: str
    key_points: str
    difficult_points: str
    teaching_preparation: str
    teaching_process: str
    summary: str
    homework: str
    course_goal_codes: str
    ability_codes: str


def _code_lines(values: list[str]) -> list[str]:
    """One line per objective, so the export can pair them with the K rows."""
    lines = []
    for item in values:
        parts = item if isinstance(item, list) else str(item).replace("，", " ").replace(",", " ").split()
        codes = [canonical_code(str(part)) for part in parts if canonical_code(str(part))]
        if codes:
            lines.append(" ".join(codes))
    return lines


def _canonical_codes(values: list[str]) -> list[str]:
    return list(dict.fromkeys(canonical_code(value) for value in values if canonical_code(value)))


def _format_process(segments: list[ProcessSegment]) -> str:
    blocks: list[str] = []
    for segment in segments:
        blocks.append(
            "\n".join(
                [
                    f"{segment.title}（{segment.minutes}分钟）",
                    f"教师活动：{segment.teacher_activity}",
                    f"学生活动：{segment.student_activity}",
                    f"学习评价：{segment.assessment}",
                ]
            )
        )
    return "\n\n".join(blocks)


def _describe(exc: ValidationError) -> str:
    problems = []
    for error in exc.errors()[:6]:
        location = ".".join(str(part) for part in error["loc"]) or "(顶层)"
        problems.append(f"{location} {error['msg']}")
    return "；".join(problems)


def validate_lesson_payload(payload: dict, evidence: LessonEvidence) -> ValidatedLesson:
    try:
        parsed = AiLessonPayload.model_validate(payload)
    except ValidationError as exc:
        # Name the offending fields: the message is shown to the teacher and is
        # also fed back to the model on retry, so "结构不完整" alone is useless.
        raise LessonValidationError(f"教案结构不完整或字段格式错误：{_describe(exc)}") from exc

    goal_lines = [line for line in parsed.teaching_goals.splitlines() if line.strip()]
    if not 3 <= len(goal_lines) <= 6:
        raise LessonValidationError(
            f"teaching_goals 必须是 3 到 5 条可检验的目标，当前为 {len(goal_lines)} 条"
        )

    goal_code_lines = _code_lines(parsed.course_goal_codes)
    ability_code_lines = _code_lines(parsed.ability_codes)
    for name, lines in (("course_goal_codes", goal_code_lines), ("ability_codes", ability_code_lines)):
        if len(lines) not in (1, len(goal_lines)):
            raise LessonValidationError(
                f"{name} 必须与 teaching_goals 一一对应，共 {len(goal_lines)} 条，当前为 {len(lines)} 条"
            )

    goal_codes = _canonical_codes(" ".join(goal_code_lines).split())
    unknown_goals = set(goal_codes) - set(evidence.course_goals)
    if unknown_goals:
        raise LessonValidationError(f"模型返回了未授权课程目标：{', '.join(sorted(unknown_goals))}")

    ability_codes = _canonical_codes(" ".join(ability_code_lines).split())
    unknown_abilities = set(ability_codes) - set(evidence.allowed_ability_codes)
    if unknown_abilities:
        raise LessonValidationError(f"模型返回了未授权能力代码：{', '.join(sorted(unknown_abilities))}")

    required = list(evidence.required_segment_minutes)
    if required:
        produced = [segment.minutes for segment in parsed.process_segments]
        if produced != required:
            raise LessonValidationError(
                f"教学过程必须恰好有 {len(required)} 个环节，时长依次为 "
                f"{'、'.join(str(item) for item in required)} 分钟，当前为 "
                f"{'、'.join(str(item) for item in produced) or '（无）'} 分钟"
            )
    total_minutes = sum(segment.minutes for segment in parsed.process_segments)
    if not required and total_minutes != evidence.duration_minutes:
        raise LessonValidationError(
            f"教学过程总时长必须为 {evidence.duration_minutes} 分钟，当前为 {total_minutes} 分钟"
        )

    return ValidatedLesson(
        title=parsed.title.strip(),
        duration_minutes=evidence.duration_minutes,
        teaching_goals=parsed.teaching_goals.strip(),
        key_points=parsed.key_points.strip(),
        difficult_points=parsed.difficult_points.strip(),
        teaching_preparation=parsed.teaching_preparation.strip(),
        teaching_process=_format_process(parsed.process_segments),
        summary=parsed.summary.strip(),
        homework=parsed.homework.strip(),
        course_goal_codes="\n".join(goal_code_lines),
        ability_codes="\n".join(ability_code_lines),
    )
