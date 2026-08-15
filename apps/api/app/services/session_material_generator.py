from dataclasses import dataclass
from typing import Literal


MaterialType = Literal["assignment", "test"]


@dataclass(frozen=True)
class GeneratedSessionMaterial:
    material_type: MaterialType
    title: str
    content: str
    reference_answer: str
    grading_criteria: str
    difficulty: str
    estimated_minutes: int
    course_goal_codes: str
    ability_codes: str
    source_status: str


def generate_session_material(
    outline,
    lesson,
    material_type: str,
    difficulty: str,
    estimated_minutes: int,
    question_count: int,
) -> GeneratedSessionMaterial:
    if material_type not in {"assignment", "test"}:
        raise ValueError("Unsupported material type")
    if estimated_minutes <= 0:
        raise ValueError("Estimated minutes must be positive")
    if material_type == "test" and question_count <= 0:
        raise ValueError("Question count must be positive")

    source_status = "outline_and_lesson" if lesson is not None else "outline_only"
    if material_type == "assignment":
        lesson_homework = getattr(lesson, "homework", "") if lesson else ""
        task = lesson_homework or outline.post_task or outline.teaching_content
        return GeneratedSessionMaterial(
            material_type="assignment",
            title=f"{outline.topic}实践作业",
            content=f"围绕“{outline.topic}”完成以下任务：{task}",
            reference_answer=f"成果应能体现：{outline.teaching_content}",
            grading_criteria="任务完成度 40 分；方法运用 30 分；成果表达 20 分；规范性 10 分。",
            difficulty=difficulty,
            estimated_minutes=estimated_minutes,
            course_goal_codes=outline.course_goal_codes,
            ability_codes=outline.ability_codes,
            source_status=source_status,
        )

    questions = "\n".join(
        f"第 {index} 题：结合本次课内容说明{outline.topic}的关键要点。"
        for index in range(1, question_count + 1)
    )
    return GeneratedSessionMaterial(
        material_type="test",
        title=f"{outline.topic}课堂测试",
        content=questions,
        reference_answer=f"答案应覆盖：{outline.teaching_content}",
        grading_criteria=f"共 {question_count} 题，按要点完整性、准确性和表达规范评分。",
        difficulty=difficulty,
        estimated_minutes=estimated_minutes,
        course_goal_codes=outline.course_goal_codes,
        ability_codes=outline.ability_codes,
        source_status=source_status,
    )
