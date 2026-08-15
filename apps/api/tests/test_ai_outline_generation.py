from types import SimpleNamespace

import pytest

from app.services.ai_outline_generation import (
    OutlineEvidenceError,
    OutlineValidationError,
    build_outline_evidence,
    generate_ai_outline,
    validate_outline_payload,
)


def _inputs(session_count: int = 2):
    task = SimpleNamespace(course_name="人工智能与创意设计", total_hours=session_count * 4, hours_per_session=4)
    projects = [
        SimpleNamespace(
            name="项目一：工具探索",
            description="建立基础认知",
            teaching_content="理解 AIGC 并完成首次图像生成",
            suggested_methods="案例分析 任务驱动",
            course_goal_codes="M1 M2",
            ability_codes="1-3-4 2-3-4",
            reference_hours=session_count * 4,
            practice_hours=session_count * 2,
        )
    ]
    goals = [
        SimpleNamespace(code="M1", description="理解 AIGC 基础", ability_codes="1-3-4"),
        SimpleNamespace(code="M2", description="完成 AI 创意项目", ability_codes="2-3-4"),
    ]
    indicators = [
        SimpleNamespace(code="1-3-4", description="理解工具原理"),
        SimpleNamespace(code="2-3-4", description="完成创意实践"),
    ]
    sessions = [
        SimpleNamespace(
            session_no=index,
            week_no=index,
            date_text=f"2026-09-{index * 7:02d}",
            weekday="周一",
            periods="1-4",
            hours=4,
        )
        for index in range(1, session_count + 1)
    ]
    return task, projects, goals, indicators, sessions


def _row(session_no: int, project_name: str = "项目一：工具探索") -> dict:
    return {
        "session_no": session_no,
        "project_name": project_name,
        "topic": f"第 {session_no} 次课主题",
        "teaching_content": f"第 {session_no} 次课教学内容",
        "ideological_point": "原创意识与职业规范",
        "teaching_methods": "案例分析与任务驱动",
        "pre_task": "观察案例",
        "in_class_task": "完成实践任务",
        "post_task": "完善并提交成果",
        "course_goal_codes": ["M1", "M2"],
        "ability_codes": ["1-3-4", "2-3-4"],
    }


def _evidence(session_count: int = 2):
    return build_outline_evidence(*_inputs(session_count))


def test_validates_whole_course_outline_and_merges_schedule():
    result = validate_outline_payload({"rows": [_row(1), _row(2)]}, _evidence())

    assert len(result) == 2
    assert result[0].date_text == "2026-09-07"
    assert result[1].week_no == 2
    assert result[0].course_goal_codes == "M1 M2"
    assert result[0].ability_codes == "1-3-4 2-3-4"


def test_rejects_wrong_row_count():
    with pytest.raises(OutlineValidationError, match="课次数量"):
        validate_outline_payload({"rows": [_row(1)]}, _evidence())


def test_rejects_duplicate_session_numbers():
    with pytest.raises(OutlineValidationError, match="连续"):
        validate_outline_payload({"rows": [_row(1), _row(1)]}, _evidence())


def test_rejects_ability_code_outside_selected_goals():
    row = _row(1)
    row["course_goal_codes"] = ["M1"]
    row["ability_codes"] = ["1-3-4", "2-3-4"]

    with pytest.raises(OutlineValidationError, match="2-3-4"):
        validate_outline_payload({"rows": [row, _row(2)]}, _evidence())


def test_rejects_course_when_schedule_hours_do_not_match_task():
    task, projects, goals, indicators, sessions = _inputs()
    task.total_hours = 12

    with pytest.raises(OutlineEvidenceError, match="总学时"):
        build_outline_evidence(task, projects, goals, indicators, sessions)


def test_rejects_missing_course_project_coverage():
    task, projects, goals, indicators, sessions = _inputs()
    projects.append(
        SimpleNamespace(
            name="项目二：动态影像",
            description="完成动态影像",
            teaching_content="生成并剪辑视频",
            suggested_methods="项目驱动",
            course_goal_codes="M2",
            ability_codes="2-3-4",
            reference_hours=4,
            practice_hours=2,
        )
    )
    projects[0].reference_hours = 4
    evidence = build_outline_evidence(task, projects, goals, indicators, sessions)

    with pytest.raises(OutlineValidationError, match="项目二：动态影像"):
        validate_outline_payload({"rows": [_row(1), _row(2)]}, evidence)


def test_calls_model_with_minimal_evidence():
    captured: dict = {}

    class FakeClient:
        def generate_json(self, system_prompt: str, user_payload: dict) -> dict:
            captured["system_prompt"] = system_prompt
            captured["user_payload"] = user_payload
            return {"rows": [_row(1), _row(2)]}

    result = generate_ai_outline(SimpleNamespace(), _evidence(), client_factory=lambda _: FakeClient())

    assert len(result) == 2
    assert "不得修改课表" in captured["system_prompt"]
    assert "location" not in str(captured["user_payload"])


def test_generated_rows_keep_the_project_they_were_assigned_to():
    result = validate_outline_payload({"rows": [_row(1), _row(2)]}, _evidence())

    assert [row.project_name for row in result] == ["项目一：工具探索", "项目一：工具探索"]


def test_missing_projects_explain_the_real_cause_instead_of_zero_hours():
    task, _projects, goals, indicators, sessions = _inputs()

    with pytest.raises(OutlineEvidenceError, match="没有可拆分的教学项目"):
        build_outline_evidence(task, [], goals, indicators, sessions)
