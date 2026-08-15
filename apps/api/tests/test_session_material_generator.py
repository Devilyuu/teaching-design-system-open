from types import SimpleNamespace

import pytest

from app.services.session_material_generator import generate_session_material


def make_outline():
    return SimpleNamespace(
        topic="AIGC 与创意设计导入",
        teaching_content="理解 AIGC 基础并完成案例拆解",
        post_task="提交案例分析记录",
        course_goal_codes="M1",
        ability_codes="1-3-4",
    )


def test_generates_assignment_from_outline_and_lesson():
    lesson = SimpleNamespace(
        teaching_goals="理解 AIGC 基础",
        key_points="案例拆解",
        homework="提交调研记录",
    )

    result = generate_session_material(make_outline(), lesson, "assignment", "medium", 40, 5)

    assert result.material_type == "assignment"
    assert result.source_status == "outline_and_lesson"
    assert result.course_goal_codes == "M1"
    assert result.ability_codes == "1-3-4"
    assert "提交" in result.content
    assert result.reference_answer
    assert result.grading_criteria


def test_generates_numbered_test_without_lesson():
    result = generate_session_material(make_outline(), None, "test", "basic", 20, 3)

    assert result.source_status == "outline_only"
    assert "第 3 题" in result.content
    assert result.course_goal_codes == "M1"
    assert result.ability_codes == "1-3-4"


@pytest.mark.parametrize(
    ("material_type", "estimated_minutes", "question_count"),
    [("quiz", 20, 3), ("assignment", 0, 3), ("test", 20, 0)],
)
def test_rejects_invalid_generation_options(material_type, estimated_minutes, question_count):
    with pytest.raises(ValueError):
        generate_session_material(
            make_outline(),
            None,
            material_type,
            "medium",
            estimated_minutes,
            question_count,
        )
