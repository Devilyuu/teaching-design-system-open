from types import SimpleNamespace

import pytest

from app.services.session_material_ai import (
    SessionMaterialEvidence,
    SessionMaterialValidationError,
    build_session_material_evidence,
    generate_ai_session_material,
    validate_session_material_payload,
)


def _evidence(material_type: str = "assignment", question_count: int = 5) -> SessionMaterialEvidence:
    return SessionMaterialEvidence(
        course_name="人工智能与创意设计",
        major="数字媒体艺术设计",
        class_name="数艺2501",
        session_no=1,
        topic="AIGC 创意流程",
        teaching_content="理解 AIGC 基础并完成创意草图",
        lesson_context={"teaching_goals": "完成创意草图", "key_points": "提示词设计"},
        material_type=material_type,
        difficulty="medium",
        estimated_minutes=40,
        question_count=question_count,
        course_goal_codes=["M1"],
        ability_codes=["1-3-4"],
    )


def _assignment_payload() -> dict:
    return {
        "title": "AIGC 创意草图实践作业",
        "task_requirements": "围绕指定主题完成一组创意草图。",
        "submission_requirements": "提交三张草图和一份设计说明。",
        "reference_points": "主题明确，提示词迭代过程完整。",
        "grading_criteria": "任务完成度 40 分，创意 30 分，表达 30 分。",
        "course_goal_codes": ["M1"],
        "ability_codes": ["1-3-4"],
    }


def _test_payload(question_count: int = 3) -> dict:
    return {
        "title": "AIGC 创意流程课堂测试",
        "questions": [
            {
                "number": index,
                "question": f"第 {index} 题题干",
                "points": 10,
                "answer": f"第 {index} 题答案",
                "grading_notes": "答出关键步骤得满分。",
            }
            for index in range(1, question_count + 1)
        ],
        "course_goal_codes": ["M1"],
        "ability_codes": ["1-3-4"],
    }


def test_validates_assignment_and_formats_editable_sections():
    result = validate_session_material_payload(_assignment_payload(), _evidence())

    assert result.title == "AIGC 创意草图实践作业"
    assert "任务要求" in result.content
    assert "提交三张草图" in result.content
    assert result.reference_answer.startswith("主题明确")
    assert result.course_goal_codes == "M1"
    assert result.ability_codes == "1-3-4"


def test_validates_test_question_count_answers_and_points():
    result = validate_session_material_payload(_test_payload(), _evidence("test", 3))

    assert "第 3 题（10 分）" in result.content
    assert "第 3 题答案" in result.reference_answer
    assert "总分：30 分" in result.grading_criteria


def test_rejects_unknown_ability_code():
    payload = _assignment_payload()
    payload["ability_codes"] = ["9-9-9"]

    with pytest.raises(SessionMaterialValidationError, match="9-9-9"):
        validate_session_material_payload(payload, _evidence())


def test_rejects_assignment_without_submission_requirements():
    payload = _assignment_payload()
    payload["submission_requirements"] = ""

    with pytest.raises(SessionMaterialValidationError, match="作业结构"):
        validate_session_material_payload(payload, _evidence())


def test_rejects_wrong_test_question_count():
    with pytest.raises(SessionMaterialValidationError, match="3"):
        validate_session_material_payload(_test_payload(2), _evidence("test", 3))


def test_builds_minimal_evidence_and_calls_json_model():
    request = SimpleNamespace(
        material_type="assignment",
        difficulty="medium",
        estimated_minutes=40,
        question_count=5,
    )
    task = SimpleNamespace(course_name="人工智能与创意设计", major="数字媒体艺术设计", class_name="数艺2501")
    outline = SimpleNamespace(
        session_no=1,
        topic="AIGC 创意流程",
        teaching_content="完成创意草图",
        course_goal_codes="M1",
        ability_codes="1-3-4",
    )
    lesson = SimpleNamespace(
        teaching_goals="完成创意草图",
        key_points="提示词设计",
        difficult_points="保持视觉一致性",
        teaching_process="案例分析与实践",
        homework="完善草图",
    )
    captured: dict = {}

    class FakeClient:
        def generate_json(self, system_prompt: str, user_payload: dict) -> dict:
            captured["system_prompt"] = system_prompt
            captured["user_payload"] = user_payload
            return _assignment_payload()

    result = generate_ai_session_material(
        SimpleNamespace(),
        task,
        outline,
        lesson,
        request,
        client_factory=lambda _: FakeClient(),
    )

    evidence = build_session_material_evidence(task, outline, lesson, request)
    assert result.title == "AIGC 创意草图实践作业"
    assert captured["user_payload"] == evidence.to_prompt_payload()
    assert "不得新增" in captured["system_prompt"]
