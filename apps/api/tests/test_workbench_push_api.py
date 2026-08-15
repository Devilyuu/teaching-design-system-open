from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.routes import tasks as task_routes
from app.services.workbench_import import Workbench, WorkbenchError

from tests.test_export_history_api import (
    create_task,
    make_lesson_template,
    make_outline_template,
    seed_lesson,
    seed_outline_row,
    upload_template,
)


@pytest.fixture(autouse=True)
def isolate_task_files(tmp_path, monkeypatch):
    monkeypatch.setattr(task_routes, "TASK_FILE_DIR", tmp_path / "task-files")


@pytest.fixture
def configured(monkeypatch):
    """Both modules read the environment; the button and the route must agree."""
    from app.routes import integrations as integration_routes

    def workbench():
        return Workbench(base_url="https://workbench.example", token="tok", owner_employee_no="admin")

    for module in (task_routes, integration_routes):
        monkeypatch.setattr(module, "workbench_from_env", workbench)


def capture(monkeypatch, result: dict | None = None) -> list[dict]:
    sent: list[dict] = []

    def fake_push(workbench, **kwargs):
        sent.append(kwargs)
        return result or {"id": "abc", "status": "RECEIVED", "created": True, "replaced": False}

    monkeypatch.setattr(task_routes, "push_document", fake_push)
    return sent


def export_lessons(client: TestClient, task_id: int, tmp_path: Path) -> int:
    template = tmp_path / "lesson-template.docx"
    make_lesson_template(template)
    outline_row_id = seed_outline_row(task_id)
    seed_lesson(task_id, outline_row_id)
    upload_template(client, task_id, "lesson", template)
    assert client.post(f"/tasks/{task_id}/lessons/export").status_code == 200
    records = client.get(f"/tasks/{task_id}/exports").json()
    return next(record["id"] for record in records if record["artifact_type"] == "lesson")


def test_the_button_is_hidden_where_no_workbench_is_configured(monkeypatch):
    monkeypatch.setattr(task_routes, "workbench_from_env", lambda: None)
    with TestClient(app) as client:
        create_task(client)
        status = client.get("/integrations/workbench")

    assert status.status_code == 200
    assert status.json() == {"configured": False, "message": ""}


def test_a_half_set_configuration_is_reported_rather_than_hidden(monkeypatch):
    def half(*_args, **_kwargs):
        raise WorkbenchError("工作台回流配置不完整：WORKBENCH_BASE_URL 与 WORKBENCH_IMPORT_TOKEN 必须同时设置")

    monkeypatch.setattr(task_routes, "workbench_from_env", half)
    from app.routes import integrations as integration_routes

    monkeypatch.setattr(integration_routes, "workbench_from_env", half)
    with TestClient(app) as client:
        create_task(client)
        status = client.get("/integrations/workbench")

    assert status.json()["configured"] is False
    assert "配置不完整" in status.json()["message"]


def test_pushing_files_the_lesson_plan_under_the_course_not_the_export(tmp_path, monkeypatch, configured):
    """Re-exporting must land on the same workbench record, so the id names the course."""
    sent = capture(monkeypatch)

    with TestClient(app) as client:
        task_id = create_task(client)
        first = export_lessons(client, task_id, tmp_path)
        assert client.post(f"/tasks/{task_id}/exports/{first}/push-to-workbench").status_code == 200

        assert client.post(f"/tasks/{task_id}/lessons/export").status_code == 200
        records = client.get(f"/tasks/{task_id}/exports").json()
        second = max(record["id"] for record in records if record["artifact_type"] == "lesson")
        assert second != first
        pushed = client.post(f"/tasks/{task_id}/exports/{second}/push-to-workbench")

    assert pushed.status_code == 200
    assert pushed.json() == {"id": "abc", "status": "RECEIVED", "created": True, "replaced": False}
    # Two exports, one workbench record: the id follows the course, not the file.
    assert [item["external_id"] for item in sent] == [f"task-{task_id}-lesson"] * 2
    assert sent[0]["title"] == "人工智能与创意设计 整门课教案"
    assert sent[0]["course_name"] == "人工智能与创意设计"
    assert sent[0]["finished_at"].count("-") == 2
    assert "2026-2027 第一学期" in sent[0]["note"]


def test_the_outline_files_under_its_own_id_not_the_lesson_plans(tmp_path, monkeypatch, configured):
    """Both deliverables travel, and neither overwrites the other."""
    sent = capture(monkeypatch)
    template = tmp_path / "outline-template.docx"
    make_outline_template(template)

    with TestClient(app) as client:
        task_id = create_task(client)
        seed_outline_row(task_id)
        upload_template(client, task_id, "outline", template)
        assert client.post(f"/tasks/{task_id}/outline/export").status_code == 200
        outline_id = client.get(f"/tasks/{task_id}/exports").json()[0]["id"]
        pushed = client.post(f"/tasks/{task_id}/exports/{outline_id}/push-to-workbench")

    assert pushed.status_code == 200
    assert sent[0]["external_id"] == f"task-{task_id}-outline"
    assert sent[0]["title"] == "人工智能与创意设计 课程实施大纲"


def test_a_workbench_rejection_reaches_the_teacher(tmp_path, monkeypatch, configured):
    def refuse(workbench, **kwargs):
        raise WorkbenchError("HTTP 409：这份教案已在工作台引用为成果，请先在工作台取消引用再重新推送")

    monkeypatch.setattr(task_routes, "push_document", refuse)

    with TestClient(app) as client:
        task_id = create_task(client)
        export_id = export_lessons(client, task_id, tmp_path)
        failed = client.post(f"/tasks/{task_id}/exports/{export_id}/push-to-workbench")

    assert failed.status_code == 502
    assert "取消引用" in failed.json()["detail"]


def _other_teacher(client: TestClient) -> None:
    """Log the client in as a pilot teacher who has no workbench of their own.

    The account may already exist -- the suite shares one database across the
    session -- so what is asserted is the login, not the creation.
    """
    password = "Pilot@2026!"
    client.post(
        "/admin/users",
        json={"employee_no": "2044", "name": "试点老师", "role": "teacher", "password": password},
    )
    token = client.post("/auth/login", json={"employee_no": "2044", "password": password}).json()
    assert "access_token" in token, token
    client.headers.update({"Authorization": f"Bearer {token['access_token']}"})


def test_a_pilot_teacher_is_not_offered_somebody_elses_workbench(monkeypatch, configured):
    """One deployment, many teachers, one personal platform among them."""
    with TestClient(app) as client:
        create_task(client)
        assert client.get("/integrations/workbench").json()["configured"] is True

        _other_teacher(client)
        status = client.get("/integrations/workbench")

    assert status.json() == {"configured": False, "message": ""}


def test_a_pilot_teacher_cannot_push_into_somebody_elses_workbench(tmp_path, monkeypatch, configured):
    """Hiding the button is not enough; the route is what actually files the file."""
    sent = capture(monkeypatch)

    with TestClient(app) as client:
        task_id = create_task(client)
        export_id = export_lessons(client, task_id, tmp_path)
        _other_teacher(client)
        refused = client.post(f"/tasks/{task_id}/exports/{export_id}/push-to-workbench")

    # 404 rather than 403: the course is not theirs either, and whose workbench
    # this is stays none of their business.
    assert refused.status_code == 404
    assert sent == []


def test_pushing_without_a_workbench_says_so(tmp_path, monkeypatch):
    monkeypatch.setattr(task_routes, "workbench_from_env", lambda: None)

    with TestClient(app) as client:
        task_id = create_task(client)
        export_id = export_lessons(client, task_id, tmp_path)
        refused = client.post(f"/tasks/{task_id}/exports/{export_id}/push-to-workbench")

    assert refused.status_code == 404
    assert "未配置" in refused.json()["detail"]
