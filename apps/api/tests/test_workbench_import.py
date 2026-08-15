import json

import httpx
import pytest

from app.services.workbench_import import (
    Workbench,
    WorkbenchError,
    push_document,
    owned_by,
    workbench_from_env,
)


def _workbench() -> Workbench:
    return Workbench(base_url="https://workbench.example", token="tok-private", owner_employee_no="1001")


def _transport(handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def _push(handler, **overrides):
    return push_document(
        _workbench(),
        external_id=overrides.pop("external_id", "task-1-lesson"),
        title=overrides.pop("title", "移动终端APP设计 整门课教案"),
        filename=overrides.pop("filename", "教案.docx"),
        content=overrides.pop("content", b"docx-bytes"),
        transport=_transport(handler),
        **overrides,
    )


FULL_ENV = {
    "WORKBENCH_BASE_URL": "https://workbench.example/",
    "WORKBENCH_IMPORT_TOKEN": "tok",
    "WORKBENCH_OWNER_EMPLOYEE_NO": "1001",
}


def test_configuration_is_all_or_nothing():
    assert workbench_from_env({}) is None
    assert workbench_from_env({"OTHER": "x"}) is None

    assert workbench_from_env(FULL_ENV) == Workbench(
        base_url="https://workbench.example", token="tok", owner_employee_no="1001"
    )

    # A partial configuration is an operations mistake; hiding the feature buries it.
    for missing in FULL_ENV:
        partial = {key: value for key, value in FULL_ENV.items() if key != missing}
        with pytest.raises(WorkbenchError, match="配置不完整") as failure:
            workbench_from_env(partial)
        assert missing in str(failure.value)


def test_the_workbench_belongs_to_exactly_one_employee_number():
    """Everyone else is told it is not configured -- whose it is, is not their business."""
    workbench = workbench_from_env(FULL_ENV)

    assert owned_by(workbench, "1001") is True
    assert owned_by(workbench, " 1001 ") is True
    assert owned_by(workbench, "2044") is False
    assert owned_by(workbench, "") is False
    assert owned_by(None, "1001") is False


def test_sends_the_document_as_the_workbench_contract_expects():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = request.content
        return httpx.Response(201, json={"id": "abc", "status": "RECEIVED", "created": True})

    result = _push(handler, course_name="移动终端APP设计", finished_at="2026-08-08", note="2025-2026 第二学期")

    assert seen["url"] == "https://workbench.example/api/teaching/import"
    assert seen["auth"] == "Bearer tok-private"
    body = seen["body"]
    assert b'name="externalSystem"' in body and b"teaching-design-system" in body
    assert b'name="externalId"' in body and b"task-1-lesson" in body
    assert b'name="courseName"' in body
    assert b'name="finishedAt"' in body and b"2026-08-08" in body
    assert b'filename="\xe6\x95\x99\xe6\xa1\x88.docx"' in body or b"docx" in body
    assert b"docx-bytes" in body
    assert result == {"id": "abc", "status": "RECEIVED", "created": True, "replaced": False}


def test_blank_optional_fields_are_left_out_rather_than_sent_empty():
    """The workbench rejects a blank finishedAt: it only accepts YYYY-MM-DD."""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.content
        return httpx.Response(200, json={"id": "abc", "status": "RECEIVED", "created": False, "replaced": True})

    result = _push(handler)

    assert b'name="finishedAt"' not in seen["body"]
    assert b'name="courseName"' not in seen["body"]
    assert b'name="term"' not in seen["body"]
    assert result["replaced"] is True


def test_the_semester_travels_as_its_own_field():
    """一门课教了几个学期，正是要分开看的东西。

    学期本来就在 `note` 里，但那是拼给人读的一整串（学期 · 班级 · 摘要），
    工作台没法拿它分组或排序。所以单独送一份。
    """
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = request.content
        return httpx.Response(201, json={"id": "abc", "status": "RECEIVED", "created": True})

    _push(handler, term="2025-2026 第二学期")

    assert b'name="term"' in seen["body"]
    assert "2025-2026 第二学期".encode() in seen["body"]


@pytest.mark.parametrize(
    ("status", "payload", "expected"),
    [
        (401, {"error": "unauthorized"}, "TEACHING_IMPORT_TOKEN"),
        (409, {"error": "该教案已引用为成果，请先在工作台取消引用再重新推送"}, "取消引用"),
        (413, {"error": "文件超过 20MB 上限"}, "大小上限"),
        (400, {"error": "载荷不合法", "issues": ["教案标题最多 200 个字符"]}, "最多 200 个字符"),
        (404, {"error": "not found"}, "工作台根地址"),
    ],
)
def test_每种拒绝都说清了下一步(status, payload, expected):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=payload)

    with pytest.raises(WorkbenchError) as failure:
        _push(handler)

    assert expected in str(failure.value)
    assert f"HTTP {status}" in str(failure.value)


def test_a_login_page_points_at_the_address_not_the_payload():
    """Pointing the base url at the web app returns its login page, not JSON."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="<!doctype html><title>登录 · 教师工作台</title>",
            headers={"content-type": "text/html; charset=utf-8"},
        )

    with pytest.raises(WorkbenchError, match="text/html"):
        _push(handler)


def test_an_unreachable_workbench_names_the_transport_fault():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("nope", request=request)

    with pytest.raises(WorkbenchError, match="无法连接工作台"):
        _push(handler)


def test_a_rejection_that_echoes_the_request_never_reveals_the_token():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": json.dumps({"authorization": "Bearer tok-private"})})

    with pytest.raises(WorkbenchError) as failure:
        _push(handler)

    assert "tok-private" not in str(failure.value)
    assert "***" in str(failure.value)
