from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db import engine, init_db
from app.main import app
from app.models import AiModelConfig
from app.services.ai_model_config import AiModelConnectionError
from app.services.ai_model_config import test_model_connection as check_model_connection
from app.services.secret_store import decrypt_secret, encrypt_secret, mask_secret


def test_model_api_key_is_encrypted_and_masked():
    encrypted = encrypt_secret("sk-private")

    assert encrypted != "sk-private"
    assert decrypt_secret(encrypted) == "sk-private"
    assert mask_secret("sk-private") == "已配置"
    assert mask_secret("") == "未配置"


def test_model_configuration_persists_only_encrypted_key():
    init_db()
    with Session(engine) as session:
        config = AiModelConfig(
            base_url="https://model.example/v1",
            model_name="lesson-model",
            encrypted_api_key=encrypt_secret("sk-private"),
        )
        session.add(config)
        session.commit()
        session.refresh(config)

        assert config.encrypted_api_key != "sk-private"
        assert decrypt_secret(config.encrypted_api_key) == "sk-private"


def _auth_headers(client: TestClient, employee_no: str = "admin", password: str = "Admin@2026!") -> dict[str, str]:
    response = client.post("/auth/login", json={"employee_no": employee_no, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _teacher_headers(client: TestClient) -> dict[str, str]:
    employee_no = f"AI{uuid4().hex[:8]}"
    admin_headers = _auth_headers(client)
    response = client.post(
        "/admin/users",
        headers=admin_headers,
        json={
            "employee_no": employee_no,
            "name": "模型测试教师",
            "password": "Teacher@2026!",
            "role": "teacher",
            "major_ids": [],
            "is_active": True,
        },
    )
    assert response.status_code == 200
    return _auth_headers(client, employee_no, "Teacher@2026!")


def test_admin_updates_model_configuration_without_exposing_secret():
    with TestClient(app) as client:
        admin_headers = _auth_headers(client)
        response = client.put(
            "/admin/ai-model",
            headers=admin_headers,
            json={
                "base_url": "https://model.example/v1/",
                "model_name": "lesson-model",
                "api_key": "sk-api-only",
            },
        )
        teacher_response = client.get("/admin/ai-model", headers=_teacher_headers(client))

    assert response.status_code == 200
    assert response.json()["base_url"] == "https://model.example/v1"
    assert response.json()["api_key_status"] == "已配置"
    assert response.json()["connection_status"] == "untested"
    assert response.json()["enabled"] is False
    assert "encrypted_api_key" not in response.json()
    assert teacher_response.status_code == 403


def test_model_configuration_must_connect_before_it_can_be_enabled(monkeypatch):
    with TestClient(app) as client:
        admin_headers = _auth_headers(client)
        client.put(
            "/admin/ai-model",
            headers=admin_headers,
            json={
                "base_url": "https://model.example/v1",
                "model_name": "lesson-model",
                "api_key": "sk-api-only",
            },
        )
        blocked = client.post("/admin/ai-model/enable", headers=admin_headers, json={"enabled": True})

        monkeypatch.setattr("app.routes.ai_config.test_model_connection", lambda _: None)
        tested = client.post("/admin/ai-model/test", headers=admin_headers)
        enabled = client.post("/admin/ai-model/enable", headers=admin_headers, json={"enabled": True})

    assert blocked.status_code == 409
    assert tested.status_code == 200
    assert tested.json()["connection_status"] == "connected"
    assert enabled.status_code == 200
    assert enabled.json()["enabled"] is True


def test_connection_check_allows_reasoning_model_to_finish(monkeypatch):
    def fake_post(url: str, **kwargs) -> httpx.Response:
        max_tokens = kwargs["json"]["max_tokens"]
        content = "" if max_tokens < 256 else '{"ping": true}'
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={
                "choices": [
                    {
                        "message": {"content": content, "reasoning_content": "thinking"},
                        "finish_reason": "length" if not content else "stop",
                    }
                ]
            },
        )

    monkeypatch.setattr("app.services.ai_model_config.httpx.post", fake_post)
    config = AiModelConfig(
        base_url="https://model.example/v1",
        model_name="reasoning-model",
        encrypted_api_key=encrypt_secret("sk-private"),
    )

    check_model_connection(config)


def _config() -> AiModelConfig:
    return AiModelConfig(
        base_url="https://model.example/v1",
        model_name="lesson-model",
        encrypted_api_key=encrypt_secret("sk-private"),
    )


def _fails_with(monkeypatch, outcome, headers: dict[str, str] | None = None) -> str:
    def fake_post(url: str, **kwargs):
        if isinstance(outcome, Exception):
            raise outcome
        return httpx.Response(
            outcome[0],
            request=httpx.Request("POST", url),
            text=outcome[1],
            headers=headers or {},
        )

    monkeypatch.setattr("app.services.ai_model_config.httpx.post", fake_post)
    with pytest.raises(AiModelConnectionError) as failure:
        check_model_connection(_config())
    return str(failure.value)


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        (httpx.ConnectError("nope"), "无法连接到接口地址"),
        (httpx.ReadTimeout("slow"), "请求超时"),
        ((401, "unauthorized"), "鉴权失败"),
        ((404, "not found"), "是否需要以 /v1 结尾"),
        ((400, "response_format unsupported"), "不支持 response_format"),
        ((429, "slow down"), "额度超限"),
        ((503, "upstream down"), "服务端错误"),
    ],
)
def test_connection_failures_say_which_leg_broke(monkeypatch, outcome, expected):
    """Pointing this at a new gateway is guesswork when every failure reads alike."""
    assert expected in _fails_with(monkeypatch, outcome)


def test_a_login_page_is_not_reported_as_a_bad_model_answer(monkeypatch):
    """A gateway behind a web app answers an unauthenticated call with HTML at 200."""
    message = _fails_with(
        monkeypatch,
        (200, "<!doctype html><title>登录</title>"),
        {"content-type": "text/html; charset=utf-8"},
    )

    assert "text/html" in message
    assert "重定向到登录页" in message


def test_a_gateway_that_echoes_the_request_never_reveals_the_key(monkeypatch):
    message = _fails_with(monkeypatch, (400, 'rejected: {"Authorization": "Bearer sk-private"}'))

    assert "sk-private" not in message
    assert "***" in message
