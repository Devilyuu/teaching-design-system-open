from dataclasses import dataclass

from app.models import OutlineRow, TeachingTask


@dataclass(frozen=True)
class GeneratedLessonPlan:
    outline_row_id: int
    session_no: int
    title: str
    duration_minutes: int
    teaching_goals: str
    key_points: str
    difficult_points: str
    teaching_process: str
    homework: str
    reflection: str
    course_goal_codes: str
    ability_codes: str


def generate_lesson_plans(task: TeachingTask, rows: list[OutlineRow]) -> list[GeneratedLessonPlan]:
    plans: list[GeneratedLessonPlan] = []
    duration = task.hours_per_session * 40

    for row in rows:
        plans.append(
            GeneratedLessonPlan(
                outline_row_id=row.id or 0,
                session_no=row.session_no,
                title=f"第 {row.session_no} 次课：{row.teaching_content}",
                duration_minutes=duration,
                teaching_goals=(
                    f"围绕“{row.teaching_content}”完成本次课学习任务；"
                    f"对应课程目标 {row.course_goal_codes}，支撑能力指标 {row.ability_codes}。"
                ),
                key_points=row.teaching_content,
                difficult_points="将 AI 工具使用、创意判断和作品规范要求落实到具体设计任务中。",
                teaching_process="\n".join(
                    [
                        f"课前：{row.pre_task}",
                        f"导入：围绕“{row.topic}”展示案例，明确本次课任务和评价标准。",
                        f"讲授与示范：采用{row.teaching_methods}，讲解关键概念、操作流程和常见问题。",
                        f"实训：学生完成“{row.in_class_task}”，教师巡回指导并记录共性问题。",
                        "展示与评价：组织作品展示、同伴互评和教师点评，强调职业规范与技术向善。",
                        f"课后：{row.post_task}",
                    ]
                ),
                homework=row.post_task,
                reflection="课后根据学生作品质量、课堂参与和提交材料补充教学反思。",
                course_goal_codes=row.course_goal_codes,
                ability_codes=row.ability_codes,
            )
        )

    return plans
