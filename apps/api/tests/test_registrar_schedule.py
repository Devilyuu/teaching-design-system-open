"""The real registrar export is an .xls matrix, not the long-format .xlsx the
first parser assumed. These lock down the shapes seen in 1001张明课表.xls.
"""

import pytest

from app.services.registrar_schedule import (
    RegistrarParseError,
    parse_registrar_matrix,
    parse_week_spec,
    split_cell_entries,
)


def test_parses_a_plain_week_range():
    assert parse_week_spec("1-5周") == [1, 2, 3, 4, 5]


def test_parses_a_single_week():
    assert parse_week_spec("13周") == [13]


def test_parses_comma_separated_groups():
    assert parse_week_spec("13-14周") == [13, 14]


def test_honours_an_odd_week_marker():
    assert parse_week_spec("9-11周(单)") == [9, 11]


def test_honours_an_even_week_marker():
    assert parse_week_spec("10-14周(双)") == [10, 12, 14]


def test_combines_a_marked_group_with_a_plain_one():
    assert parse_week_spec("9-11周(单),12-14周") == [9, 11, 12, 13, 14]


def test_reads_periods_and_weeks_out_of_one_entry():
    entry = split_cell_entries(
        "移动终端APP设计/(1-2节)1-5周/示例校区 教学楼101/张明/"
        "移动终端APP设计-0003//数字艺术2431;数字艺术2433/ /多媒体"
    )[0]

    assert entry.course_name == "移动终端APP设计"
    assert entry.periods == "1-2"
    assert entry.weeks == [1, 2, 3, 4, 5]
    assert entry.location == "示例校区 教学楼101"
    assert entry.teacher == "张明"
    assert entry.teaching_class == "移动终端APP设计-0003"
    assert entry.class_names == "数字艺术2431;数字艺术2433"


def test_one_cell_can_hold_several_courses():
    entries = split_cell_entries(
        "移动终端APP设计/(1-2节)1-5周/教学楼101/张明/移动终端APP设计-0003//数字艺术2431/ /多媒体\n"
        "移动终端APP设计/(1-2节)9-11周(单),12-14周/教学楼102/张明/移动终端APP设计-0002//数字艺术2432/ /多媒体"
    )

    assert len(entries) == 2
    assert entries[0].teaching_class.endswith("0003")
    assert entries[1].weeks == [9, 11, 12, 13, 14]


def test_ignores_a_blank_cell():
    assert split_cell_entries("") == []
    assert split_cell_entries("   ") == []


def make_matrix(rows: list[list[str]]):
    """Stand-in for the sheet reader so the parser is testable without a file."""
    return rows


def test_expands_a_matrix_into_dated_sessions():
    sheet = make_matrix([
        ["2025-2026学年第2学期", "", "张明老师的课表", "", "", "", "", "", ""],
        ["节次", "", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"],
        ["上午", "一", "移动终端APP设计/(1-2节)1-2周/教学楼101/张明/移动终端APP设计-0003//数字艺术2431/ /多媒体", "", "", "", "", "", ""],
        ["", "二", "移动终端APP设计/(3-4节)1-2周/教学楼101/张明/移动终端APP设计-0003//数字艺术2431/ /多媒体", "", "", "", "", "", ""],
        ["注--内容顺序为：课程<>周次<>校区   本学期2026-03-02正式上课至2026-07-05结束，共18周.", "", "", "", "", "", "", "", ""],
    ])

    result = parse_registrar_matrix(sheet)

    assert result.term_start.isoformat() == "2026-03-02"
    assert result.total_weeks == 18
    assert [item.date_text for item in result.sessions] == ["2026-03-02", "2026-03-09"]
    assert [item.week_no for item in result.sessions] == [1, 2]
    assert [item.periods for item in result.sessions] == ["1-4", "1-4"]
    assert [item.hours for item in result.sessions] == [4, 4]
    assert result.sessions[0].weekday == "一"
    assert result.sessions[0].location == "教学楼101"


def test_merges_adjacent_period_blocks_on_the_same_day():
    """1-2节 and 3-4节 on the same date are one four-period session."""
    sheet = make_matrix([
        ["节次", "", "星期一", "星期二"],
        ["上午", "一", "移动终端APP设计/(1-2节)1周/A101/张明/移动终端APP设计-0003//数字艺术2431/ /多媒体", ""],
        ["", "二", "移动终端APP设计/(3-4节)1周/A101/张明/移动终端APP设计-0003//数字艺术2431/ /多媒体", ""],
        ["注 本学期2026-03-02正式上课至2026-07-05结束，共18周."],
    ])

    result = parse_registrar_matrix(sheet)

    assert len(result.sessions) == 1
    assert result.sessions[0].periods == "1-4"
    assert result.sessions[0].hours == 4


def test_separates_the_two_teaching_classes_of_one_course():
    sheet = make_matrix([
        ["节次", "", "星期一"],
        ["上午", "一",
         "移动终端APP设计/(1-2节)1周/教学楼101/张明/移动终端APP设计-0003//数字艺术2431/ /多媒体\n"
         "移动终端APP设计/(1-2节)2周/教学楼102/张明/移动终端APP设计-0002//数字艺术2432/ /多媒体"],
        ["注 本学期2026-03-02正式上课至2026-07-05结束，共18周."],
    ])

    result = parse_registrar_matrix(sheet)

    assert sorted(result.teaching_classes) == ["移动终端APP设计-0002", "移动终端APP设计-0003"]
    only = parse_registrar_matrix(sheet, teaching_class="移动终端APP设计-0003")
    assert [item.date_text for item in only.sessions] == ["2026-03-02"]
    assert only.sessions[0].class_name == "数字艺术2431"


def test_keeps_only_the_requested_course():
    sheet = make_matrix([
        ["节次", "", "星期一", "星期二"],
        ["上午", "一",
         "移动终端APP设计/(1-2节)1周/A101/张明/移动终端APP设计-0003//数字艺术2431/ /多媒体",
         "劳动教育/(1-2节)1周/操场3/张明/劳动教育-0095//数字艺术2433/ /操场"],
        ["注 本学期2026-03-02正式上课至2026-07-05结束，共18周."],
    ])

    result = parse_registrar_matrix(sheet, course_name="移动终端APP设计")

    assert sorted(result.course_names) == ["劳动教育", "移动终端APP设计"]
    assert len(result.sessions) == 1
    assert result.sessions[0].course_name == "移动终端APP设计"


def test_tolerates_the_registrar_spelling_the_course_differently():
    """建课程时写「移动终端APP设计」，教务写「移动终端APP设计（一）」，不该整张课表作废。"""
    sheet = make_matrix([
        ["节次", "", "星期一", "星期二"],
        ["上午", "一",
         "移动终端APP设计（一）/(1-2节)1周/A101/张明/移动终端APP设计（一）-0003//数字艺术2431/ /多媒体",
         "劳动教育/(1-2节)1周/操场3/张明/劳动教育-0095//数字艺术2433/ /操场"],
        ["注 本学期2026-03-02正式上课至2026-07-05结束，共18周."],
    ])

    result = parse_registrar_matrix(sheet, course_name="移动终端APP设计")

    assert [item.course_name for item in result.sessions] == ["移动终端APP设计（一）"]


def test_prefers_the_exact_course_over_a_lookalike():
    """课表里同时有「网页设计」和「网页设计实训」时，选前者不该把后者也带进来。"""
    sheet = make_matrix([
        ["节次", "", "星期一", "星期二"],
        ["上午", "一",
         "网页设计/(1-2节)1周/A101/张明/网页设计-0001//数字艺术2431/ /多媒体",
         "网页设计实训/(1-2节)1周/A102/张明/网页设计实训-0001//数字艺术2431/ /多媒体"],
        ["注 本学期2026-03-02正式上课至2026-07-05结束，共18周."],
    ])

    result = parse_registrar_matrix(sheet, course_name="网页设计")

    assert [item.course_name for item in result.sessions] == ["网页设计"]


def test_requires_the_semester_start_date():
    sheet = make_matrix([
        ["节次", "", "星期一"],
        ["上午", "一", "移动终端APP设计/(1-2节)1周/A101/张明/移动终端APP设计-0003//数字艺术2431/ /多媒体"],
    ])

    with pytest.raises(RegistrarParseError, match="开学日期"):
        parse_registrar_matrix(sheet)


def test_term_length_ignores_per_course_week_counts_in_the_footnote():
    sheet = make_matrix([
        ["节次", "", "星期一"],
        ["上午", "一", "移动终端APP设计/(1-2节)1周/A101/张明/移动终端APP设计-0003//数字艺术2431/ /多媒体"],
        ["其他课程：电商网页设计★张明(共3周)/1-3周/电商网页设计-0001/无;"],
        ["注 本学期2026-03-02正式上课至2026-07-05结束，共18周."],
    ])

    assert parse_registrar_matrix(sheet).total_weeks == 18


def test_reads_the_export_that_inserts_a_course_code_and_total_hours():
    """The 2026-09-10 export adds 课程号 after the course and 课程总学时 after the
    composition; the fixed-position reader saw the course code where it expected
    the weeks and dropped every entry."""
    entry = split_cell_entries(
        "字体设计/12012006060/(1-2节)1-2周,4周/示例校区 教学楼304/张明/"
        "字体设计-0004//视觉244/48/ /创意专业教室"
    )[0]

    assert entry.course_name == "字体设计"
    assert entry.periods == "1-2"
    assert entry.weeks == [1, 2, 4]
    assert entry.location == "示例校区 教学楼304"
    assert entry.teacher == "张明"
    assert entry.teaching_class == "字体设计-0004"
    assert entry.class_names == "视觉244"


def test_skips_a_major_direction_shown_between_teacher_and_class():
    entry = split_cell_entries(
        "字体设计/12012006060/(1-2节)1-2周/示例校区 教学楼304/张明/视觉传达方向/"
        "字体设计-0004//视觉244/48/ /创意专业教室"
    )[0]

    assert entry.teaching_class == "字体设计-0004"
    assert entry.class_names == "视觉244"


def test_an_entry_without_a_weeks_field_is_not_an_entry():
    assert split_cell_entries("字体设计/12012006060/示例校区 教学楼304") == []
