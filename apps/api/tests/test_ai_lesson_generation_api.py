from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.auth import hash_password
from app.db import engine, init_db
from app.main import app
from app.models import (
    AbilityIndicator,
    AiModelConfig,
    CourseGoal,
    LessonGenerationItem,
    LessonGenerationRun,
    LessonPlan,
    OutlineRow,
    SourceConfirmation,
    TeachingTask,
    User,
)
from app.services.ai_lesson_generation import _generate_one, create_generation_run, process_generation_run
from app.services.lesson_evidence import LessonEvidence, build_lesson_evidence
from app.services.openai_compatible import ModelProviderError
from app.services.secret_store import encrypt_secret


def _payload(session_no: int) -> dict:
    return {
        "title": f"第{session_no}次课：AIGC创意流程",
        "teaching_goals": ["能说出AIGC创意流程的环节", "能使用工具完成一张创意草图", "能对照标准评价草图质量"],
        "key_points": "AIGC创意流程",
        "difficult_points": "把创意判断落实到设计任务",
        "teaching_preparation": "教师准备案例，学生准备草图工具",
        "process_segments": [
            {
                "title": "导入",
                "minutes": 40,
                "teacher_activity": "展示案例",
                "student_activity": "观察提问",
                "assessment": "口头提问",
            },
            {
                "title": "实训",
                "minutes": 120,
                "teacher_activity": "示范指导",
                "student_activity": "完成草图",
                "assessment": "过程检查",
            },
        ],
        "summary": "归纳创意流程",
        "homework": "优化创意方案",
        "course_goal_codes": ["M1", "M1", "M1"],
        "ability_codes": ["1-3-4", "1-3-4", "1-3-4"],
    }


class PartialFailureClient:
    def generate_json(self, _system_prompt: str, user_payload: dict) -> dict:
        session_no = user_payload["session_no"]
        if session_no == 2:
            raise ModelProviderError("provider unavailable")
        return _payload(session_no)


def _seed_run_for_two_sessions() -> tuple[int, int]:
    init_db()
    suffix = uuid4().hex[:8]
    with Session(engine) as session:
        user = User(
            employee_no=f"GEN{suffix}",
            name="生成测试教师",
            role="teacher",
            password_hash=hash_password("Teacher@2026!"),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        task = TeachingTask(
            owner_id=user.id,
            term="2026-2027 第一学期",
            major="数字媒体艺术设计",
            class_name="数艺2501",
            course_name=f"人工智能与创意设计-{suffix}",
            teacher_name=user.name,
            location="智慧教室",
            total_hours=8,
            hours_per_session=4,
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        session.add(CourseGoal(task_id=task.id, code="M1", description="完成创意设计任务", ability_codes="1-3-4"))
        session.add(
            AbilityIndicator(
                task_id=task.id,
                code="1-3-4",
                category="专业能力",
                group_code="1-3",
                description="能够完成创意设计",
            )
        )
        session.add(SourceConfirmation(task_id=task.id, confirmed_by_id=user.id))
        session.add(
            AiModelConfig(
                base_url="https://model.example/v1",
                model_name="lesson-model",
                encrypted_api_key=encrypt_secret("sk-private"),
                enabled=True,
                connection_status="connected",
            )
        )
        rows = []
        for session_no in (1, 2):
            row = OutlineRow(
                task_id=task.id,
                session_no=session_no,
                date_text=f"2026-09-0{session_no}",
                week_no=1,
                weekday="周二",
                periods="1-4",
                topic=f"主题{session_no}",
                teaching_content=f"教学内容{session_no}",
                course_goal_codes="M1",
                ability_codes="1-3-4",
            )
            session.add(row)
            rows.append(row)
        session.commit()
        for row in rows:
            session.refresh(row)
        run = create_generation_run(session, task, user.id, rows)
        run_id = run.id
        task_id = task.id
    return task_id, run_id


def test_generation_run_preserves_success_and_retries_failed_session_once():
    task_id, run_id = _seed_run_for_two_sessions()

    process_generation_run(run_id, client_factory=lambda _: PartialFailureClient())

    with Session(engine) as session:
        saved_run = session.get(LessonGenerationRun, run_id)
        items = session.exec(
            select(LessonGenerationItem)
            .where(LessonGenerationItem.run_id == run_id)
            .order_by(LessonGenerationItem.id)
        ).all()
        lessons = session.exec(select(LessonPlan).where(LessonPlan.task_id == task_id)).all()

    assert saved_run.status == "completed_with_errors"
    assert saved_run.succeeded_items == 1
    assert saved_run.failed_items == 1
    assert [item.status for item in items] == ["succeeded", "failed"]
    assert items[1].attempts == 2
    assert items[1].error_code == "provider_error"
    assert len(lessons) == 1
    assert lessons[0].generation_source == "ai"
    assert lessons[0].review_status == "draft"


def _auth_headers(client: TestClient, employee_no: str, password: str = "Teacher@2026!") -> dict[str, str]:
    response = client.post("/auth/login", json={"employee_no": employee_no, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_teacher_starts_and_reads_owned_generation_run(monkeypatch):
    init_db()
    suffix = uuid4().hex[:8]
    employee_no = f"API{suffix}"
    other_employee_no = f"OTHER{suffix}"
    with Session(engine) as session:
        teacher = User(
            employee_no=employee_no,
            name="接口测试教师",
            role="teacher",
            password_hash=hash_password("Teacher@2026!"),
        )
        other = User(
            employee_no=other_employee_no,
            name="其他教师",
            role="teacher",
            password_hash=hash_password("Teacher@2026!"),
        )
        session.add(teacher)
        session.add(other)
        session.commit()
        session.refresh(teacher)
        task = TeachingTask(
            owner_id=teacher.id,
            term="2026-2027 第一学期",
            major="数字媒体艺术设计",
            class_name="数艺2501",
            course_name=f"接口测试课程-{suffix}",
            teacher_name=teacher.name,
            location="智慧教室",
            total_hours=4,
            hours_per_session=4,
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        session.add(CourseGoal(task_id=task.id, code="M1", description="完成任务", ability_codes="1-3-4"))
        session.add(
            AbilityIndicator(
                task_id=task.id,
                code="1-3-4",
                category="专业能力",
                group_code="1-3",
                description="能够完成创意设计",
            )
        )
        session.add(SourceConfirmation(task_id=task.id, confirmed_by_id=teacher.id))
        session.add(
            OutlineRow(
                task_id=task.id,
                session_no=1,
                date_text="2026-09-01",
                week_no=1,
                weekday="周二",
                periods="1-4",
                topic="AIGC流程",
                teaching_content="理解AIGC流程",
                course_goal_codes="M1",
                ability_codes="1-3-4",
            )
        )
        if session.exec(select(AiModelConfig).where(AiModelConfig.enabled == True)).first() is None:  # noqa: E712
            session.add(
                AiModelConfig(
                    base_url="https://model.example/v1",
                    model_name="lesson-model",
                    encrypted_api_key=encrypt_secret("sk-private"),
                    enabled=True,
                    connection_status="connected",
                )
            )
        session.commit()
        task_id = task.id

    monkeypatch.setattr("app.routes.lesson_ai.process_generation_run", lambda _: None)
    with TestClient(app) as client:
        teacher_headers = _auth_headers(client, employee_no)
        started = client.post(f"/tasks/{task_id}/lesson-generation-runs", headers=teacher_headers)
        assert started.status_code == 200
        run_id = started.json()["id"]
        loaded = client.get(f"/tasks/{task_id}/lesson-generation-runs/{run_id}", headers=teacher_headers)
        forbidden = client.get(
            f"/tasks/{task_id}/lesson-generation-runs/{run_id}",
            headers=_auth_headers(client, other_employee_no),
        )

    assert loaded.status_code == 200
    assert loaded.json()["total_items"] == 1
    assert loaded.json()["items"][0]["status"] == "pending"
    assert forbidden.status_code == 404


def test_progress_counts_the_items_as_they_land():
    """跑到一半时，进度要反映已经落地的条数。

    `_finish_run()` 只在**整批跑完之后**才写 run 上的 `succeeded_items`，而 20 次课
    要跑五六分钟。读那个汇总值的话，这五六分钟里界面一直是 0/20、最后一瞬跳到
    20/20——**看上去和卡死一模一样**。2026-08-11 线上就这么发生了，老师以为坏了，
    那时 18 份教案其实已经落库。所以进度改成从 items 现场数。
    """
    init_db()
    suffix = uuid4().hex[:8]
    employee_no = f"PROG{suffix}"
    with Session(engine) as session:
        teacher = User(
            employee_no=employee_no,
            name="进度测试教师",
            role="teacher",
            password_hash=hash_password("Teacher@2026!"),
        )
        session.add(teacher)
        session.commit()
        session.refresh(teacher)
        task = TeachingTask(
            owner_id=teacher.id,
            term="2026-2027 第一学期",
            major="数字媒体艺术设计",
            class_name="数艺2501",
            course_name=f"进度测试课程-{suffix}",
            teacher_name=teacher.name,
            location="智慧教室",
            total_hours=12,
            hours_per_session=4,
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        # 整批还没跑完，所以 run 上的汇总值仍是初始的 0 —— 正是线上当时的状态
        run = LessonGenerationRun(
            task_id=task.id,
            initiated_by_id=teacher.id,
            status="running",
            total_items=3,
            succeeded_items=0,
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        for status in ("succeeded", "succeeded", "running"):
            session.add(LessonGenerationItem(run_id=run.id, outline_row_id=0, status=status))
        session.commit()
        task_id, run_id = task.id, run.id

    with TestClient(app) as client:
        loaded = client.get(
            f"/tasks/{task_id}/lesson-generation-runs/{run_id}",
            headers=_auth_headers(client, employee_no),
        )

    assert loaded.status_code == 200
    body = loaded.json()
    assert body["total_items"] == 3
    assert body["succeeded_items"] == 2, "进度应反映已落地的条数，不是等整批完成才跳变"
    assert body["failed_items"] == 0


def test_revision_candidate_does_not_overwrite_until_teacher_accepts(monkeypatch):
    init_db()
    suffix = uuid4().hex[:8]
    employee_no = f"REV{suffix}"
    with Session(engine) as session:
        teacher = User(
            employee_no=employee_no,
            name="修订测试教师",
            role="teacher",
            password_hash=hash_password("Teacher@2026!"),
        )
        session.add(teacher)
        session.commit()
        session.refresh(teacher)
        task = TeachingTask(
            owner_id=teacher.id,
            term="2026-2027 第一学期",
            major="数字媒体艺术设计",
            class_name="数艺2501",
            course_name=f"修订测试课程-{suffix}",
            teacher_name=teacher.name,
            location="智慧教室",
            total_hours=4,
            hours_per_session=4,
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        row = OutlineRow(
            task_id=task.id,
            session_no=1,
            date_text="2026-09-01",
            week_no=1,
            weekday="周二",
            periods="1-4",
            topic="AIGC流程",
            teaching_content="理解AIGC流程",
            course_goal_codes="M1",
            ability_codes="1-3-4",
        )
        session.add(row)
        session.add(CourseGoal(task_id=task.id, code="M1", description="完成任务", ability_codes="1-3-4"))
        session.add(
            AbilityIndicator(
                task_id=task.id,
                code="1-3-4",
                category="专业能力",
                group_code="1-3",
                description="能够完成创意设计",
            )
        )
        session.add(SourceConfirmation(task_id=task.id, confirmed_by_id=teacher.id))
        session.commit()
        session.refresh(row)
        lesson = LessonPlan(
            task_id=task.id,
            outline_row_id=row.id,
            session_no=1,
            title="第1次课",
            teaching_goals="原教学目标",
            key_points="原教学重点",
            difficult_points="原教学难点",
            teaching_process="原教学过程",
            homework="原课后任务",
            generation_source="ai",
            review_status="draft",
        )
        session.add(lesson)
        session.commit()
        session.refresh(lesson)
        task_id = task.id
        lesson_id = lesson.id

    monkeypatch.setattr(
        "app.routes.lesson_ai.generate_revision_candidate_text",
        lambda *args, **kwargs: "增加艺术设计案例分析",
    )
    with TestClient(app) as client:
        headers = _auth_headers(client, employee_no)
        created = client.post(
            f"/tasks/{task_id}/lessons/{lesson_id}/revision-candidates",
            headers=headers,
            json={"field_name": "key_points", "instruction": "增加艺术设计案例"},
        )
        assert created.status_code == 200
        candidate_id = created.json()["id"]
        before = client.get(f"/tasks/{task_id}/lessons", headers=headers).json()[0]
        accepted = client.post(
            f"/tasks/{task_id}/lesson-revision-candidates/{candidate_id}/accept",
            headers=headers,
        )

    assert before["key_points"] == "原教学重点"
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    with Session(engine) as session:
        saved = session.get(LessonPlan, lesson_id)
        assert saved.key_points == "增加艺术设计案例分析"
        assert saved.teaching_goals == "原教学目标"
        assert saved.review_status == "reviewed"


class MinutesThenFixedClient:
    """Fails validation once, then succeeds; records what each attempt was told."""

    def __init__(self) -> None:
        self.payloads: list[dict] = []

    def generate_json(self, _system_prompt: str, user_payload: dict) -> dict:
        self.payloads.append(user_payload)
        payload = _payload(user_payload["session_no"])
        if len(self.payloads) == 1:
            payload["process_segments"][1]["minutes"] = 100  # totals 140, not 160
        return payload


def _evidence_for_retry() -> LessonEvidence:
    return build_lesson_evidence(
        TeachingTask(
            term="2026-2027 第一学期", major="数字媒体艺术设计", class_name="数艺2501",
            course_name="人工智能与创意设计", teacher_name="张老师", location="智慧教室",
            total_hours=32, hours_per_session=4,
        ),
        OutlineRow(
            id=1, task_id=1, session_no=1, date_text="2026-09-07", week_no=1, weekday="一",
            periods="1-4", topic="AIGC创意流程", teaching_content="理解流程",
            course_goal_codes="M1", ability_codes="1-3-4",
        ),
        [CourseGoal(task_id=1, code="M1", description="完成创意设计", ability_codes="1-3-4")],
        [AbilityIndicator(task_id=1, code="1-3-4", category="专业能力", group_code="1-3", description="能完成设计")],
        None,
        None,
    )


def test_retry_tells_the_model_what_was_wrong_with_the_first_answer():
    client = MinutesThenFixedClient()

    lesson, attempts, _duration, error_code = _generate_one(
        AiModelConfig(base_url="https://model.example", model_name="test", encrypted_api_key="x", enabled=True),
        _evidence_for_retry(),
        lambda _config: client,
    )

    assert lesson is not None
    assert attempts == 2
    assert error_code == ""
    assert "previous_attempt_error" not in client.payloads[0]
    assert "160" in client.payloads[1]["previous_attempt_error"]


def test_workers_never_receive_session_bound_objects(tmp_path, monkeypatch):
    """A commit expires ORM instances; a worker touching one then fails in
    milliseconds with no network call. Workers must get detached data."""
    from sqlalchemy import inspect as sa_inspect

    bound: list[bool] = []

    class RecordingClient:
        def __init__(self, config):
            # Judge at call time: after the run returns the session is closed
            # and every instance looks detached, which would prove nothing.
            bound.append(sa_inspect(config).session is not None)

        def generate_json(self, _system_prompt: str, user_payload: dict) -> dict:
            return _payload(user_payload["session_no"])

    task_id, run_id = _seed_run_for_two_sessions()
    process_generation_run(run_id, client_factory=RecordingClient)

    assert bound, "模型客户端从未被调用"
    assert not any(bound), "工作线程拿到了仍绑定 Session 的配置对象"

    with Session(engine) as session:
        items = session.exec(
            select(LessonGenerationItem).where(LessonGenerationItem.run_id == run_id)
        ).all()
    assert [item.status for item in items] == ["succeeded", "succeeded"]
    assert [item.error_code for item in items] == ["", ""]
