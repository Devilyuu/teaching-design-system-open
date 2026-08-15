from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    employee_no: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class PasswordReset(BaseModel):
    password: str


class StatusResponse(BaseModel):
    status: str


class UserRead(BaseModel):
    id: int
    employee_no: str
    name: str
    role: str
    is_active: bool
    major_ids: list[int] = []


class MajorCreate(BaseModel):
    name: str
    short_name: str = ""
    is_active: bool = True


class MajorRead(MajorCreate):
    id: int


class UserCreate(BaseModel):
    employee_no: str
    name: str
    password: str
    role: str = "teacher"
    major_ids: list[int] = []
    is_active: bool = True


class TeachingTaskCreate(BaseModel):
    major_id: int | None = None
    term: str
    major: str
    class_name: str
    course_name: str
    teacher_name: str
    location: str
    total_hours: int = 32
    hours_per_session: int = 4


class TeachingTaskRead(TeachingTaskCreate):
    id: int
    owner_id: int | None = None
    status: str
    course_standard_uploaded: bool = False
    talent_plan_uploaded: bool = False
    sources_confirmed: bool = False
    schedule_uploaded: bool = False
    outline_template_uploaded: bool = False
    lesson_template_uploaded: bool = False
    outline_rows_count: int = 0
    lesson_plans_count: int = 0
    session_count: int = 0
    completed_sessions_count: int = 0
    next_session_no: int | None = None
    next_session_date: str = ""
    next_session_weekday: str = ""
    next_session_periods: str = ""


class ParseSummary(BaseModel):
    task_id: int
    goals_count: int = 0
    projects_count: int = 0
    indicators_count: int = 0
    sessions_count: int = 0


class AbilityIndicatorRead(BaseModel):
    code: str
    category: str
    group_code: str
    description: str


class CourseGoalReviewRead(BaseModel):
    code: str
    description: str
    ability_codes: list[str]
    indicators: list[AbilityIndicatorRead]
    unknown_codes: list[str]


class SourceReviewRead(BaseModel):
    task_id: int
    goals: list[CourseGoalReviewRead]
    indicators_count: int
    unknown_codes: list[str]
    can_confirm: bool
    confirmed: bool


class MaterialReadinessRead(BaseModel):
    kind: str
    # 与前端 types.ts 的 MaterialReadiness 保持一致。课表走候选流程时会停在
    # awaiting_confirmation（等老师确认教学班），漏掉它会让 /readiness 直接 500 ——
    # 服务层测试断言得到这个值，但它不过 FastAPI 的 response_model 校验，抓不到。
    status: Literal["missing", "ready", "attention", "awaiting_confirmation"]
    filename: str = ""
    uploaded_at: datetime | None = None
    uploaded_by: str = ""
    message: str
    summary: dict = Field(default_factory=dict)


class ReadinessBlockerRead(BaseModel):
    code: str
    message: str
    material_kind: str | None = None


class ReviewNoticeRead(BaseModel):
    id: int
    artifact_type: str
    reason: str
    created_at: datetime


class CourseReadinessRead(BaseModel):
    task_id: int
    materials: dict[str, MaterialReadinessRead]
    source_review: SourceReviewRead
    schedule_hours: int
    expected_hours: int
    can_generate_outline: bool
    blocking_reasons: list[ReadinessBlockerRead]
    next_action: Literal["complete_materials", "confirm_sources", "generate_outline", "open_outline"]
    pending_schedule: dict | None = None
    review_notices: list[ReviewNoticeRead] = Field(default_factory=list)


class ScheduleChangeRead(BaseModel):
    session_no: int
    change_type: Literal["added", "removed", "changed"]
    fields: list[str]
    before: dict | None = None
    after: dict | None = None


class ExportRecordRead(BaseModel):
    id: int
    artifact_type: str
    artifact_label: str
    filename: str
    size_bytes: int
    template_filename: str
    source_summary: str
    session_no: int | None
    exported_by: str
    created_at: datetime
    available: bool


class WorkbenchStatusRead(BaseModel):
    configured: bool
    message: str = ""


class WorkbenchPushRead(BaseModel):
    id: str
    status: str
    created: bool
    replaced: bool


class ScheduleSessionPreview(BaseModel):
    session_no: int
    week_no: int
    date_text: str
    weekday: str
    periods: str
    course_name: str
    class_name: str
    location: str
    hours: int


class ScheduleColumnMatchRead(BaseModel):
    field: str
    column_index: int
    header_text: str
    confidence: Literal["exact", "alias", "manual"]


class ScheduleCandidateRead(BaseModel):
    id: int
    task_id: int
    filename: str
    status: str
    session_count: int
    total_hours: int
    added_count: int
    removed_count: int
    changed_count: int
    can_confirm: bool
    blocking_message: str = ""
    changes: list[ScheduleChangeRead]
    sessions: list[ScheduleSessionPreview] = []
    header_row: int = 0
    matches: list[ScheduleColumnMatchRead] = []
    detected_headers: list[str] = []
    unmapped_headers: list[str] = []
    warnings: list[str] = []
    course_names: list[str] = []
    course_filter: str = ""
    teaching_classes: list[str] = []
    teaching_class: str = ""


class ScheduleRemapRequest(BaseModel):
    header_row: int | None = None
    mapping: dict[str, int] | None = None
    course_name: str | None = None
    teaching_class: str | None = None


class OutlineRowRead(BaseModel):
    id: int
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
    note: str
    updated_at: datetime
    post_class_recorded: bool = False
    has_previous_adjustment: bool = False


class OutlineRowUpdate(BaseModel):
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
    note: str = ""


class OutlineRevisionRequest(BaseModel):
    field_name: Literal["topic", "teaching_content", "teaching_methods", "tasks", "all"]
    instruction: str = Field(default="", max_length=500)


class OutlineRevisionCandidateRead(BaseModel):
    id: int
    task_id: int
    outline_row_id: int
    field_name: str
    original_content: str
    proposed_content: str
    teacher_instruction: str
    status: str
    created_at: datetime


class LessonPlanRead(BaseModel):
    id: int
    task_id: int
    outline_row_id: int
    session_no: int
    title: str
    duration_minutes: int
    teaching_goals: str
    key_points: str
    difficult_points: str
    teaching_preparation: str
    teaching_process: str
    summary: str
    homework: str
    reflection: str
    course_goal_codes: str
    ability_codes: str
    generation_source: str
    review_status: str


class LessonPlanUpdate(BaseModel):
    title: str
    duration_minutes: int
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


class SessionMaterialGenerate(BaseModel):
    material_type: Literal["assignment", "test"]
    difficulty: Literal["basic", "medium", "advanced"] = "medium"
    estimated_minutes: int = Field(default=40, gt=0, le=600)
    question_count: int = Field(default=5, gt=0, le=50)


class SessionMaterialRead(BaseModel):
    id: int
    task_id: int
    outline_row_id: int
    owner_user_id: int
    material_type: str
    title: str
    content: str
    reference_answer: str
    grading_criteria: str
    difficulty: str
    estimated_minutes: int
    course_goal_codes: str
    ability_codes: str
    source_status: str
    generation_method: str
    created_at: datetime
    updated_at: datetime


class SessionMaterialUpdate(BaseModel):
    title: str
    content: str
    reference_answer: str
    grading_criteria: str
    difficulty: Literal["basic", "medium", "advanced"]
    estimated_minutes: int = Field(gt=0, le=600)


class PostClassReflectionUpsert(BaseModel):
    progress_status: Literal["completed", "partial", "not_completed"]
    mastery_level: Literal["good", "average", "weak"]
    classroom_effect: Literal["smooth", "normal", "needs_adjustment"]
    note: str = Field(default="", max_length=500)


class PostClassReflectionRead(BaseModel):
    id: int
    task_id: int
    outline_row_id: int
    owner_user_id: int
    progress_status: str
    mastery_level: str
    classroom_effect: str
    note: str
    suggestion_type: str
    suggestion_text: str
    suggested_minutes: int
    status: str
    target_outline_row_id: int | None
    applied_lesson_plan_id: int | None
    created_at: datetime
    updated_at: datetime
    applied_at: datetime | None
    reverted_at: datetime | None


class SessionWorkspaceRead(BaseModel):
    outline: OutlineRowRead
    lesson: LessonPlanRead | None
    materials: list[SessionMaterialRead]
    reflection: PostClassReflectionRead | None
    next_outline: OutlineRowRead | None
    next_lesson_exists: bool


class AiModelConfigUpdate(BaseModel):
    base_url: str = Field(min_length=1, max_length=500)
    model_name: str = Field(min_length=1, max_length=200)
    api_key: str = Field(default="", max_length=1000)


class AiModelEnable(BaseModel):
    enabled: bool


class AiModelConfigRead(BaseModel):
    id: int | None
    base_url: str
    model_name: str
    api_key_status: str
    enabled: bool
    connection_status: str
    last_tested_at: datetime | None
    updated_at: datetime | None


class LessonGenerationItemRead(BaseModel):
    id: int
    outline_row_id: int
    lesson_plan_id: int | None
    status: str
    attempts: int
    duration_ms: int
    error_code: str


class LessonGenerationRunRead(BaseModel):
    id: int
    task_id: int
    status: str
    total_items: int
    succeeded_items: int
    failed_items: int
    created_at: datetime
    finished_at: datetime | None
    items: list[LessonGenerationItemRead]


class LessonRevisionRequest(BaseModel):
    field_name: Literal[
        "teaching_goals",
        "key_points",
        "difficult_points",
        "teaching_preparation",
        "teaching_process",
        "summary",
        "homework",
    ]
    instruction: str = Field(default="", max_length=500)


class LessonRevisionCandidateRead(BaseModel):
    id: int
    lesson_plan_id: int
    field_name: str
    original_content: str
    proposed_content: str
    teacher_instruction: str
    status: str
    created_at: datetime
