from dataclasses import dataclass

from app.services.course_standard_parser import ParsedCourseGoal
from app.services.schedule_parser import ScheduleSession


@dataclass(frozen=True)
class GeneratedOutlineRow:
    session_no: int
    date_text: str
    week_no: int
    weekday: str
    periods: str
    topic: str
    teaching_content: str
    ideological_point: str
    teaching_methods: str
    pre_task: str
    in_class_task: str
    post_task: str
    course_goal_codes: str
    ability_codes: str
    project_name: str = ""
    note: str = ""


def generate_outline_rows(
    sessions: list[ScheduleSession],
    goals: list[ParsedCourseGoal],
) -> list[GeneratedOutlineRow]:
    if not goals:
        raise ValueError("At least one course goal is required")

    rows: list[GeneratedOutlineRow] = []
    for index, session in enumerate(sessions):
        goal = goals[index % len(goals)]
        session_no = index + 1
        rows.append(
            GeneratedOutlineRow(
                session_no=session_no,
                date_text=session.date_text,
                week_no=session.week_no,
                weekday=session.weekday,
                periods=session.periods,
                topic=f"第 {session_no} 次课：{goal.description}",
                teaching_content=goal.description,
                ideological_point="职业规范、原创意识与技术向善",
                teaching_methods="案例分析、任务驱动、实训操作、作品点评",
                pre_task="预习本次课相关案例，记录主题来源和问题。",
                in_class_task="完成本次课项目任务，保留设计过程记录。",
                post_task="完善课堂成果并提交阶段材料。",
                course_goal_codes=goal.code,
                ability_codes=" ".join(goal.ability_codes),
            )
        )

    return rows
