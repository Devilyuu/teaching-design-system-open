import json
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook
import pytest

from app.main import app
from app.routes import tasks as task_routes


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post("/auth/login", json={"employee_no": "admin", "password": "Admin@2026!"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_task(client: TestClient) -> int:
    client.headers.update(auth_headers(client))
    response = client.post(
        "/tasks",
        json={
            "term": "2026-2027 第一学期",
            "major": "数字媒体艺术设计",
            "class_name": "数字艺术25级1班",
            "course_name": "人工智能与创意设计",
            "teacher_name": "张明",
            "location": "智慧教室",
            "total_hours": 8,
            "hours_per_session": 4,
        },
    )
    assert response.status_code == 200
    return response.json()["id"]


def write_rows(path: Path, rows: list[list]) -> None:
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    wb.save(path)


def make_registrar_xlsx(path: Path) -> None:
    write_rows(
        path,
        [
            ["某职业技术学院 2026-2027 学年第一学期任课表"],
            ["教师：张明"],
            ["教学周", "上课日期", "星期几", "节次", "课程名称", "教学班", "上课教室", "任课教师"],
            [1, "2026-09-07", "星期一", "第1-4节", "人工智能与创意设计", "数字艺术25级1班", "实训楼A301", "张明"],
            [2, "2026-09-14", "星期一", "第1-4节", "人工智能与创意设计", "数字艺术25级1班", "实训楼A301", "张明"],
        ],
    )


@pytest.fixture(autouse=True)
def isolate_task_files(tmp_path, monkeypatch):
    monkeypatch.setattr(task_routes, "TASK_FILE_DIR", tmp_path / "task-files")


def stub_registrar_matrix(monkeypatch) -> None:
    """Serve the registrar's matrix without writing a real OLE2 .xls.

    Reading the binary is xlrd's job and is covered against the school's own
    file; what needs a test here is that a chosen teaching class survives the
    trip from the form field down to the parser.
    """
    from app.services import registrar_schedule

    entry = "{course}/(1-4节)1-2周/实训楼A301/张明/{code}//数字艺术2431/ /多媒体"
    matrix = [
        ["某职业技术学院 2026-2027 学年第一学期任课表"],
        ["星期一", "星期二", "星期三"],
        [
            entry.format(course="人工智能与创意设计", code="人工智能与创意设计-0001"),
            entry.format(course="人工智能与创意设计", code="人工智能与创意设计-0002"),
            # A teacher's timetable carries their other courses too.
            entry.format(course="劳动教育", code="劳动教育-0095"),
        ],
        ["本学期 2026-09-07 正式上课，2027-01-22 结束，共 20 周"],
    ]
    monkeypatch.setattr(registrar_schedule, "read_xls_matrix", lambda path: matrix)


def test_registrar_xls_offers_its_teaching_classes_and_merges_them_until_one_is_chosen(tmp_path, monkeypatch):
    stub_registrar_matrix(monkeypatch)
    path = tmp_path / "1001课表.xls"
    path.write_bytes(b"stub")

    with TestClient(app) as client:
        task_id = create_task(client)
        with path.open("rb") as file:
            response = client.post(
                f"/tasks/{task_id}/schedule-candidates",
                files={"file": ("1001课表.xls", file)},
            )

    assert response.status_code == 200
    body = response.json()
    # 劳动教育-0095 is on the same timetable but another course; offering it
    # would only ever parse to an empty schedule.
    assert body["teaching_classes"] == ["人工智能与创意设计-0001", "人工智能与创意设计-0002"]
    assert body["teaching_class"] == ""
    # Both classes are still in there -- two weeks each -- and the teacher is
    # told so rather than left to notice the doubled session count.
    assert body["session_count"] == 4
    assert any("多个教学班" in warning for warning in body["warnings"])


def test_choosing_a_teaching_class_reparses_the_stored_registrar_file(tmp_path, monkeypatch):
    stub_registrar_matrix(monkeypatch)
    path = tmp_path / "1001课表.xls"
    path.write_bytes(b"stub")

    with TestClient(app) as client:
        task_id = create_task(client)
        with path.open("rb") as file:
            created = client.post(
                f"/tasks/{task_id}/schedule-candidates",
                files={"file": ("1001课表.xls", file)},
            )
        candidate_id = created.json()["id"]
        response = client.post(
            f"/tasks/{task_id}/schedule-candidates/{candidate_id}/remap",
            json={"teaching_class": "人工智能与创意设计-0002"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["teaching_class"] == "人工智能与创意设计-0002"
    assert body["session_count"] == 2
    # -0002 is the 星期二 column, so the dates move with the choice.
    assert [item["weekday"] for item in body["sessions"]] == ["二", "二"]
    assert [item["date_text"] for item in body["sessions"]] == ["2026-09-08", "2026-09-15"]
    assert not any("多个教学班" in warning for warning in body["warnings"])


def test_a_later_remap_keeps_the_teaching_class_already_chosen(tmp_path, monkeypatch):
    """Omitting the field must not silently widen the schedule back to both classes."""
    stub_registrar_matrix(monkeypatch)
    path = tmp_path / "1001课表.xls"
    path.write_bytes(b"stub")

    with TestClient(app) as client:
        task_id = create_task(client)
        with path.open("rb") as file:
            created = client.post(
                f"/tasks/{task_id}/schedule-candidates",
                files={"file": ("1001课表.xls", file)},
            )
        candidate_id = created.json()["id"]
        client.post(
            f"/tasks/{task_id}/schedule-candidates/{candidate_id}/remap",
            json={"teaching_class": "人工智能与创意设计-0001"},
        )
        response = client.post(
            f"/tasks/{task_id}/schedule-candidates/{candidate_id}/remap",
            json={"course_name": "人工智能与创意设计"},
        )

    assert response.status_code == 200
    assert response.json()["teaching_class"] == "人工智能与创意设计-0001"
    assert response.json()["session_count"] == 2


def test_schedule_candidate_exposes_detected_column_mapping(tmp_path):
    path = tmp_path / "registrar.xlsx"
    make_registrar_xlsx(path)

    with TestClient(app) as client:
        task_id = create_task(client)
        with path.open("rb") as file:
            response = client.post(
                f"/tasks/{task_id}/schedule-candidates",
                files={"file": ("registrar.xlsx", file)},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["header_row"] == 2
    assert body["session_count"] == 2
    mapped = {item["field"]: item["header_text"] for item in body["matches"]}
    assert mapped["periods"] == "节次"
    assert mapped["class_name"] == "教学班"
    assert mapped["location"] == "上课教室"
    assert body["unmapped_headers"] == ["任课教师"]
    assert body["course_names"] == ["人工智能与创意设计"]
    assert [item["session_no"] for item in body["sessions"]] == [1, 2]
    assert body["sessions"][0]["periods"] == "1-4"
    assert body["sessions"][0]["weekday"] == "一"
    assert body["sessions"][0]["location"] == "实训楼A301"


def test_schedule_candidate_keeps_only_the_task_course(tmp_path):
    path = tmp_path / "whole-timetable.xlsx"
    write_rows(
        path,
        [
            ["周次", "日期", "星期", "节次", "课程", "班级", "地点"],
            [1, "2026-09-07", "一", "1-4", "人工智能与创意设计", "数字艺术25级1班", "智慧教室"],
            [1, "2026-09-08", "二", "1-2", "版式设计", "数字艺术25级2班", "A302"],
            [2, "2026-09-14", "一", "1-4", "人工智能与创意设计", "数字艺术25级1班", "智慧教室"],
        ],
    )

    with TestClient(app) as client:
        task_id = create_task(client)
        with path.open("rb") as file:
            response = client.post(
                f"/tasks/{task_id}/schedule-candidates",
                files={"file": ("whole-timetable.xlsx", file)},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["session_count"] == 2
    assert body["course_names"] == ["人工智能与创意设计", "版式设计"]
    assert body["course_filter"] == "人工智能与创意设计"


def test_schedule_upload_reports_detected_headers_when_mapping_fails(tmp_path):
    path = tmp_path / "noperiods.xlsx"
    write_rows(
        path,
        [
            ["周次", "日期", "星期", "课程", "班级", "地点"],
            [1, "2026-09-07", "一", "人工智能与创意设计", "数字艺术25级1班", "智慧教室"],
        ],
    )

    with TestClient(app) as client:
        task_id = create_task(client)
        with path.open("rb") as file:
            response = client.post(
                f"/tasks/{task_id}/schedule-candidates",
                files={"file": ("noperiods.xlsx", file)},
            )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["missing_fields"] == ["periods"]
    assert detail["detected_headers"] == ["周次", "日期", "星期", "课程", "班级", "地点"]
    assert "节次" in detail["message"]


def test_schedule_upload_accepts_a_manual_column_mapping(tmp_path):
    path = tmp_path / "opaque.xlsx"
    write_rows(
        path,
        [
            ["第几周", "什么时候", "礼拜", "第几节", "上什么课", "哪个班", "在哪上"],
            [1, "2026-09-07", "一", "1-4", "人工智能与创意设计", "数字艺术25级1班", "智慧教室"],
        ],
    )
    mapping = {
        "week_no": 0,
        "date_text": 1,
        "weekday": 2,
        "periods": 3,
        "course_name": 4,
        "class_name": 5,
        "location": 6,
    }

    with TestClient(app) as client:
        task_id = create_task(client)
        with path.open("rb") as file:
            response = client.post(
                f"/tasks/{task_id}/schedule-candidates",
                files={"file": ("opaque.xlsx", file)},
                data={"header_row": "0", "mapping": json.dumps(mapping)},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["session_count"] == 1
    assert all(item["confidence"] == "manual" for item in body["matches"])
    assert body["changes"][0]["after"]["location"] == "智慧教室"


def test_schedule_candidate_can_be_remapped_before_confirming(tmp_path):
    path = tmp_path / "swapped.xlsx"
    write_rows(
        path,
        [
            ["周次", "日期", "星期", "节次", "课程", "班级", "地点"],
            [1, "2026-09-07", "一", "1-4", "人工智能与创意设计", "数字艺术25级1班", "智慧教室"],
        ],
    )

    with TestClient(app) as client:
        task_id = create_task(client)
        with path.open("rb") as file:
            created = client.post(
                f"/tasks/{task_id}/schedule-candidates",
                files={"file": ("swapped.xlsx", file)},
            )
        assert created.status_code == 200
        candidate_id = created.json()["id"]
        response = client.post(
            f"/tasks/{task_id}/schedule-candidates/{candidate_id}/remap",
            json={
                "header_row": 0,
                "mapping": {
                    "week_no": 0,
                    "date_text": 1,
                    "weekday": 2,
                    "periods": 3,
                    "course_name": 4,
                    "class_name": 6,
                    "location": 5,
                },
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == candidate_id
    assert body["status"] == "pending"
    assert body["changes"][0]["after"]["class_name"] == "智慧教室"
    assert body["changes"][0]["after"]["location"] == "数字艺术25级1班"


def test_remap_rejects_a_mapping_that_cannot_be_parsed(tmp_path):
    path = tmp_path / "plain.xlsx"
    write_rows(
        path,
        [
            ["周次", "日期", "星期", "节次", "课程", "班级", "地点"],
            [1, "2026-09-07", "一", "1-4", "人工智能与创意设计", "数字艺术25级1班", "智慧教室"],
        ],
    )

    with TestClient(app) as client:
        task_id = create_task(client)
        with path.open("rb") as file:
            created = client.post(
                f"/tasks/{task_id}/schedule-candidates",
                files={"file": ("plain.xlsx", file)},
            )
        candidate_id = created.json()["id"]
        response = client.post(
            f"/tasks/{task_id}/schedule-candidates/{candidate_id}/remap",
            json={"header_row": 0, "mapping": {"week_no": 0, "date_text": 1}},
        )

    assert response.status_code == 400
    assert response.json()["detail"]["missing_fields"] == ["periods"]


def test_names_the_courses_on_the_sheet_when_none_matches_the_task(tmp_path):
    """课程名对不上时，报错要把课表里的课程列出来，教师才有下一步可走。"""
    path = tmp_path / "schedule.xlsx"
    write_rows(
        path,
        [
            ["教学周", "上课日期", "星期几", "节次", "课程名称", "教学班", "上课教室"],
            [1, "2026-09-07", "星期一", "第1-4节", "版式设计", "数字艺术25级1班", "A301"],
            [2, "2026-09-14", "星期一", "第1-4节", "劳动教育", "数字艺术25级1班", "操场"],
        ],
    )
    with TestClient(app) as client:
        task_id = create_task(client)
        with path.open("rb") as handle:
            response = client.post(
                f"/tasks/{task_id}/schedule-candidates",
                files={"file": ("schedule.xlsx", handle, "application/octet-stream")},
            )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["course_names"] == ["版式设计", "劳动教育"]
    assert "人工智能与创意设计" in detail["message"]
    assert "版式设计" in detail["message"]


def test_accepts_a_course_chosen_from_the_sheet(tmp_path):
    path = tmp_path / "schedule.xlsx"
    write_rows(
        path,
        [
            ["教学周", "上课日期", "星期几", "节次", "课程名称", "教学班", "上课教室"],
            [1, "2026-09-07", "星期一", "第1-4节", "版式设计", "数字艺术25级1班", "A301"],
            [2, "2026-09-14", "星期一", "第1-4节", "劳动教育", "数字艺术25级1班", "操场"],
        ],
    )
    with TestClient(app) as client:
        task_id = create_task(client)
        with path.open("rb") as handle:
            response = client.post(
                f"/tasks/{task_id}/schedule-candidates",
                data={"course_name": "版式设计"},
                files={"file": ("schedule.xlsx", handle, "application/octet-stream")},
            )

    assert response.status_code == 200
    assert response.json()["session_count"] == 1
    assert response.json()["course_filter"] == "版式设计"
