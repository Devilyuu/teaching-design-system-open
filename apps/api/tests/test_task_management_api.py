from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, select
import pytest

from app.db import engine
from app.main import app
from app.models import CourseGoal, ScheduleCandidateSession, ScheduleImportCandidate, TeachingTask
from app.routes import tasks as task_routes
from tests.test_schedule_mapping_api import auth_headers, create_task, make_registrar_xlsx


@pytest.fixture(autouse=True)
def isolate_task_files(tmp_path, monkeypatch):
    monkeypatch.setattr(task_routes, "TASK_FILE_DIR", tmp_path / "task-files")


def teacher_headers(client: TestClient, employee_no: str) -> dict[str, str]:
    admin = auth_headers(client)
    response = client.post(
        "/admin/users",
        headers=admin,
        json={"employee_no": employee_no, "name": "张老师", "role": "teacher", "password": "Teacher@2026!", "major_ids": []},
    )
    assert response.status_code == 200, response.text
    login = client.post("/auth/login", json={"employee_no": employee_no, "password": "Teacher@2026!"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_renames_a_course():
    with TestClient(app) as client:
        task_id = create_task(client)
        response = client.patch(f"/tasks/{task_id}", json={"course_name": "人工智能与创意设计（一） "})

        assert response.status_code == 200
        assert response.json()["course_name"] == "人工智能与创意设计（一）"
        listed = client.get("/tasks").json()
        assert [item["course_name"] for item in listed if item["id"] == task_id] == ["人工智能与创意设计（一）"]


def test_rejects_an_empty_course_name():
    with TestClient(app) as client:
        task_id = create_task(client)
        response = client.patch(f"/tasks/{task_id}", json={"course_name": "  "})

        assert response.status_code == 400
        assert "课程名称" in response.json()["detail"]


def test_another_teacher_cannot_edit_or_delete_the_course():
    with TestClient(app) as client:
        task_id = create_task(client)
        other = teacher_headers(client, "T9001")
        client.headers.clear()

        assert client.patch(f"/tasks/{task_id}", headers=other, json={"course_name": "别人的课"}).status_code == 404
        assert client.delete(f"/tasks/{task_id}", headers=other).status_code == 404


def test_deletes_the_course_with_its_rows_and_files(tmp_path):
    schedule = tmp_path / "schedule.xlsx"
    make_registrar_xlsx(schedule)
    with TestClient(app) as client:
        task_id = create_task(client)
        with schedule.open("rb") as handle:
            uploaded = client.post(
                f"/tasks/{task_id}/schedule-candidates",
                files={"file": ("schedule.xlsx", handle, "application/octet-stream")},
            )
        assert uploaded.status_code == 200, uploaded.text
        with Session(engine) as session:
            session.add(CourseGoal(task_id=task_id, code="M1", description="目标", ability_codes="1-3-4"))
            session.commit()
        task_dir = task_routes.TASK_FILE_DIR / str(task_id)
        assert task_dir.exists()

        response = client.delete(f"/tasks/{task_id}")

        assert response.status_code == 204
        assert client.get(f"/tasks/{task_id}/readiness").status_code == 404
        assert not task_dir.exists()

    with Session(engine) as session:
        assert session.get(TeachingTask, task_id) is None
        assert session.exec(select(CourseGoal).where(CourseGoal.task_id == task_id)).all() == []
        assert session.exec(select(ScheduleImportCandidate).where(ScheduleImportCandidate.task_id == task_id)).all() == []
        assert session.exec(select(ScheduleCandidateSession).where(ScheduleCandidateSession.candidate_id == uploaded.json()["id"])).all() == []
