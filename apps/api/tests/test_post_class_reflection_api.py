import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import engine
from app.main import app
from app.models import LessonPlan, OutlineRow, PostClassReflection


def _auth_headers(client: TestClient):
    response = client.post("/auth/login", json={"employee_no": "admin", "password": "Admin@2026!"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def reflection_course():
    with TestClient(app) as client:
        client.headers.update(_auth_headers(client))
        task = client.post(
            "/tasks",
            json={
                "term": "2026-2027-1",
                "major": "数字媒体艺术设计",
                "class_name": "数媒 2501",
                "course_name": "人工智能与创意设计",
                "teacher_name": "测试教师",
                "location": "智慧教室",
                "total_hours": 8,
                "hours_per_session": 4,
            },
        ).json()
        with Session(engine) as session:
            rows = []
            for session_no, date_text in ((1, "2026-09-07"), (2, "2026-09-14")):
                row = OutlineRow(
                    task_id=task["id"],
                    session_no=session_no,
                    date_text=date_text,
                    week_no=session_no,
                    weekday="周一",
                    periods="1-4",
                    topic=f"第 {session_no} 次课",
                    teaching_content=f"第 {session_no} 次课教学内容",
                    course_goal_codes="M1",
                    ability_codes="1-3-4",
                )
                session.add(row)
                session.commit()
                session.refresh(row)
                rows.append(row)
            second_lesson = LessonPlan(
                task_id=task["id"],
                outline_row_id=rows[1].id,
                session_no=2,
                title="第 2 次课",
                teaching_goals="完成创意设计任务",
                key_points="设计流程",
                difficult_points="方案迭代",
                teaching_process="导入\n讲授新知识",
                homework="完善作品",
                course_goal_codes="M1",
                ability_codes="1-3-4",
            )
            session.add(second_lesson)
            session.commit()
            session.refresh(second_lesson)
            yield client, task["id"], rows[0].id, rows[1].id, second_lesson.id


def _reflection_payload():
    return {
        "progress_status": "partial",
        "mastery_level": "average",
        "classroom_effect": "normal",
        "note": "示范环节未完成",
    }


def test_teacher_saves_reflection_and_workspace_returns_suggestion(reflection_course):
    client, task_id, first_row_id, second_row_id, _ = reflection_course

    response = client.put(
        f"/tasks/{task_id}/sessions/{first_row_id}/reflection",
        json=_reflection_payload(),
    )

    assert response.status_code == 200
    assert response.json()["target_outline_row_id"] == second_row_id
    workspace = client.get(f"/tasks/{task_id}/sessions/{first_row_id}").json()
    assert workspace["reflection"]["suggested_minutes"] == 20
    assert workspace["next_outline"]["id"] == second_row_id
    assert workspace["next_lesson_exists"] is True


def test_last_session_saves_without_target(reflection_course):
    client, task_id, _, last_row_id, _ = reflection_course

    response = client.put(
        f"/tasks/{task_id}/sessions/{last_row_id}/reflection",
        json={
            "progress_status": "completed",
            "mastery_level": "good",
            "classroom_effect": "smooth",
            "note": "",
        },
    )

    assert response.status_code == 200
    assert response.json()["target_outline_row_id"] is None


def test_applied_reflection_cannot_be_edited_or_deleted(reflection_course):
    client, task_id, first_row_id, _, _ = reflection_course
    reflection = client.put(
        f"/tasks/{task_id}/sessions/{first_row_id}/reflection",
        json=_reflection_payload(),
    ).json()
    with Session(engine) as session:
        stored = session.get(PostClassReflection, reflection["id"])
        stored.status = "applied"
        session.add(stored)
        session.commit()

    updated = client.put(
        f"/tasks/{task_id}/sessions/{first_row_id}/reflection",
        json=_reflection_payload(),
    )
    deleted = client.delete(f"/tasks/{task_id}/reflections/{reflection['id']}")

    assert updated.status_code == 409
    assert deleted.status_code == 409


def test_apply_appends_once_and_revert_preserves_teacher_changes(reflection_course):
    client, task_id, first_row_id, _, lesson_id = reflection_course
    reflection = client.put(
        f"/tasks/{task_id}/sessions/{first_row_id}/reflection",
        json=_reflection_payload(),
    ).json()

    first = client.post(f"/tasks/{task_id}/reflections/{reflection['id']}/apply")
    second = client.post(f"/tasks/{task_id}/reflections/{reflection['id']}/apply")

    assert first.status_code == second.status_code == 200
    assert second.json()["teaching_process"].count(f"记录 {reflection['id']} 开始") == 1
    lesson = second.json()
    lesson["teaching_process"] += "\n教师后来新增的总结"
    saved = client.put(f"/tasks/{task_id}/lessons/{lesson_id}", json={
        key: value for key, value in lesson.items()
        if key not in {"id", "task_id", "outline_row_id", "session_no"}
    })
    assert saved.status_code == 200

    reverted = client.post(f"/tasks/{task_id}/reflections/{reflection['id']}/revert")
    repeated = client.post(f"/tasks/{task_id}/reflections/{reflection['id']}/revert")

    assert reverted.status_code == repeated.status_code == 200
    assert "教师后来新增的总结" in repeated.json()["teaching_process"]
    assert f"记录 {reflection['id']} 开始" not in repeated.json()["teaching_process"]


def test_apply_without_next_lesson_stays_pending(reflection_course):
    client, task_id, first_row_id, _, lesson_id = reflection_course
    with Session(engine) as session:
        session.delete(session.get(LessonPlan, lesson_id))
        session.commit()
    reflection = client.put(
        f"/tasks/{task_id}/sessions/{first_row_id}/reflection",
        json=_reflection_payload(),
    ).json()

    response = client.post(f"/tasks/{task_id}/reflections/{reflection['id']}/apply")

    assert response.status_code == 409
    workspace = client.get(f"/tasks/{task_id}/sessions/{first_row_id}").json()
    assert workspace["reflection"]["status"] == "pending"


def test_regenerating_whole_course_reapplies_active_adjustment(reflection_course):
    client, task_id, first_row_id, second_row_id, _ = reflection_course
    reflection = client.put(
        f"/tasks/{task_id}/sessions/{first_row_id}/reflection",
        json=_reflection_payload(),
    ).json()
    assert client.post(f"/tasks/{task_id}/reflections/{reflection['id']}/apply").status_code == 200

    response = client.post(f"/tasks/{task_id}/lessons/generate")

    assert response.status_code == 200
    target = next(item for item in response.json() if item["outline_row_id"] == second_row_id)
    assert f"记录 {reflection['id']} 开始" in target["teaching_process"]


def test_outline_list_marks_recorded_and_adjusted_sessions(reflection_course):
    client, task_id, first_row_id, second_row_id, _ = reflection_course
    reflection = client.put(
        f"/tasks/{task_id}/sessions/{first_row_id}/reflection",
        json=_reflection_payload(),
    ).json()
    assert client.post(f"/tasks/{task_id}/reflections/{reflection['id']}/apply").status_code == 200

    rows = client.get(f"/tasks/{task_id}/outline").json()
    first = next(row for row in rows if row["id"] == first_row_id)
    second = next(row for row in rows if row["id"] == second_row_id)

    assert first["post_class_recorded"] is True
    assert second["has_previous_adjustment"] is True
