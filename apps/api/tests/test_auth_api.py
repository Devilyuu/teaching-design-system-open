from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def auth_headers(client: TestClient, employee_no: str = "admin", password: str = "Admin@2026!") -> dict[str, str]:
    response = client.post("/auth/login", json={"employee_no": employee_no, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_teacher(client: TestClient, password: str = "Teacher@2026!") -> str:
    suffix = uuid4().hex[:8]
    response = client.post(
        "/admin/users",
        json={
            "employee_no": f"P{suffix}",
            "name": "密码测试教师",
            "password": password,
            "role": "teacher",
            "major_ids": [],
            "is_active": True,
        },
        headers=auth_headers(client),
    )
    assert response.status_code == 200
    return response.json()["employee_no"]


def test_default_admin_can_login_and_read_current_user():
    with TestClient(app) as client:
        response = client.post(
            "/auth/login",
            json={"employee_no": "admin", "password": "Admin@2026!"},
        )

        assert response.status_code == 200
        token = response.json()["access_token"]

        me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert me.status_code == 200
    assert me.json()["employee_no"] == "admin"
    assert me.json()["role"] == "admin"
    assert me.json()["is_active"] is True


def test_login_rejects_wrong_password():
    with TestClient(app) as client:
        response = client.post(
            "/auth/login",
            json={"employee_no": "admin", "password": "wrong-password"},
        )

    assert response.status_code == 401


def test_current_user_requires_valid_token():
    with TestClient(app) as client:
        response = client.get("/auth/me", headers={"Authorization": "Bearer bad-token"})

    assert response.status_code == 401


def test_user_can_change_own_password_and_old_password_stops_working():
    with TestClient(app) as client:
        employee_no = create_teacher(client)
        teacher_headers = auth_headers(client, employee_no, "Teacher@2026!")

        response = client.post(
            "/auth/change-password",
            json={"current_password": "Teacher@2026!", "new_password": "Changed@2026!"},
            headers=teacher_headers,
        )
        old_login = client.post(
            "/auth/login",
            json={"employee_no": employee_no, "password": "Teacher@2026!"},
        )
        new_login = client.post(
            "/auth/login",
            json={"employee_no": employee_no, "password": "Changed@2026!"},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert old_login.status_code == 401
    assert new_login.status_code == 200


def test_user_cannot_change_password_with_wrong_current_password():
    with TestClient(app) as client:
        employee_no = create_teacher(client)
        teacher_headers = auth_headers(client, employee_no, "Teacher@2026!")

        response = client.post(
            "/auth/change-password",
            json={"current_password": "wrong-password", "new_password": "Changed@2026!"},
            headers=teacher_headers,
        )

    assert response.status_code == 400


def test_profile_starts_empty_and_gates_until_every_line_is_filled():
    with TestClient(app) as client:
        employee_no = create_teacher(client)
        headers = auth_headers(client, employee_no, "Teacher@2026!")

        assert client.get("/auth/me", headers=headers).json()["profile_complete"] is False
        profile = client.get("/auth/profile", headers=headers).json()
        assert profile == {"name": "密码测试教师", "office_location": "", "phone": "", "bio": "", "complete": False}

        partial = client.put(
            "/auth/profile",
            json={"office_location": "信息楼316", "phone": "", "bio": ""},
            headers=headers,
        )
        assert partial.status_code == 400
        assert "联系电话" in partial.json()["detail"] and "教师简介" in partial.json()["detail"]
        assert client.get("/auth/me", headers=headers).json()["profile_complete"] is False

        saved = client.put(
            "/auth/profile",
            json={"office_location": " 信息楼 316 ", "phone": "13800000000", "bio": "张明，讲师。\n研究方向为数字媒体。\n\n"},
            headers=headers,
        )
        assert saved.status_code == 200
        assert saved.json()["office_location"] == "信息楼 316"
        assert saved.json()["bio"] == "张明，讲师。\n研究方向为数字媒体。"
        assert saved.json()["complete"] is True
        assert client.get("/auth/me", headers=headers).json()["profile_complete"] is True


def test_profile_is_private_to_its_owner():
    with TestClient(app) as client:
        first = auth_headers(client, create_teacher(client), "Teacher@2026!")
        second = auth_headers(client, create_teacher(client), "Teacher@2026!")
        client.put("/auth/profile", json={"office_location": "A", "phone": "1", "bio": "b"}, headers=first)

        assert client.get("/auth/profile", headers=second).json()["complete"] is False
