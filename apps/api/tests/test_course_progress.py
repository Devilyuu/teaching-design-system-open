from dataclasses import dataclass
from datetime import date

from app.services.course_progress import summarize_course_sessions


@dataclass(frozen=True)
class Session:
    session_no: int
    date_text: str
    weekday: str
    periods: str


def test_returns_empty_progress_for_no_sessions():
    progress = summarize_course_sessions([], today=date(2026, 6, 29))

    assert progress.session_count == 0
    assert progress.completed_sessions_count == 0
    assert progress.next_session_no is None
    assert progress.next_session_date == ""
    assert progress.next_session_weekday == ""
    assert progress.next_session_periods == ""


def test_summarizes_completed_and_next_session():
    sessions = [
        Session(1, "2026-06-22", "Monday", "1-2"),
        Session(2, "2026-06-29", "Monday", "3-4"),
        Session(3, "2026-07-06", "Monday", "5-6"),
    ]

    progress = summarize_course_sessions(sessions, today=date(2026, 6, 29))

    assert progress.session_count == 3
    assert progress.completed_sessions_count == 1
    assert progress.next_session_no == 2
    assert progress.next_session_date == "2026-06-29"
    assert progress.next_session_weekday == "Monday"
    assert progress.next_session_periods == "3-4"


def test_orders_same_day_sessions_by_session_number():
    sessions = [
        Session(2, "2026-06-29", "Monday", "3-4"),
        Session(1, "2026-06-29", "Monday", "1-2"),
    ]

    progress = summarize_course_sessions(sessions, today=date(2026, 6, 29))

    assert progress.next_session_no == 1


def test_returns_no_next_session_when_all_sessions_are_completed():
    sessions = [
        Session(1, "2026-06-15", "Monday", "1-2"),
        Session(2, "2026-06-22", "Monday", "3-4"),
    ]

    progress = summarize_course_sessions(sessions, today=date(2026, 6, 29))

    assert progress.session_count == 2
    assert progress.completed_sessions_count == 2
    assert progress.next_session_no is None
    assert progress.next_session_date == ""
    assert progress.next_session_weekday == ""
    assert progress.next_session_periods == ""


def test_ignores_invalid_dates_for_chronology_but_counts_the_session():
    sessions = [
        Session(1, "第一周", "Monday", "1-2"),
        Session(2, "2026-07-06 08:00", "Monday", "3-4"),
    ]

    progress = summarize_course_sessions(sessions, today=date(2026, 6, 29))

    assert progress.session_count == 2
    assert progress.completed_sessions_count == 0
    assert progress.next_session_no == 2
    assert progress.next_session_date == "2026-07-06"
    assert progress.next_session_weekday == "Monday"
    assert progress.next_session_periods == "3-4"


def test_strips_whitespace_before_parsing_session_dates():
    sessions = [Session(1, " 2026-06-29 ", "Monday", "1-2")]

    progress = summarize_course_sessions(sessions, today=date(2026, 6, 29))

    assert progress.next_session_no == 1
    assert progress.next_session_date == "2026-06-29"
