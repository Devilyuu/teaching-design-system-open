import os

from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

from app.db import engine, engine_url
from app.main import app


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/auth/login", json={"employee_no": "admin", "password": "Admin@2026!"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_tests_use_configured_temporary_database():
    """Whatever DATABASE_URL names, and nothing else -- never a real database.

    Compared piece by piece rather than as a string: a bare postgresql:// URL is
    rewritten to name its driver, and SQLAlchemy masks the password in str().
    """
    configured = make_url(engine_url(os.environ["DATABASE_URL"]))

    assert engine.url.database == configured.database
    assert engine.url.host == configured.host
    assert engine.url.drivername == configured.drivername


def test_health_endpoint_returns_ok():
    with TestClient(app) as client:
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_cors_allows_vite_localhost_origin():
    with TestClient(app) as client:
        response = client.options(
            "/health",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_cors_allows_visible_codex_preview_origin():
    with TestClient(app) as client:
        for origin in ("http://localhost:54536", "http://127.0.0.1:54536"):
            response = client.options(
                "/health",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "GET",
                },
            )

            assert response.status_code == 200
            assert response.headers["access-control-allow-origin"] == origin


def test_cors_exposes_download_filename_header():
    with TestClient(app) as client:
        response = client.get(
            "/health",
            headers={"Origin": "http://127.0.0.1:5173"},
        )

        assert "Content-Disposition" in response.headers["access-control-expose-headers"]


def test_create_task_endpoint_returns_created_task():
    with TestClient(app) as client:
        response = client.post(
            "/tasks",
            headers=auth_headers(client),
            json={
                "term": "2026-2027 第一学期",
                "major": "数字媒体艺术设计",
                "class_name": "数字艺术25级1班",
                "course_name": "人工智能与创意设计",
                "teacher_name": "张明",
                "location": "智慧教室",
                "total_hours": 32,
                "hours_per_session": 4,
            },
        )

        assert response.status_code == 200
        assert response.json()["course_name"] == "人工智能与创意设计"
        assert response.json()["status"] == "materials_pending"


def test_create_task_normalises_the_semester():
    """表单上的下拉管不住直接调 API 的路径，所以收口在路由这一层。

    线上真的出现过 `2025-2026第二学期` 和 `2025-2026 第二学期` 两条记录指同一个
    学期——学期是要拿来分组和排序的，两种写法就是两格。
    """
    with TestClient(app) as client:
        response = client.post(
            "/tasks",
            headers=auth_headers(client),
            json={
                "term": "2025-2026第二学期",
                "major": "数字媒体艺术设计",
                "class_name": "数字艺术25级1班",
                "course_name": "人工智能与创意设计",
                "teacher_name": "张明",
                "location": "智慧教室",
                "total_hours": 32,
                "hours_per_session": 4,
            },
        )

        assert response.status_code == 200
        assert response.json()["term"] == "2025-2026 第二学期"
