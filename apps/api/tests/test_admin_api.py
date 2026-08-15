from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def auth_headers(client: TestClient, employee_no: str = "admin", password: str = "Admin@2026!") -> dict[str, str]:
    response = client.post("/auth/login", json={"employee_no": employee_no, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_task_payload(major: str = "数字媒体艺术设计") -> dict:
    return {
        "term": "2026-2027 第一学期",
        "major": major,
        "class_name": "数字艺术 2501",
        "course_name": "人工智能与创意设计",
        "teacher_name": "临时教师",
        "location": "智慧教室",
        "total_hours": 32,
        "hours_per_session": 4,
    }


def test_admin_can_create_major_and_teacher_with_employee_number_login():
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        admin_headers = auth_headers(client)
        major_response = client.post(
            "/admin/majors",
            json={"name": f"数字媒体艺术设计-{suffix}", "short_name": "数媒"},
            headers=admin_headers,
        )
        assert major_response.status_code == 200
        major_id = major_response.json()["id"]

        user_response = client.post(
            "/admin/users",
            json={
                "employee_no": f"T{suffix}",
                "name": "张老师",
                "password": "Teacher@2026!",
                "role": "teacher",
                "major_ids": [major_id],
                "is_active": True,
            },
            headers=admin_headers,
        )
        assert user_response.status_code == 200

        teacher_headers = auth_headers(client, f"T{suffix}", "Teacher@2026!")
        me = client.get("/auth/me", headers=teacher_headers)
        majors = client.get("/majors", headers=teacher_headers)

    assert me.status_code == 200
    assert me.json()["employee_no"] == f"T{suffix}"
    assert me.json()["major_ids"] == [major_id]
    assert majors.status_code == 200
    assert [major["id"] for major in majors.json()] == [major_id]


def test_teacher_only_sees_own_tasks_while_admin_sees_all_tasks():
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        admin_headers = auth_headers(client)
        first = client.post(
            "/admin/users",
            json={
                "employee_no": f"A{suffix}",
                "name": "甲老师",
                "password": "Teacher@2026!",
                "role": "teacher",
                "major_ids": [],
                "is_active": True,
            },
            headers=admin_headers,
        )
        second = client.post(
            "/admin/users",
            json={
                "employee_no": f"B{suffix}",
                "name": "乙老师",
                "password": "Teacher@2026!",
                "role": "teacher",
                "major_ids": [],
                "is_active": True,
            },
            headers=admin_headers,
        )
        assert first.status_code == 200
        assert second.status_code == 200

        first_headers = auth_headers(client, f"A{suffix}", "Teacher@2026!")
        second_headers = auth_headers(client, f"B{suffix}", "Teacher@2026!")
        first_task = client.post("/tasks", json=create_task_payload("视觉传达设计"), headers=first_headers)
        second_task = client.post("/tasks", json=create_task_payload("环境艺术设计"), headers=second_headers)
        assert first_task.status_code == 200
        assert second_task.status_code == 200

        first_tasks = client.get("/tasks", headers=first_headers)
        admin_tasks = client.get("/tasks", headers=admin_headers)
        forbidden = client.get(f"/tasks/{second_task.json()['id']}/outline", headers=first_headers)

    assert [task["id"] for task in first_tasks.json()] == [first_task.json()["id"]]
    assert first_task.json()["owner_id"] == first.json()["id"]
    assert {first_task.json()["id"], second_task.json()["id"]}.issubset({task["id"] for task in admin_tasks.json()})
    assert forbidden.status_code == 404


def test_admin_can_reset_teacher_password():
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        admin_headers = auth_headers(client)
        teacher = client.post(
            "/admin/users",
            json={
                "employee_no": f"R{suffix}",
                "name": "重置密码教师",
                "password": "Teacher@2026!",
                "role": "teacher",
                "major_ids": [],
                "is_active": True,
            },
            headers=admin_headers,
        )
        assert teacher.status_code == 200

        reset = client.post(
            f"/admin/users/{teacher.json()['id']}/password",
            json={"password": "Reset@2026!"},
            headers=admin_headers,
        )
        old_login = client.post(
            "/auth/login",
            json={"employee_no": f"R{suffix}", "password": "Teacher@2026!"},
        )
        new_login = client.post(
            "/auth/login",
            json={"employee_no": f"R{suffix}", "password": "Reset@2026!"},
        )

    assert reset.status_code == 200
    assert reset.json() == {"status": "ok"}
    assert old_login.status_code == 401
    assert new_login.status_code == 200
