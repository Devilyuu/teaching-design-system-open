import json
from types import SimpleNamespace

import pytest

from app.models import OutlineRow
from app.services.outline_revision import OutlineRevisionError, generate_outline_revision


def _row() -> OutlineRow:
    return OutlineRow(
        task_id=1,
        session_no=1,
        date_text="2026-09-07",
        week_no=1,
        weekday="周一",
        periods="1-4",
        topic="AIGC 工具入门",
        teaching_content="理解 AIGC 并完成首次图像生成",
        ideological_point="原创意识",
        teaching_methods="案例分析",
        pre_task="观察案例",
        in_class_task="完成实践",
        post_task="提交成果",
        course_goal_codes="M1",
        ability_codes="1-3-4",
    )


def test_generates_one_outline_field_candidate():
    class FakeClient:
        def generate_json(self, _system_prompt: str, _user_payload: dict) -> dict:
            return {"teaching_content": "优化后的教学内容"}

    proposed = generate_outline_revision(
        SimpleNamespace(), _row(), None, None, "teaching_content", "增加实践任务", lambda _: FakeClient()
    )

    assert proposed == "优化后的教学内容"


def test_generates_task_fields_as_structured_candidate():
    class FakeClient:
        def generate_json(self, _system_prompt: str, _user_payload: dict) -> dict:
            return {"pre_task": "课前观察", "in_class_task": "课堂实践", "post_task": "课后完善"}

    proposed = generate_outline_revision(
        SimpleNamespace(), _row(), None, None, "tasks", "", lambda _: FakeClient()
    )

    assert json.loads(proposed)["in_class_task"] == "课堂实践"


def test_rejects_incomplete_task_candidate():
    class FakeClient:
        def generate_json(self, _system_prompt: str, _user_payload: dict) -> dict:
            return {"pre_task": "课前观察", "in_class_task": "课堂实践"}

    with pytest.raises(OutlineRevisionError, match="缺少"):
        generate_outline_revision(SimpleNamespace(), _row(), None, None, "tasks", "", lambda _: FakeClient())
