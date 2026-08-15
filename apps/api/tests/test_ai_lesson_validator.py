import json

import httpx
import pytest

from app.models import AiModelConfig
from app.services.ai_lesson_validator import LessonValidationError, validate_lesson_payload
from app.services.lesson_evidence import LessonEvidence
from app.services.openai_compatible import OpenAICompatibleClient
from app.services.secret_store import encrypt_secret


def _evidence() -> LessonEvidence:
    return LessonEvidence(
        course_name="人工智能与创意设计",
        major="数字媒体艺术设计",
        class_name="数艺2501",
        session_no=1,
        date_text="2026-09-01",
        topic="AIGC创意流程",
        teaching_content="理解AIGC基础与创意设计流程",
        duration_minutes=160,
        teaching_methods="讲授、示范、实训",
        pre_task="观察案例",
        in_class_task="完成创意草图",
        post_task="优化方案",
        ideological_point="职业规范",
        course_goals={"M1": "完成创意设计任务"},
        selected_course_goal_codes=["M1"],
        allowed_ability_codes={"1-3-4": "能够完成创意设计"},
        selected_ability_codes=["1-3-4"],
        previous_topic="",
        next_topic="提示词设计",
    )


def _payload(total_minutes: int = 160) -> dict:
    return {
        "title": "第1次课：AIGC创意流程",
        "teaching_goals": ["能说出AIGC创意流程的环节", "能使用工具完成一张创意草图", "能对照标准评价草图质量"],
        "key_points": "AIGC创意流程",
        "difficult_points": "把创意判断落实到设计任务",
        "teaching_preparation": "教师准备案例，学生准备草图工具",
        "process_segments": [
            {
                "title": "导入与任务说明",
                "minutes": 40,
                "teacher_activity": "展示案例并说明任务",
                "student_activity": "观察并提出问题",
                "assessment": "口头提问",
            },
            {
                "title": "示范与实训",
                "minutes": total_minutes - 40,
                "teacher_activity": "示范并巡回指导",
                "student_activity": "完成创意草图",
                "assessment": "过程检查",
            },
        ],
        "summary": "归纳创意流程和职业规范",
        "homework": "优化创意方案",
        "course_goal_codes": ["M1", "M1", "M1"],
        "ability_codes": ["1-3-4", "1-3-4", "1-3-4"],
    }


def test_validates_structured_lesson_and_formats_process_text():
    lesson = validate_lesson_payload(_payload(), _evidence())

    assert lesson.duration_minutes == 160
    assert "导入与任务说明（40分钟）" in lesson.teaching_process
    assert "教师活动：展示案例并说明任务" in lesson.teaching_process
    # One code line per objective so the export can pair them with the K rows.
    assert lesson.course_goal_codes == "M1\nM1\nM1"
    assert lesson.ability_codes == "1-3-4\n1-3-4\n1-3-4"


def test_rejects_invented_ability_code():
    payload = _payload()
    payload["ability_codes"] = ["9-9-9"]

    with pytest.raises(LessonValidationError, match="9-9-9"):
        validate_lesson_payload(payload, _evidence())


def test_rejects_process_duration_mismatch():
    with pytest.raises(LessonValidationError, match="160"):
        validate_lesson_payload(_payload(total_minutes=120), _evidence())


def test_openai_compatible_client_parses_json_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://model.example/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer sk-private"
        request_body = json.loads(request.content)
        assert request_body["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(_payload(), ensure_ascii=False)}}]},
        )

    config = AiModelConfig(
        base_url="https://model.example/v1",
        model_name="lesson-model",
        encrypted_api_key=encrypt_secret("sk-private"),
    )
    client = OpenAICompatibleClient(config, transport=httpx.MockTransport(handler))

    assert client.generate_json("system", {"evidence": True})["title"].startswith("第1次课")


def test_accepts_list_valued_text_fields_from_the_model():
    """DeepSeek returns these as JSON arrays about half the time."""
    payload = _payload()
    payload["teaching_goals"] = ["1. 掌握概念", "2. 完成实践", "3. 评价成果"]
    payload["key_points"] = ["要点一", "要点二"]
    payload["difficult_points"] = ["难点一"]
    payload["teaching_preparation"] = ["课件", "分组名单"]
    payload["homework"] = ["作业一", "作业二"]
    payload["summary"] = ["小结一"]
    payload["process_segments"][0]["teacher_activity"] = ["讲解", "演示"]

    lesson = validate_lesson_payload(payload, _evidence())

    assert lesson.teaching_goals == "1. 掌握概念\n2. 完成实践\n3. 评价成果"
    assert lesson.key_points == "要点一\n要点二"
    assert lesson.difficult_points == "难点一"
    assert lesson.teaching_preparation == "课件\n分组名单"
    assert lesson.homework == "作业一\n作业二"


def test_names_the_offending_field_when_the_structure_is_wrong():
    payload = _payload()
    del payload["key_points"]

    with pytest.raises(LessonValidationError, match="key_points"):
        validate_lesson_payload(payload, _evidence())


def _evidence_with_layout():
    from dataclasses import replace
    return replace(_evidence(), required_segment_minutes=(20, 40, 60, 40))


def test_enforces_the_segment_pacing_the_template_fixes():
    payload = _payload()  # two segments of 40 and 120

    with pytest.raises(LessonValidationError, match="20、40、60、40"):
        validate_lesson_payload(payload, _evidence_with_layout())


def test_accepts_segments_matching_the_template_pacing():
    payload = _payload()
    payload["process_segments"] = [
        {"title": f"环节{index}", "minutes": minutes, "teacher_activity": "讲解",
         "student_activity": "练习", "assessment": "检查"}
        for index, minutes in enumerate((20, 40, 60, 40), start=1)
    ]

    lesson = validate_lesson_payload(payload, _evidence_with_layout())

    assert lesson.teaching_process.count("分钟") == 4
