from types import SimpleNamespace

import pytest

from app.services.ai_outline_sections import (
    OutlineSectionsError,
    build_sections_evidence,
    generate_outline_sections,
    validate_sections_payload,
)


def item(**values):
    return SimpleNamespace(**values)


def evidence(total_hours: int = 80):
    return build_sections_evidence(
        task=item(course_name="移动终端APP设计", total_hours=total_hours),
        projects=[
            item(name="项目一：逻辑建模", description="", teaching_content="调研与功能梳理",
                 suggested_methods="讲授、讨论", reference_hours=30),
            item(name="项目二：视觉设计", description="", teaching_content="图标与页面设计",
                 suggested_methods="实做学习", reference_hours=50),
        ],
        goals=[item(code="M1", description="掌握界面设计", ability_codes="1-3-4")],
        indicators=[item(code="1-3-4", description="界面设计能力")],
    )


def payload(**overrides):
    values = {
        "course_summary": "本课程围绕移动端界面设计展开。",
        "teaching_strategy": "线上线下混合式+项目化教学",
        "prerequisites": "图像处理技术、设计基础",
        "learning_outcomes": ["掌握界面设计流程", "能够完成高保真原型"],
        "unit_key_points": {
            "项目一：逻辑建模": "重点：需求调研\n难点：撰写提示词",
            "项目二：视觉设计": "重点：视觉一致性\n难点：规范制定",
        },
        "study_advice": "跟着做、想着做、变着做，逐步强化训练。",
        "academic_integrity": "不得抄袭他人作品",
        "attendance": "请假需履行手续",
        "classroom_discipline": "上课起立问好，保持教室整洁。",
        "assignment_requirements": "作业不得迟交。",
    }
    values.update(overrides)
    return values


def test_the_learning_content_table_comes_from_the_standard_not_the_model():
    """Only 重点/难点 is written here; the rest is what the standard already states."""
    sections = validate_sections_payload(payload(), evidence())

    first, second = sections.learning_units
    assert [unit.name for unit in sections.learning_units] == ["项目一：逻辑建模", "项目二：视觉设计"]
    assert first.teaching_content == "调研与功能梳理"
    assert first.teaching_methods == "讲授、讨论"
    assert first.hours == 30 and second.hours == 50
    assert first.key_points.startswith("重点：需求调研")


def test_every_unit_needs_its_key_points_and_no_invented_ones():
    with pytest.raises(OutlineSectionsError, match="缺少教学单元"):
        validate_sections_payload(
            payload(unit_key_points={"项目一：逻辑建模": "重点：a\n难点：b"}),
            evidence(),
        )

    with pytest.raises(OutlineSectionsError, match="多出未知教学单元"):
        validate_sections_payload(
            payload(unit_key_points={
                "项目一：逻辑建模": "重点：a\n难点：b",
                "项目二：视觉设计": "重点：c\n难点：d",
                "项目三：凭空冒出来的": "重点：e\n难点：f",
            }),
            evidence(),
        )


def test_unit_hours_are_checked_against_the_course_total():
    """The standard is the one that disagrees here, so say so rather than blame the model."""
    with pytest.raises(OutlineSectionsError, match="请先核对课程标准"):
        validate_sections_payload(payload(), evidence(total_hours=64))


def test_a_malformed_payload_is_rejected_before_anything_is_read():
    with pytest.raises(OutlineSectionsError, match="结构不完整"):
        validate_sections_payload({"course_summary": "只有一个字段"}, evidence())


def _renamed_unit():
    return payload(unit_key_points={"项目一 逻辑建模": "重点：a\n难点：b", "项目二：视觉设计": "重点：c\n难点：d"})


def test_generation_retries_with_the_reason_it_was_rejected():
    attempts: list[dict] = []

    class Client:
        def __init__(self, config):
            pass

        def generate_json(self, system_prompt, prompt_payload):
            attempts.append(prompt_payload)
            return _renamed_unit() if len(attempts) == 1 else payload()

    sections = generate_outline_sections(item(id=1), evidence(), client_factory=Client)

    assert len(attempts) == 2
    assert "缺少教学单元" in attempts[1]["previous_attempt_error"]
    assert sections.learning_units[0].key_points.startswith("重点：需求调研")


def test_generation_gives_up_with_the_last_reason(monkeypatch):
    class Client:
        def __init__(self, config):
            pass

        def generate_json(self, system_prompt, prompt_payload):
            return _renamed_unit()

    with pytest.raises(OutlineSectionsError, match="缺少教学单元"):
        generate_outline_sections(item(id=1), evidence(), client_factory=Client, attempts=2)
