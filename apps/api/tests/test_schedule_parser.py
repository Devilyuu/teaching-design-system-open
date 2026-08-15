from datetime import date
from pathlib import Path

import pytest
from openpyxl import Workbook

from app.services.schedule_parser import (
    ScheduleParseError,
    analyze_schedule,
    parse_schedule,
)


def make_schedule_xlsx(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.append(["周次", "日期", "星期", "节次", "课程", "班级", "地点"])
    ws.append([1, "2026-09-07", "一", "1-4", "人工智能与创意设计", "数字艺术25级1班", "智慧教室"])
    ws.append([2, "2026-09-14", "一", "1-4", "人工智能与创意设计", "数字艺术25级1班", "智慧教室"])
    wb.save(path)


def write_rows(path: Path, rows: list[list]) -> None:
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    wb.save(path)


def test_parse_schedule_rows_from_xlsx(tmp_path):
    path = tmp_path / "schedule.xlsx"
    make_schedule_xlsx(path)

    sessions = parse_schedule(path)

    assert len(sessions) == 2
    assert sessions[0].week_no == 1
    assert sessions[0].date_text == "2026-09-07"
    assert sessions[0].periods == "1-4"
    assert sessions[0].hours == 4


def test_maps_registrar_column_aliases(tmp_path):
    path = tmp_path / "registrar.xlsx"
    write_rows(
        path,
        [
            ["教学周", "上课日期", "星期几", "节次", "课程名称", "教学班", "上课教室"],
            [1, "2026-09-07", "星期一", "第1-4节", "人工智能与创意设计", "数媒25-1", "实训楼A301"],
        ],
    )

    analysis = analyze_schedule(path)

    assert [match.field for match in analysis.matches] == [
        "week_no",
        "date_text",
        "weekday",
        "periods",
        "course_name",
        "class_name",
        "location",
    ]
    assert analysis.sessions[0].periods == "1-4"
    assert analysis.sessions[0].hours == 4
    assert analysis.sessions[0].location == "实训楼A301"


def test_skips_title_rows_above_the_header(tmp_path):
    path = tmp_path / "titled.xlsx"
    write_rows(
        path,
        [
            ["某职业技术学院 2026-2027 学年第一学期课表"],
            ["教师：张老师", None, None, "打印日期：2026-08-20"],
            [],
            ["周次", "日期", "星期", "节次", "课程", "班级", "地点"],
            [1, "2026-09-07", "一", "1-4", "人工智能与创意设计", "数媒25-1", "A301"],
        ],
    )

    analysis = analyze_schedule(path)

    assert analysis.header_row_index == 3
    assert len(analysis.sessions) == 1


def test_fills_down_vertically_merged_cells(tmp_path):
    path = tmp_path / "merged.xlsx"
    write_rows(
        path,
        [
            ["周次", "日期", "星期", "节次", "课程", "班级", "地点"],
            [1, "2026-09-07", "一", "1-2", "人工智能与创意设计", "数媒25-1", "A301"],
            [None, None, None, "3-4", None, None, None],
        ],
    )

    analysis = analyze_schedule(path)

    assert len(analysis.sessions) == 2
    second = analysis.sessions[1]
    assert second.week_no == 1
    assert second.date_text == "2026-09-07"
    assert second.course_name == "人工智能与创意设计"
    assert second.class_name == "数媒25-1"
    assert second.periods == "3-4"


def test_normalizes_fullwidth_headers_and_values(tmp_path):
    path = tmp_path / "fullwidth.xlsx"
    write_rows(
        path,
        [
            ["周　次", "日　期", "星期", "节　次", "课程名称", "班级", "地点"],
            ["１", "2026-09-07", "一", "１-４", "人工智能与创意设计", "数媒25-1", "A301"],
        ],
    )

    analysis = analyze_schedule(path)

    assert analysis.sessions[0].week_no == 1
    assert analysis.sessions[0].periods == "1-4"
    assert analysis.sessions[0].hours == 4


def test_formats_real_date_cells_without_time(tmp_path):
    path = tmp_path / "datecell.xlsx"
    write_rows(
        path,
        [
            ["周次", "日期", "星期", "节次", "课程", "班级", "地点"],
            [1, date(2026, 9, 7), "一", "1-4", "人工智能与创意设计", "数媒25-1", "A301"],
        ],
    )

    analysis = analyze_schedule(path)

    assert analysis.sessions[0].date_text == "2026-09-07"


def test_reports_unmapped_columns_without_failing(tmp_path):
    path = tmp_path / "extra.xlsx"
    write_rows(
        path,
        [
            ["周次", "日期", "星期", "节次", "课程", "班级", "地点", "任课教师", "备注"],
            [1, "2026-09-07", "一", "1-4", "人工智能与创意设计", "数媒25-1", "A301", "张老师", ""],
        ],
    )

    analysis = analyze_schedule(path)

    assert analysis.unmapped_headers == ["任课教师", "备注"]
    assert len(analysis.sessions) == 1


def test_derives_weekday_from_date_when_column_missing(tmp_path):
    path = tmp_path / "noweekday.xlsx"
    write_rows(
        path,
        [
            ["周次", "日期", "节次", "课程", "班级", "地点"],
            [1, "2026-09-07", "1-4", "人工智能与创意设计", "数媒25-1", "A301"],
        ],
    )

    analysis = analyze_schedule(path)

    assert analysis.sessions[0].weekday == "一"
    assert any("星期" in warning for warning in analysis.warnings)


def test_derives_week_numbers_when_column_missing(tmp_path):
    path = tmp_path / "noweek.xlsx"
    write_rows(
        path,
        [
            ["日期", "星期", "节次", "课程", "班级", "地点"],
            ["2026-09-07", "一", "1-4", "人工智能与创意设计", "数媒25-1", "A301"],
            ["2026-09-14", "一", "1-4", "人工智能与创意设计", "数媒25-1", "A301"],
        ],
    )

    analysis = analyze_schedule(path)

    assert [item.week_no for item in analysis.sessions] == [1, 2]
    assert any("周次" in warning for warning in analysis.warnings)


def test_raises_with_detected_headers_when_required_column_missing(tmp_path):
    path = tmp_path / "noperiods.xlsx"
    write_rows(
        path,
        [
            ["周次", "日期", "星期", "课程", "班级", "地点"],
            [1, "2026-09-07", "一", "人工智能与创意设计", "数媒25-1", "A301"],
        ],
    )

    with pytest.raises(ScheduleParseError) as excinfo:
        analyze_schedule(path)

    error = excinfo.value
    assert "节次" in str(error)
    assert error.detected_headers == ["周次", "日期", "星期", "课程", "班级", "地点"]
    assert error.missing_fields == ["periods"]


def test_manual_mapping_overrides_detection(tmp_path):
    path = tmp_path / "manual.xlsx"
    write_rows(
        path,
        [
            ["第几周", "什么时候", "礼拜", "第几节", "上什么课", "哪个班", "在哪上"],
            [1, "2026-09-07", "一", "1-4", "人工智能与创意设计", "数媒25-1", "A301"],
        ],
    )

    analysis = analyze_schedule(
        path,
        header_row=0,
        mapping={
            "week_no": 0,
            "date_text": 1,
            "weekday": 2,
            "periods": 3,
            "course_name": 4,
            "class_name": 5,
            "location": 6,
        },
    )

    assert len(analysis.sessions) == 1
    assert analysis.sessions[0].course_name == "人工智能与创意设计"
    assert all(match.confidence == "manual" for match in analysis.matches)


def test_collects_distinct_course_names_for_filtering(tmp_path):
    path = tmp_path / "multicourse.xlsx"
    write_rows(
        path,
        [
            ["周次", "日期", "星期", "节次", "课程", "班级", "地点"],
            [1, "2026-09-07", "一", "1-4", "人工智能与创意设计", "数媒25-1", "A301"],
            [1, "2026-09-08", "二", "1-2", "版式设计", "数媒25-2", "A302"],
        ],
    )

    analysis = analyze_schedule(path)

    assert analysis.course_names == ["人工智能与创意设计", "版式设计"]


def test_filters_rows_to_one_course(tmp_path):
    path = tmp_path / "multicourse.xlsx"
    write_rows(
        path,
        [
            ["周次", "日期", "星期", "节次", "课程", "班级", "地点"],
            [1, "2026-09-07", "一", "1-4", "人工智能与创意设计", "数媒25-1", "A301"],
            [1, "2026-09-08", "二", "1-2", "版式设计", "数媒25-2", "A302"],
            [2, "2026-09-14", "一", "1-4", "人工智能与创意设计", "数媒25-1", "A301"],
        ],
    )

    analysis = analyze_schedule(path, course_name="人工智能与创意设计")

    assert len(analysis.sessions) == 2
    assert {item.course_name for item in analysis.sessions} == {"人工智能与创意设计"}
    assert [item.week_no for item in analysis.sessions] == [1, 2]


@pytest.mark.parametrize(
    ("raw", "expected_text", "expected_hours"),
    [
        ("1-4", "1-4", 4),
        ("第1-4节", "1-4", 4),
        ("1-2节", "1-2", 2),
        ("3", "3", 1),
        ("1,2", "1-2", 2),
        ("1、2、3、4", "1-4", 4),
    ],
)
def test_normalizes_period_text_and_hours(tmp_path, raw, expected_text, expected_hours):
    path = tmp_path / "periods.xlsx"
    write_rows(
        path,
        [
            ["周次", "日期", "星期", "节次", "课程", "班级", "地点"],
            [1, "2026-09-07", "一", raw, "人工智能与创意设计", "数媒25-1", "A301"],
        ],
    )

    analysis = analyze_schedule(path)

    assert analysis.sessions[0].periods == expected_text
    assert analysis.sessions[0].hours == expected_hours
