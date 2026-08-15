from app.services.course_standard_parser import ParsedCourseGoal
from app.services.outline_generator import generate_outline_rows
from app.services.schedule_parser import ScheduleSession


def test_generate_outline_rows_maps_sessions_to_course_goals():
    sessions = [
        ScheduleSession(1, "2026-09-07", "一", "1-4", "人工智能与创意设计", "数字艺术25级1班", "智慧教室", 4),
        ScheduleSession(2, "2026-09-14", "一", "1-4", "人工智能与创意设计", "数字艺术25级1班", "智慧教室", 4),
    ]
    goals = [
        ParsedCourseGoal("M1", "理解AIGC基础与创意设计流程", ["1-3-4"]),
        ParsedCourseGoal("M2", "完成AI辅助文创项目", ["2-3-4", "2-3-5"]),
    ]

    rows = generate_outline_rows(sessions, goals)

    assert len(rows) == 2
    assert rows[0].session_no == 1
    assert rows[0].periods == "1-4"
    assert rows[0].course_goal_codes == "M1"
    assert rows[0].ability_codes == "1-3-4"
    assert rows[1].course_goal_codes == "M2"
    assert rows[1].ability_codes == "2-3-4 2-3-5"
