"""Parse the matrix timetable the registrar system exports.

The export is an OLE2 .xls whose rows are period blocks and whose columns are
weekdays. Each cell packs one or more course entries, and the sheet's footnote
carries the semester start date, which is what turns a week number into a date.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
import re


WEEKDAY_CHARS = ("一", "二", "三", "四", "五", "六", "日")
WEEKDAY_HEADERS = tuple(f"星期{char}" for char in WEEKDAY_CHARS)

# 课程<>周次<>校区地点<>教师<>教学班<>课堂名称<>教学班组成<>板块等级<>场地类别
FIELD_COURSE, FIELD_WEEKS, FIELD_LOCATION, FIELD_TEACHER, FIELD_CLASS = 0, 1, 2, 3, 4
FIELD_COMPOSITION = 6


class RegistrarParseError(ValueError):
    pass


@dataclass(frozen=True)
class CellEntry:
    course_name: str
    periods: str
    weeks: list[int]
    location: str
    teacher: str
    teaching_class: str
    class_names: str


@dataclass(frozen=True)
class RegistrarSession:
    week_no: int
    date_text: str
    weekday: str
    periods: str
    course_name: str
    class_name: str
    location: str
    hours: int


@dataclass(frozen=True)
class RegistrarSchedule:
    sessions: list[RegistrarSession]
    term_start: date
    total_weeks: int
    course_names: list[str] = field(default_factory=list)
    teaching_classes: list[str] = field(default_factory=list)


def parse_week_spec(text: str) -> list[int]:
    """Expand 1-5周 / 9-11周(单),12-14周 into the weeks it covers."""
    weeks: list[int] = []
    for group in re.split(r"[,，]", text):
        numbers = [int(item) for item in re.findall(r"\d+", group)]
        if not numbers:
            continue
        low, high = numbers[0], numbers[-1]
        step_odd = "单" in group
        step_even = "双" in group
        for week in range(low, high + 1):
            if step_odd and week % 2 == 0:
                continue
            if step_even and week % 2 == 1:
                continue
            weeks.append(week)
    return sorted(dict.fromkeys(weeks))


def split_cell_entries(text: str) -> list[CellEntry]:
    entries: list[CellEntry] = []
    for line in str(text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split("/")]
        if len(parts) < 2:
            continue
        matched = re.match(r"\((?P<periods>[^)]*?)节?\)(?P<weeks>.+)", parts[FIELD_WEEKS])
        if matched is None:
            continue
        entries.append(
            CellEntry(
                course_name=parts[FIELD_COURSE],
                periods=matched.group("periods").strip(),
                weeks=parse_week_spec(matched.group("weeks")),
                location=parts[FIELD_LOCATION] if len(parts) > FIELD_LOCATION else "",
                teacher=parts[FIELD_TEACHER] if len(parts) > FIELD_TEACHER else "",
                teaching_class=parts[FIELD_CLASS] if len(parts) > FIELD_CLASS else "",
                class_names=parts[FIELD_COMPOSITION] if len(parts) > FIELD_COMPOSITION else "",
            )
        )
    return entries


def read_xls_matrix(path: Path | str) -> list[list[str]]:
    import xlrd

    book = xlrd.open_workbook(str(path))
    sheet = book.sheet_by_index(0)
    return [
        [str(sheet.cell_value(row, column)).strip() for column in range(sheet.ncols)]
        for row in range(sheet.nrows)
    ]


def _find_term_start(rows: list[list[str]]) -> tuple[date | None, int]:
    joined = " ".join(cell for row in rows for cell in row if cell)
    start = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})\s*正式上课", joined)
    # Anchor to the term sentence: the footnote also lists per-course spans
    # such as "电商网页设计★张明(共3周)", which must not win.
    weeks = re.search(r"结束[，,]?\s*共\s*(\d+)\s*周", joined)
    parsed = None
    if start is not None:
        parsed = date(int(start.group(1)), int(start.group(2)), int(start.group(3)))
    return parsed, int(weeks.group(1)) if weeks else 0


def _find_weekday_columns(rows: list[list[str]]) -> tuple[int, dict[int, int]]:
    for index, row in enumerate(rows):
        columns = {
            position: WEEKDAY_HEADERS.index(cell)
            for position, cell in enumerate(row)
            if cell in WEEKDAY_HEADERS
        }
        if columns:
            return index, columns
    raise RegistrarParseError("未找到星期表头行，请确认这是教务系统导出的课表")


def _merge_same_day_periods(
    items: list[RegistrarSession],
    periods_per_session: int = 4,
) -> list[RegistrarSession]:
    """Adjacent period blocks on one date form teaching sessions.

    A whole day of 1-8节 is two four-period sessions, not one eight-period one:
    the course is taught in fixed-length sessions and the outline is written
    per session.
    """
    by_day: dict[tuple[str, str], list[RegistrarSession]] = {}
    for item in items:
        by_day.setdefault((item.date_text, item.course_name), []).append(item)
    merged: list[RegistrarSession] = []
    for group in by_day.values():
        numbers: list[int] = []
        for item in group:
            numbers.extend(int(part) for part in re.findall(r"\d+", item.periods))
        low, high = min(numbers), max(numbers)
        first = group[0]
        step = max(1, periods_per_session)
        start = low
        while start <= high:
            stop = min(start + step - 1, high)
            merged.append(
                RegistrarSession(
                    week_no=first.week_no,
                    date_text=first.date_text,
                    weekday=first.weekday,
                    periods=f"{start}-{stop}" if start != stop else str(start),
                    course_name=first.course_name,
                    class_name=first.class_name,
                    location=first.location,
                    hours=stop - start + 1,
                )
            )
            start = stop + 1
    return sorted(merged, key=lambda item: (item.date_text, int(item.periods.split("-")[0])))


def parse_registrar_matrix(
    rows: list[list[str]],
    *,
    course_name: str | None = None,
    teaching_class: str | None = None,
    periods_per_session: int = 4,
) -> RegistrarSchedule:
    term_start, total_weeks = _find_term_start(rows)
    if term_start is None:
        raise RegistrarParseError("课表中没有开学日期，无法把周次换算成上课日期")
    header_index, weekday_columns = _find_weekday_columns(rows)

    raw: list[RegistrarSession] = []
    courses: list[str] = []
    classes: list[str] = []
    for row in rows[header_index + 1 :]:
        for column, weekday_index in weekday_columns.items():
            if column >= len(row):
                continue
            for entry in split_cell_entries(row[column]):
                if entry.course_name and entry.course_name not in courses:
                    courses.append(entry.course_name)
                if entry.teaching_class and entry.teaching_class not in classes:
                    classes.append(entry.teaching_class)
                if course_name and entry.course_name != course_name:
                    continue
                if teaching_class and entry.teaching_class != teaching_class:
                    continue
                for week in entry.weeks:
                    day = term_start + timedelta(weeks=week - 1, days=weekday_index)
                    numbers = [int(part) for part in re.findall(r"\d+", entry.periods)]
                    span = max(numbers) - min(numbers) + 1 if numbers else 1
                    raw.append(
                        RegistrarSession(
                            week_no=week,
                            date_text=day.isoformat(),
                            weekday=WEEKDAY_CHARS[weekday_index],
                            periods=entry.periods,
                            course_name=entry.course_name,
                            class_name=entry.class_names.split(";")[0].strip(),
                            location=entry.location,
                            hours=span,
                        )
                    )

    return RegistrarSchedule(
        sessions=_merge_same_day_periods(raw, periods_per_session),
        term_start=term_start,
        total_weeks=total_weeks,
        course_names=courses,
        teaching_classes=classes,
    )


def parse_registrar_xls(
    path: Path | str,
    *,
    course_name: str | None = None,
    teaching_class: str | None = None,
    periods_per_session: int = 4,
) -> RegistrarSchedule:
    return parse_registrar_matrix(
        read_xls_matrix(path),
        course_name=course_name,
        teaching_class=teaching_class,
        periods_per_session=periods_per_session,
    )
