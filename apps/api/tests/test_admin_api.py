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


def test_new_account_defaults_to_employee_number_password_until_changed():
    suffix = uuid4().hex[:8]
    employee_no = f"D{suffix}"
    with TestClient(app) as client:
        admin_headers = auth_headers(client)
        created = client.post(
            "/admin/users",
            json={"employee_no": employee_no, "name": "默认密码教师"},
            headers=admin_headers,
        )
        assert created.status_code == 200
        assert created.json()["must_change_password"] is True

        teacher_headers = auth_headers(client, employee_no, employee_no)
        me_before = client.get("/auth/me", headers=teacher_headers)
        same_as_employee_no = client.post(
            "/auth/change-password",
            json={"current_password": employee_no, "new_password": employee_no},
            headers=teacher_headers,
        )
        too_short = client.post(
            "/auth/change-password",
            json={"current_password": employee_no, "new_password": "short"},
            headers=teacher_headers,
        )
        changed = client.post(
            "/auth/change-password",
            json={"current_password": employee_no, "new_password": "Mine@2026!"},
            headers=teacher_headers,
        )
        me_after = client.get("/auth/me", headers=teacher_headers)

    assert me_before.json()["must_change_password"] is True
    assert same_as_employee_no.status_code == 400
    assert too_short.status_code == 400
    assert changed.status_code == 200
    assert me_after.json()["must_change_password"] is False


def test_batch_import_creates_teachers_and_skips_existing_numbers():
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        admin_headers = auth_headers(client)
        major = client.post("/admin/majors", json={"name": f"批量导入专业-{suffix}"}, headers=admin_headers)
        major_id = major.json()["id"]
        existing = client.post(
            "/admin/users",
            json={"employee_no": f"E{suffix}", "name": "已有教师"},
            headers=admin_headers,
        )
        assert existing.status_code == 200

        result = client.post(
            "/admin/users/batch",
            json={
                "items": [
                    {"employee_no": f"N1{suffix}", "name": "张明"},
                    {"employee_no": f" N2{suffix} ", "name": "李华 "},
                    {"employee_no": f"N1{suffix}", "name": "张明（重复行）"},
                    {"employee_no": f"E{suffix}", "name": "已有教师"},
                ],
                "major_ids": [major_id],
            },
            headers=admin_headers,
        )
        assert result.status_code == 200
        body = result.json()

        second_headers = auth_headers(client, f"N2{suffix}", f"N2{suffix}")
        second_majors = client.get("/majors", headers=second_headers)

    assert [user["employee_no"] for user in body["created"]] == [f"N1{suffix}", f"N2{suffix}"]
    assert body["created"][1]["name"] == "李华"
    assert all(user["must_change_password"] for user in body["created"])
    assert body["skipped"] == [f"N1{suffix}", f"E{suffix}"]
    assert [major["id"] for major in second_majors.json()] == [major_id]


def test_batch_import_rejects_rows_missing_a_name():
    suffix = uuid4().hex[:8]
    with TestClient(app) as client:
        admin_headers = auth_headers(client)
        result = client.post(
            "/admin/users/batch",
            json={"items": [{"employee_no": f"X{suffix}", "name": "  "}], "major_ids": []},
            headers=admin_headers,
        )
        listed = client.get("/admin/users", headers=admin_headers)

    assert result.status_code == 400
    assert f"X{suffix}" not in {user["employee_no"] for user in listed.json()}


def test_admin_can_deactivate_rename_and_rebind_majors_but_not_deactivate_self():
    suffix = uuid4().hex[:8]
    employee_no = f"U{suffix}"
    with TestClient(app) as client:
        admin_headers = auth_headers(client)
        major = client.post("/admin/majors", json={"name": f"改绑专业-{suffix}"}, headers=admin_headers)
        teacher = client.post(
            "/admin/users",
            json={"employee_no": employee_no, "name": "待改名"},
            headers=admin_headers,
        )
        teacher_id = teacher.json()["id"]

        renamed = client.patch(
            f"/admin/users/{teacher_id}",
            json={"name": "已改名", "major_ids": [major.json()["id"]]},
            headers=admin_headers,
        )
        deactivated = client.patch(f"/admin/users/{teacher_id}", json={"is_active": False}, headers=admin_headers)
        login_while_inactive = client.post("/auth/login", json={"employee_no": employee_no, "password": employee_no})
        reactivated = client.patch(f"/admin/users/{teacher_id}", json={"is_active": True}, headers=admin_headers)
        login_after = client.post("/auth/login", json={"employee_no": employee_no, "password": employee_no})

        admin_me = client.get("/auth/me", headers=admin_headers).json()
        self_deactivate = client.patch(f"/admin/users/{admin_me['id']}", json={"is_active": False}, headers=admin_headers)

    assert renamed.status_code == 200
    assert renamed.json()["name"] == "已改名"
    assert renamed.json()["major_ids"] == [major.json()["id"]]
    assert deactivated.json()["is_active"] is False
    assert login_while_inactive.status_code == 401
    assert reactivated.json()["is_active"] is True
    assert login_after.status_code == 200
    assert self_deactivate.status_code == 400


def test_reset_with_empty_password_falls_back_to_employee_number():
    suffix = uuid4().hex[:8]
    employee_no = f"F{suffix}"
    with TestClient(app) as client:
        admin_headers = auth_headers(client)
        teacher = client.post(
            "/admin/users",
            json={"employee_no": employee_no, "name": "忘记密码教师", "password": "Chosen@2026!"},
            headers=admin_headers,
        )
        teacher_headers = auth_headers(client, employee_no, "Chosen@2026!")
        client.post(
            "/auth/change-password",
            json={"current_password": "Chosen@2026!", "new_password": "Forgotten@2026!"},
            headers=teacher_headers,
        )

        reset = client.post(f"/admin/users/{teacher.json()['id']}/password", json={"password": ""}, headers=admin_headers)
        too_short = client.post(f"/admin/users/{teacher.json()['id']}/password", json={"password": "abc"}, headers=admin_headers)
        login = client.post("/auth/login", json={"employee_no": employee_no, "password": employee_no})
        me = client.get("/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"})

    assert reset.status_code == 200
    assert too_short.status_code == 400
    assert login.status_code == 200
    assert me.json()["must_change_password"] is True
