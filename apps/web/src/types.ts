export type TaskStatus =
  | "materials_pending"
  | "outline_ready"
  | "lesson_pending"
  | "completed";

export interface TeachingTask {
  id: number;
  term: string;
  major: string;
  class_name: string;
  course_name: string;
  teacher_name: string;
  location: string;
  total_hours: number;
  hours_per_session: number;
  status: TaskStatus | string;
  course_standard_uploaded?: boolean;
  talent_plan_uploaded?: boolean;
  sources_confirmed?: boolean;
  schedule_uploaded?: boolean;
  outline_template_uploaded?: boolean;
  lesson_template_uploaded?: boolean;
  outline_rows_count?: number;
  lesson_plans_count?: number;
  session_count?: number;
  completed_sessions_count?: number;
  next_session_no?: number | null;
  next_session_date?: string;
  next_session_weekday?: string;
  next_session_periods?: string;
}

export type TeachingTaskCreate = Omit<TeachingTask, "id" | "status">;

export interface CurrentUser {
  id: number;
  employee_no: string;
  name: string;
  role: "admin" | "teacher" | string;
  is_active: boolean;
  /** Set whenever an admin chose the password; the app forces a change before anything else. */
  must_change_password?: boolean;
  major_ids: number[];
}

export interface Major {
  id: number;
  name: string;
  short_name: string;
  is_active: boolean;
}

export interface ManagedUser extends CurrentUser {}

export interface UserCreate {
  employee_no: string;
  name: string;
  /** Empty means the employee number becomes the initial password. */
  password: string;
  role: "admin" | "teacher";
  major_ids: number[];
  is_active: boolean;
}

export interface UserUpdate {
  name?: string;
  is_active?: boolean;
  major_ids?: number[];
}

export interface UserBatchItem {
  employee_no: string;
  name: string;
}

export interface UserBatchResult {
  created: ManagedUser[];
  skipped: string[];
}

export interface ParseSummary {
  task_id: number;
  goals_count: number;
  indicators_count: number;
  sessions_count: number;
  projects_count: number;
}

export interface AbilityIndicatorReview {
  code: string;
  category: string;
  group_code: string;
  description: string;
}

export interface CourseGoalReview {
  code: string;
  description: string;
  ability_codes: string[];
  indicators: AbilityIndicatorReview[];
  unknown_codes: string[];
}

export interface SourceReview {
  task_id: number;
  goals: CourseGoalReview[];
  indicators_count: number;
  unknown_codes: string[];
  can_confirm: boolean;
  confirmed: boolean;
}

export interface MaterialReadiness {
  kind: string;
  status: "missing" | "ready" | "attention" | "awaiting_confirmation";
  filename: string;
  message: string;
  summary: Record<string, unknown>;
}

export interface ExportRecord {
  id: number;
  artifact_type: "outline" | "lesson" | "session_material";
  artifact_label: string;
  filename: string;
  size_bytes: number;
  template_filename: string;
  source_summary: string;
  session_no: number | null;
  exported_by: string;
  created_at: string;
  available: boolean;
}

export type ScheduleField =
  | "week_no"
  | "date_text"
  | "weekday"
  | "periods"
  | "course_name"
  | "class_name"
  | "location";

export interface ScheduleColumnMatch {
  field: ScheduleField;
  column_index: number;
  header_text: string;
  confidence: "exact" | "alias" | "manual";
}

export interface ScheduleSessionPreview {
  session_no: number;
  week_no: number;
  date_text: string;
  weekday: string;
  periods: string;
  course_name: string;
  class_name: string;
  location: string;
  hours: number;
}

export interface WorkbenchStatus {
  configured: boolean;
  message: string;
}

export interface WorkbenchPushResult {
  id: string;
  status: string;
  created: boolean;
  replaced: boolean;
}

export interface ScheduleRemapInput {
  header_row: number;
  mapping: Partial<Record<ScheduleField, number>>;
  course_name: string;
  teaching_class: string;
}

export interface ScheduleCandidate {
  id: number;
  status: string;
  filename: string;
  session_count: number;
  total_hours: number;
  added_count: number;
  removed_count: number;
  changed_count: number;
  can_confirm: boolean;
  blocking_message: string;
  sessions: ScheduleSessionPreview[];
  header_row: number;
  matches: ScheduleColumnMatch[];
  detected_headers: string[];
  unmapped_headers: string[];
  warnings: string[];
  course_names: string[];
  course_filter: string;
  teaching_classes: string[];
  teaching_class: string;
}

export interface CourseReadiness {
  task_id: number;
  materials: Record<string, MaterialReadiness>;
  source_review: SourceReview;
  schedule_hours: number;
  expected_hours: number;
  can_generate_outline: boolean;
  blocking_reasons: Array<{ code: string; message: string; material_kind?: string }>;
  next_action: "complete_materials" | "confirm_sources" | "generate_outline" | "open_outline";
  pending_schedule: ScheduleCandidate | null;
  review_notices: Array<{ id: number; artifact_type: string; reason: string }>;
}

export interface OutlineRow {
  id: number;
  session_no: number;
  date_text: string;
  week_no: number;
  weekday: string;
  periods: string;
  topic: string;
  teaching_content: string;
  ideological_point: string;
  teaching_methods: string;
  pre_task: string;
  in_class_task: string;
  post_task: string;
  course_goal_codes: string;
  ability_codes: string;
  note: string;
  updated_at: string;
  post_class_recorded?: boolean;
  has_previous_adjustment?: boolean;
}

export type OutlineRevisionField = "topic" | "teaching_content" | "teaching_methods" | "tasks" | "all";

export interface OutlineRevisionCandidate {
  id: number;
  task_id: number;
  outline_row_id: number;
  field_name: OutlineRevisionField;
  original_content: string;
  proposed_content: string;
  teacher_instruction: string;
  status: "pending" | "accepted" | "rejected";
  created_at: string;
}

export interface LessonPlan {
  id: number;
  task_id: number;
  outline_row_id: number;
  session_no: number;
  title: string;
  duration_minutes: number;
  teaching_goals: string;
  key_points: string;
  difficult_points: string;
  teaching_preparation: string;
  teaching_process: string;
  summary: string;
  homework: string;
  reflection: string;
  course_goal_codes: string;
  ability_codes: string;
  generation_source: "ai" | "manual" | string;
  review_status: "draft" | "reviewed" | string;
}

export interface AiModelConfig {
  id: number | null;
  base_url: string;
  model_name: string;
  api_key_status: string;
  enabled: boolean;
  connection_status: "unconfigured" | "untested" | "connected" | "failed" | string;
  last_tested_at: string | null;
  updated_at: string | null;
}

export interface AiModelConfigUpdate {
  base_url: string;
  model_name: string;
  api_key: string;
}

export interface LessonGenerationItem {
  id: number;
  outline_row_id: number;
  lesson_plan_id: number | null;
  status: "pending" | "running" | "succeeded" | "failed";
  attempts: number;
  duration_ms: number;
  error_code: string;
}

export interface LessonGenerationRun {
  id: number;
  task_id: number;
  status: "pending" | "running" | "completed" | "completed_with_errors" | "failed";
  total_items: number;
  succeeded_items: number;
  failed_items: number;
  created_at: string;
  finished_at: string | null;
  items: LessonGenerationItem[];
}

export type LessonRevisionField = "teaching_goals" | "key_points" | "difficult_points" | "teaching_preparation" | "teaching_process" | "summary" | "homework";

export interface LessonRevisionCandidate {
  id: number;
  lesson_plan_id: number;
  field_name: LessonRevisionField;
  original_content: string;
  proposed_content: string;
  teacher_instruction: string;
  status: "pending" | "accepted" | "rejected";
  created_at: string;
}

export type SessionMaterialType = "assignment" | "test";
export type SessionMaterialDifficulty = "basic" | "medium" | "advanced";

export interface SessionMaterial {
  id: number;
  task_id: number;
  outline_row_id: number;
  owner_user_id: number;
  material_type: SessionMaterialType;
  title: string;
  content: string;
  reference_answer: string;
  grading_criteria: string;
  difficulty: SessionMaterialDifficulty;
  estimated_minutes: number;
  course_goal_codes: string;
  ability_codes: string;
  source_status: "outline_and_lesson" | "outline_only";
  generation_method: "rule" | "ai";
  created_at: string;
  updated_at: string;
}

export interface SessionWorkspace {
  outline: OutlineRow;
  lesson: LessonPlan | null;
  materials: SessionMaterial[];
  reflection: PostClassReflection | null;
  next_outline: OutlineRow | null;
  next_lesson_exists: boolean;
}

export type ProgressStatus = "completed" | "partial" | "not_completed";
export type MasteryLevel = "good" | "average" | "weak";
export type ClassroomEffect = "smooth" | "normal" | "needs_adjustment";

export interface PostClassReflectionInput {
  progress_status: ProgressStatus;
  mastery_level: MasteryLevel;
  classroom_effect: ClassroomEffect;
  note: string;
}

export interface PostClassReflection extends PostClassReflectionInput {
  id: number;
  task_id: number;
  outline_row_id: number;
  owner_user_id: number;
  suggestion_type: string;
  suggestion_text: string;
  suggested_minutes: number;
  status: "pending" | "applied" | "reverted";
  target_outline_row_id: number | null;
  applied_lesson_plan_id: number | null;
  created_at: string;
  updated_at: string;
  applied_at: string | null;
  reverted_at: string | null;
}

export interface SessionMaterialGenerateInput {
  material_type: SessionMaterialType;
  difficulty: SessionMaterialDifficulty;
  estimated_minutes: number;
  question_count: number;
}
