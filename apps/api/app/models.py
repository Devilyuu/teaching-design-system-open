from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class TeachingTask(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    owner_id: int | None = Field(default=None, index=True)
    major_id: int | None = Field(default=None, index=True)
    term: str
    major: str
    class_name: str
    course_name: str
    teacher_name: str
    location: str
    total_hours: int = 32
    hours_per_session: int = 4
    status: str = "materials_pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Major(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    short_name: str = ""
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    employee_no: str = Field(index=True, unique=True)
    name: str
    role: str = "teacher"
    password_hash: str
    is_active: bool = True
    # Set whenever an admin chose the password (account creation, reset): the
    # teacher is the only one who should know the password they work with.
    must_change_password: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserMajorLink(SQLModel, table=True):
    user_id: int = Field(primary_key=True)
    major_id: int = Field(primary_key=True)


class CourseGoal(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(index=True)
    code: str
    description: str
    ability_codes: str


class CourseProject(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(index=True)
    sequence_no: int
    name: str
    description: str = ""
    teaching_content: str
    suggested_methods: str = ""
    course_goal_codes: str
    ability_codes: str
    reference_hours: int
    practice_hours: int


class AbilityIndicator(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(index=True)
    code: str = Field(index=True)
    category: str
    group_code: str
    description: str


class SourceConfirmation(SQLModel, table=True):
    task_id: int = Field(primary_key=True)
    confirmed_by_id: int
    confirmed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ScheduleSessionRecord(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(index=True)
    session_no: int
    week_no: int
    date_text: str
    weekday: str
    periods: str
    course_name: str
    class_name: str
    location: str
    hours: int


class TaskMaterialAsset(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(index=True)
    kind: str = Field(index=True)
    original_filename: str
    storage_path: str
    size_bytes: int
    uploaded_by_id: int = Field(index=True)
    status: str = "ready"
    summary_json: str = "{}"
    error_message: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ScheduleImportCandidate(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(index=True)
    original_filename: str
    storage_path: str
    uploaded_by_id: int = Field(index=True)
    status: str = "pending"
    parse_meta_json: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ScheduleCandidateSession(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    candidate_id: int = Field(index=True)
    session_no: int
    week_no: int
    date_text: str
    weekday: str
    periods: str
    course_name: str
    class_name: str
    location: str
    hours: int


class ExportRecord(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(index=True)
    artifact_type: str
    filename: str
    storage_path: str
    size_bytes: int
    template_filename: str = ""
    source_summary: str = ""
    session_no: int | None = None
    exported_by_id: int = Field(index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CourseReviewNotice(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(index=True)
    artifact_type: str
    reason: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None


class OutlineRow(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(index=True)
    session_no: int
    date_text: str
    week_no: int
    weekday: str
    periods: str
    topic: str
    teaching_content: str
    ideological_point: str = ""
    teaching_methods: str = ""
    pre_task: str = ""
    in_class_task: str = ""
    post_task: str = ""
    course_goal_codes: str = ""
    ability_codes: str = ""
    project_name: str = ""
    note: str = ""
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OutlineSectionSet(SQLModel, table=True):
    """The outline's generated body -- everything in it except 学习进程.

    Kept rather than written afresh at each export: a teacher who exports,
    reads, and exports again is checking one document, not two.
    """

    task_id: int = Field(primary_key=True)
    payload_json: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LessonPlan(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(index=True)
    outline_row_id: int = Field(index=True)
    session_no: int
    title: str
    duration_minutes: int = 160
    teaching_goals: str
    key_points: str
    difficult_points: str
    teaching_preparation: str = ""
    teaching_process: str
    summary: str = ""
    homework: str
    reflection: str = ""
    course_goal_codes: str = ""
    ability_codes: str = ""
    generation_source: str = "manual"
    review_status: str = "reviewed"


class SessionMaterial(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(index=True)
    outline_row_id: int = Field(index=True)
    owner_user_id: int = Field(index=True)
    material_type: str
    title: str
    content: str
    reference_answer: str
    grading_criteria: str
    difficulty: str = "medium"
    estimated_minutes: int = 40
    course_goal_codes: str = ""
    ability_codes: str = ""
    source_status: str = "outline_only"
    generation_method: str = "rule"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PostClassReflection(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(index=True)
    outline_row_id: int = Field(index=True, unique=True)
    owner_user_id: int = Field(index=True)
    progress_status: str
    mastery_level: str
    classroom_effect: str
    note: str = ""
    suggestion_type: str = "none"
    suggestion_text: str = ""
    suggested_minutes: int = 0
    status: str = "pending"
    target_outline_row_id: int | None = Field(default=None, index=True)
    applied_lesson_plan_id: int | None = Field(default=None, index=True)
    applied_block_marker: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    applied_at: datetime | None = None
    reverted_at: datetime | None = None


class AiModelConfig(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    base_url: str
    model_name: str
    encrypted_api_key: str
    enabled: bool = False
    connection_status: str = "untested"
    last_tested_at: datetime | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LessonGenerationRun(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(index=True)
    initiated_by_id: int = Field(index=True)
    status: str = "pending"
    total_items: int = 0
    succeeded_items: int = 0
    failed_items: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None


class LessonGenerationItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(index=True)
    outline_row_id: int = Field(index=True)
    lesson_plan_id: int | None = Field(default=None, index=True)
    status: str = "pending"
    attempts: int = 0
    duration_ms: int = 0
    error_code: str = ""


class LessonRevisionCandidate(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    lesson_plan_id: int = Field(index=True)
    field_name: str
    original_content: str
    proposed_content: str
    teacher_instruction: str = ""
    status: str = "pending"
    created_by_id: int = Field(index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OutlineRevisionCandidate(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(index=True)
    outline_row_id: int = Field(index=True)
    field_name: str
    original_content: str
    proposed_content: str
    teacher_instruction: str = ""
    source_updated_at: datetime
    status: str = "pending"
    created_by_id: int = Field(index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
