from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Protocol


class ScheduledSession(Protocol):
    session_no: int
    date_text: str
    weekday: str
    periods: str


@dataclass(frozen=True)
class CourseProgress:
    session_count: int
    completed_sessions_count: int
    next_session_no: int | None
    next_session_date: str
    next_session_weekday: str
    next_session_periods: str


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value.strip()[:10])
    except (TypeError, ValueError):
        return None


def summarize_course_sessions(
    sessions: Iterable[ScheduledSession], today: date | None = None
) -> CourseProgress:
    session_list = list(sessions)
    current_date = today or date.today()
    dated_sessions = [
        (session_date, session)
        for session in session_list
        if (session_date := _parse_date(session.date_text)) is not None
    ]

    completed_sessions_count = sum(
        session_date < current_date for session_date, _ in dated_sessions
    )
    upcoming_sessions = [
        (session_date, session)
        for session_date, session in dated_sessions
        if session_date >= current_date
    ]
    if not upcoming_sessions:
        return CourseProgress(
            session_count=len(session_list),
            completed_sessions_count=completed_sessions_count,
            next_session_no=None,
            next_session_date="",
            next_session_weekday="",
            next_session_periods="",
        )

    next_date, next_session = min(
        upcoming_sessions, key=lambda item: (item[0], item[1].session_no)
    )
    return CourseProgress(
        session_count=len(session_list),
        completed_sessions_count=completed_sessions_count,
        next_session_no=next_session.session_no,
        next_session_date=next_date.isoformat(),
        next_session_weekday=next_session.weekday,
        next_session_periods=next_session.periods,
    )
