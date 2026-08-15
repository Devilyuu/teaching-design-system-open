"""Send a finished document to the teacher's own workbench (课题罗盘).

The workbench files one record per `externalId` and replaces it when the same
id arrives again, so the id names **the course and kind, not the export**: a
course is exported many times while its layout is settled and only the last one
is worth filing.

The workbench is one teacher's personal platform, and the pilot puts every
teacher on one deployment, so the configuration names its owner by employee
number. Without that, every teacher would be offered a button that files their
work into somebody else's platform.
"""

from collections.abc import Mapping
from dataclasses import dataclass
import os

import httpx


WORKBENCH_SYSTEM = "teaching-design-system"
IMPORT_PATH = "/api/teaching/import"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class WorkbenchError(RuntimeError):
    pass


SETTINGS = ("WORKBENCH_BASE_URL", "WORKBENCH_IMPORT_TOKEN", "WORKBENCH_OWNER_EMPLOYEE_NO")


@dataclass(frozen=True)
class Workbench:
    base_url: str
    token: str
    owner_employee_no: str


def workbench_from_env(env: Mapping[str, str] | None = None) -> Workbench | None:
    """All three or none -- a partial configuration is an operations mistake.

    Returning None for "not configured" and raising for "configured wrong" keeps
    the two apart: the first hides the feature, the second has to be seen. The
    owner is not optional: an address and a token with nobody named would offer
    every teacher on the deployment a button into one person's platform.
    """
    source = os.environ if env is None else env
    values = {name: (source.get(name) or "").strip() for name in SETTINGS}
    values["WORKBENCH_BASE_URL"] = values["WORKBENCH_BASE_URL"].rstrip("/")
    if not any(values.values()):
        return None
    missing = [name for name in SETTINGS if not values[name]]
    if missing:
        raise WorkbenchError("工作台回流配置不完整：" + "、".join(missing) + " 必须一并设置")
    return Workbench(
        base_url=values["WORKBENCH_BASE_URL"],
        token=values["WORKBENCH_IMPORT_TOKEN"],
        owner_employee_no=values["WORKBENCH_OWNER_EMPLOYEE_NO"],
    )


def owned_by(workbench: Workbench | None, employee_no: str) -> bool:
    """Whether this deployment's workbench belongs to this teacher.

    Everyone else is told the feature is not configured rather than that it
    belongs to someone: whose platform it is, is none of their business.
    """
    return workbench is not None and workbench.owner_employee_no == (employee_no or "").strip()


def push_document(
    workbench: Workbench,
    *,
    external_id: str,
    title: str,
    filename: str,
    content: bytes,
    course_name: str = "",
    term: str = "",
    finished_at: str = "",
    note: str = "",
    transport: httpx.BaseTransport | None = None,
) -> dict:
    fields = {
        "externalSystem": WORKBENCH_SYSTEM,
        "externalId": external_id,
        "title": title,
    }
    # term 是可选的：老工作台不认这个字段会忽略它，值为空时干脆不送。
    for key, value in (
        ("courseName", course_name),
        ("term", term),
        ("finishedAt", finished_at),
        ("note", note),
    ):
        if value:
            fields[key] = value

    try:
        with httpx.Client(transport=transport, timeout=60) as client:
            response = client.post(
                f"{workbench.base_url}{IMPORT_PATH}",
                headers={"Authorization": f"Bearer {workbench.token}"},
                data=fields,
                files={"file": (filename, content, DOCX_MIME)},
            )
    except httpx.HTTPError as exc:
        raise WorkbenchError(f"无法连接工作台（{type(exc).__name__}）") from exc

    if response.status_code not in (200, 201):
        raise WorkbenchError(_rejection(response, workbench.token))

    body = _body(response)
    return {
        "id": str(body.get("id") or ""),
        "status": str(body.get("status") or ""),
        "created": bool(body.get("created")),
        "replaced": bool(body.get("replaced")),
    }


def _body(response) -> dict:
    """The workbench answers JSON on every documented path.

    Anything else means the address is not the import endpoint -- most often it
    points at the workbench's web app, whose proxy answers an unauthenticated
    call with its login page rather than a 401.
    """
    try:
        parsed = response.json()
    except ValueError as exc:
        kind = response.headers.get("content-type", "").split(";")[0].strip() or "未知类型"
        raise WorkbenchError(
            f"工作台返回的是 {kind} 而不是 JSON，"
            "请确认 WORKBENCH_BASE_URL 填的是工作台地址本身（不带 /api/teaching/import）"
        ) from exc
    return parsed if isinstance(parsed, dict) else {}


def _rejection(response, secret: str) -> str:
    hints = {
        400: "工作台认为载荷不合法",
        401: "工作台不接受这个令牌，请确认它与工作台的 TEACHING_IMPORT_TOKEN 一致",
        404: "工作台没有这个接口，请确认地址填的是工作台根地址",
        409: "这份教案已在工作台引用为成果，请先在工作台取消引用再重新推送",
        413: "文件超过工作台的大小上限",
    }
    hint = hints.get(response.status_code, "工作台拒绝了这次回流")
    detail = ""
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        parts = [str(body.get("error") or "")]
        issues = body.get("issues")
        if isinstance(issues, list):
            parts.extend(str(issue) for issue in issues)
        detail = "；".join(part for part in parts if part and part != "unauthorized")
    if not detail:
        detail = response.text[:200].strip()
    detail = detail.replace(secret, "***") if secret else detail
    return f"HTTP {response.status_code}：{hint}" + (f"（{detail}）" if detail else "")
