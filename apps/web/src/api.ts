import type {
  AiModelConfig,
  AiModelConfigUpdate,
  CurrentUser,
  CourseReadiness,
  ExportRecord,
  LessonGenerationRun,
  LessonRevisionCandidate,
  LessonRevisionField,
  LessonPlan,
  Major,
  ManagedUser,
  OutlineRevisionCandidate,
  OutlineRevisionField,
  OutlineRow,
  ParseSummary,
  PostClassReflection,
  PostClassReflectionInput,
  SessionMaterial,
  SessionMaterialGenerateInput,
  SessionWorkspace,
  ScheduleCandidate,
  ScheduleRemapInput,
  WorkbenchPushResult,
  WorkbenchStatus,
  SourceReview,
  TeachingTask,
  TeachingTaskCreate,
  UserCreate
} from "./types";

export function resolveApiBaseUrl(configuredUrl: string | undefined, isDev: boolean, baseUrl: string): string {
  if (configuredUrl) return configuredUrl;
  if (isDev) return "http://localhost:8000";
  return `${baseUrl.replace(/\/$/, "")}/api`;
}

const API_BASE_URL = resolveApiBaseUrl(
  import.meta.env.VITE_API_BASE_URL,
  import.meta.env.DEV,
  import.meta.env.BASE_URL
);
export const TOKEN_KEY = "teachingDesignToken";

export function getStoredToken(): string {
  return localStorage.getItem(TOKEN_KEY) ?? "";
}

export function setStoredToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearStoredToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  readonly status: number;
  readonly detectedHeaders: string[];
  readonly missingFields: string[];
  /** Courses the timetable does list, sent back when none of them matched the course record. */
  readonly courseNames: string[];

  constructor(
    message: string,
    status: number,
    detectedHeaders: string[] = [],
    missingFields: string[] = [],
    courseNames: string[] = []
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detectedHeaders = detectedHeaders;
    this.missingFields = missingFields;
    this.courseNames = courseNames;
  }
}

async function buildRequestError(response: Response): Promise<Error> {
  const text = await response.text();
  const fallback = text || `Request failed with ${response.status}`;
  try {
    const detail = (JSON.parse(text) as { detail?: unknown }).detail;
    if (typeof detail === "string") return new ApiError(detail, response.status);
    if (detail && typeof detail === "object") {
      const parsed = detail as {
        message?: string;
        detected_headers?: string[];
        missing_fields?: string[];
        course_names?: string[];
      };
      return new ApiError(
        parsed.message ?? fallback,
        response.status,
        parsed.detected_headers ?? [],
        parsed.missing_fields ?? [],
        parsed.course_names ?? []
      );
    }
  } catch {
    // Not a JSON body; fall through to the raw text.
  }
  return new ApiError(fallback, response.status);
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const isFormData = options?.body instanceof FormData;
  const token = getStoredToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: isFormData
      ? {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...options?.headers
        }
      : {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...options?.headers
        },
    ...options
  });

  if (!response.ok) {
    throw await buildRequestError(response);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function login(employeeNo: string, password: string): Promise<string> {
  const response = await request<{ access_token: string }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ employee_no: employeeNo, password })
  });
  setStoredToken(response.access_token);
  return response.access_token;
}

export function getCurrentUser(): Promise<CurrentUser> {
  return request<CurrentUser>("/auth/me");
}

export function listMajors(): Promise<Major[]> {
  return request<Major[]>("/majors");
}

export function listAdminMajors(): Promise<Major[]> {
  return request<Major[]>("/admin/majors");
}

export function createMajor(payload: Omit<Major, "id">): Promise<Major> {
  return request<Major>("/admin/majors", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function listAdminUsers(): Promise<ManagedUser[]> {
  return request<ManagedUser[]>("/admin/users");
}

export function getAiModelConfig(): Promise<AiModelConfig> {
  return request<AiModelConfig>("/admin/ai-model");
}

export function updateAiModelConfig(payload: AiModelConfigUpdate): Promise<AiModelConfig> {
  return request<AiModelConfig>("/admin/ai-model", {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function testAiModelConfig(): Promise<AiModelConfig> {
  return request<AiModelConfig>("/admin/ai-model/test", { method: "POST" });
}

export function enableAiModelConfig(enabled: boolean): Promise<AiModelConfig> {
  return request<AiModelConfig>("/admin/ai-model/enable", {
    method: "POST",
    body: JSON.stringify({ enabled })
  });
}

export function startLessonGeneration(taskId: number): Promise<LessonGenerationRun> {
  return request<LessonGenerationRun>(`/tasks/${taskId}/lesson-generation-runs`, { method: "POST" });
}

export function getLessonGenerationRun(taskId: number, runId: number): Promise<LessonGenerationRun> {
  return request<LessonGenerationRun>(`/tasks/${taskId}/lesson-generation-runs/${runId}`);
}

export function retryLessonGenerationItem(taskId: number, runId: number, itemId: number): Promise<LessonGenerationRun> {
  return request<LessonGenerationRun>(`/tasks/${taskId}/lesson-generation-runs/${runId}/items/${itemId}/retry`, {
    method: "POST"
  });
}

export function createLessonRevisionCandidate(taskId: number, lessonId: number, fieldName: LessonRevisionField, instruction: string): Promise<LessonRevisionCandidate> {
  return request<LessonRevisionCandidate>(`/tasks/${taskId}/lessons/${lessonId}/revision-candidates`, {
    method: "POST",
    body: JSON.stringify({ field_name: fieldName, instruction })
  });
}

export function acceptLessonRevisionCandidate(taskId: number, candidateId: number): Promise<LessonRevisionCandidate> {
  return request<LessonRevisionCandidate>(`/tasks/${taskId}/lesson-revision-candidates/${candidateId}/accept`, { method: "POST" });
}

export function rejectLessonRevisionCandidate(taskId: number, candidateId: number): Promise<LessonRevisionCandidate> {
  return request<LessonRevisionCandidate>(`/tasks/${taskId}/lesson-revision-candidates/${candidateId}/reject`, { method: "POST" });
}

export function createUser(payload: UserCreate): Promise<ManagedUser> {
  return request<ManagedUser>("/admin/users", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function changePassword(currentPassword: string, newPassword: string): Promise<{ status: string }> {
  return request<{ status: string }>("/auth/change-password", {
    method: "POST",
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword })
  });
}

export function resetUserPassword(userId: number, password: string): Promise<{ status: string }> {
  return request<{ status: string }>(`/admin/users/${userId}/password`, {
    method: "POST",
    body: JSON.stringify({ password })
  });
}

export function listTasks(): Promise<TeachingTask[]> {
  return request<TeachingTask[]>("/tasks");
}

export function createTask(payload: TeachingTaskCreate): Promise<TeachingTask> {
  return request<TeachingTask>("/tasks", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateTask(taskId: number, payload: Partial<TeachingTaskCreate>): Promise<TeachingTask> {
  return request<TeachingTask>(`/tasks/${taskId}`, {
    method: "PATCH",
    body: JSON.stringify(payload)
  });
}

export function deleteTask(taskId: number): Promise<void> {
  return request<void>(`/tasks/${taskId}`, { method: "DELETE" });
}

export function listOutlineRows(taskId: number): Promise<OutlineRow[]> {
  return request<OutlineRow[]>(`/tasks/${taskId}/outline`);
}

export function updateOutlineRow(taskId: number, row: OutlineRow): Promise<OutlineRow> {
  const { id, session_no: _sessionNo, updated_at: _updatedAt, ...payload } = row;
  return request<OutlineRow>(`/tasks/${taskId}/outline/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function getCourseReadiness(taskId: number): Promise<CourseReadiness> {
  return request<CourseReadiness>(`/tasks/${taskId}/readiness`);
}

export function uploadScheduleCandidate(
  taskId: number,
  file: File,
  options?: Partial<ScheduleRemapInput>
): Promise<ScheduleCandidate> {
  const body = new FormData();
  body.append("file", file);
  if (options?.header_row !== undefined) body.append("header_row", String(options.header_row));
  if (options?.mapping) body.append("mapping", JSON.stringify(options.mapping));
  if (options?.course_name !== undefined) body.append("course_name", options.course_name);
  if (options?.teaching_class !== undefined) body.append("teaching_class", options.teaching_class);
  return request<ScheduleCandidate>(`/tasks/${taskId}/schedule-candidates`, { method: "POST", body });
}

export function remapScheduleCandidate(
  taskId: number,
  candidateId: number,
  payload: ScheduleRemapInput
): Promise<ScheduleCandidate> {
  return request<ScheduleCandidate>(`/tasks/${taskId}/schedule-candidates/${candidateId}/remap`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function confirmScheduleCandidate(taskId: number, candidateId: number): Promise<ScheduleCandidate> {
  return request<ScheduleCandidate>(`/tasks/${taskId}/schedule-candidates/${candidateId}/confirm`, { method: "POST" });
}

export function discardScheduleCandidate(taskId: number, candidateId: number): Promise<ScheduleCandidate> {
  return request<ScheduleCandidate>(`/tasks/${taskId}/schedule-candidates/${candidateId}/discard`, { method: "POST" });
}

export function resolveReviewNotice(taskId: number, noticeId: number): Promise<{ status: string }> {
  return request<{ status: string }>(`/tasks/${taskId}/review-notices/${noticeId}/resolve`, { method: "POST" });
}

export function createOutlineRevisionCandidate(
  taskId: number,
  rowId: number,
  fieldName: OutlineRevisionField,
  instruction = ""
): Promise<OutlineRevisionCandidate> {
  return request<OutlineRevisionCandidate>(`/tasks/${taskId}/outline/${rowId}/revision-candidates`, {
    method: "POST",
    body: JSON.stringify({ field_name: fieldName, instruction })
  });
}

export function acceptOutlineRevisionCandidate(taskId: number, candidateId: number): Promise<OutlineRevisionCandidate> {
  return request<OutlineRevisionCandidate>(`/tasks/${taskId}/outline-revision-candidates/${candidateId}/accept`, {
    method: "POST"
  });
}

export function rejectOutlineRevisionCandidate(taskId: number, candidateId: number): Promise<OutlineRevisionCandidate> {
  return request<OutlineRevisionCandidate>(`/tasks/${taskId}/outline-revision-candidates/${candidateId}/reject`, {
    method: "POST"
  });
}

function uploadFile<T>(path: string, file: File): Promise<T> {
  const body = new FormData();
  body.append("file", file);
  return request<T>(path, { method: "POST", body });
}

export function uploadCourseStandard(taskId: number, file: File): Promise<ParseSummary> {
  return uploadFile<ParseSummary>(`/tasks/${taskId}/course-standard`, file);
}

export function uploadTalentPlan(taskId: number, file: File): Promise<ParseSummary> {
  return uploadFile<ParseSummary>(`/tasks/${taskId}/talent-plan`, file);
}

export function getSourceReview(taskId: number): Promise<SourceReview> {
  return request<SourceReview>(`/tasks/${taskId}/sources/review`);
}

export function confirmSources(taskId: number): Promise<SourceReview> {
  return request<SourceReview>(`/tasks/${taskId}/sources/confirm`, { method: "POST" });
}

export function uploadSchedule(taskId: number, file: File): Promise<ParseSummary> {
  return uploadFile<ParseSummary>(`/tasks/${taskId}/schedule`, file);
}

export function uploadTemplate(taskId: number, kind: "outline" | "lesson", file: File): Promise<{ kind: string; filename: string; size: number }> {
  return uploadFile<{ kind: string; filename: string; size: number }>(`/tasks/${taskId}/templates/${kind}`, file);
}

export function generateOutline(taskId: number): Promise<OutlineRow[]> {
  return request<OutlineRow[]>(`/tasks/${taskId}/outline/generate`, { method: "POST" });
}

/** Rewrite the outline's prose. The schedule, resources and assessment stay put. */
export function regenerateOutlineSections(taskId: number): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>(`/tasks/${taskId}/outline/sections/regenerate`, {
    method: "POST"
  });
}

export async function exportOutline(taskId: number, template?: File | null): Promise<{ blob: Blob; filename: string }> {
  const body = template ? new FormData() : undefined;
  if (body && template) body.append("file", template);
  const token = getStoredToken();
  const response = await fetch(`${API_BASE_URL}/tasks/${taskId}/outline/export`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body
  });

  if (!response.ok) {
    // The refusals these endpoints raise are written for the teacher; throwing
    // the raw JSON body hid the sentence telling them what to fix.
    throw await buildRequestError(response);
  }

  const disposition = response.headers.get("Content-Disposition") ?? "";
  const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/)?.[1];
  return {
    blob: await response.blob(),
    filename: encodedName ? decodeURIComponent(encodedName) : "课程实施大纲.docx"
  };
}

export function listLessonPlans(taskId: number): Promise<LessonPlan[]> {
  return request<LessonPlan[]>(`/tasks/${taskId}/lessons`);
}

export function generateLessonPlans(taskId: number): Promise<LessonPlan[]> {
  return request<LessonPlan[]>(`/tasks/${taskId}/lessons/generate`, { method: "POST" });
}

export function updateLessonPlan(taskId: number, lesson: LessonPlan): Promise<LessonPlan> {
  const { id, task_id: _taskId, outline_row_id: _outlineRowId, session_no: _sessionNo, ...payload } = lesson;
  return request<LessonPlan>(`/tasks/${taskId}/lessons/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export async function exportLessonPlans(taskId: number, template?: File | null): Promise<{ blob: Blob; filename: string }> {
  const body = template ? new FormData() : undefined;
  if (body && template) body.append("file", template);
  const token = getStoredToken();
  const response = await fetch(`${API_BASE_URL}/tasks/${taskId}/lessons/export`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body
  });

  if (!response.ok) {
    // The refusals these endpoints raise are written for the teacher; throwing
    // the raw JSON body hid the sentence telling them what to fix.
    throw await buildRequestError(response);
  }

  const disposition = response.headers.get("Content-Disposition") ?? "";
  const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/)?.[1];
  return {
    blob: await response.blob(),
    filename: encodedName ? decodeURIComponent(encodedName) : "教案.docx"
  };
}

export function getSessionWorkspace(taskId: number, outlineRowId: number): Promise<SessionWorkspace> {
  return request<SessionWorkspace>(`/tasks/${taskId}/sessions/${outlineRowId}`);
}

export function generateSessionMaterial(
  taskId: number,
  outlineRowId: number,
  payload: SessionMaterialGenerateInput
): Promise<SessionMaterial> {
  return request<SessionMaterial>(`/tasks/${taskId}/sessions/${outlineRowId}/materials/generate`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateSessionMaterial(taskId: number, material: SessionMaterial): Promise<SessionMaterial> {
  const {
    id,
    task_id: _taskId,
    outline_row_id: _outlineRowId,
    owner_user_id: _ownerUserId,
    material_type: _materialType,
    course_goal_codes: _courseGoalCodes,
    ability_codes: _abilityCodes,
    source_status: _sourceStatus,
    generation_method: _generationMethod,
    created_at: _createdAt,
    updated_at: _updatedAt,
    ...payload
  } = material;
  return request<SessionMaterial>(`/tasks/${taskId}/materials/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function deleteSessionMaterial(taskId: number, materialId: number): Promise<void> {
  return request<void>(`/tasks/${taskId}/materials/${materialId}`, { method: "DELETE" });
}

export function upsertPostClassReflection(
  taskId: number,
  outlineRowId: number,
  payload: PostClassReflectionInput
): Promise<PostClassReflection> {
  return request<PostClassReflection>(`/tasks/${taskId}/sessions/${outlineRowId}/reflection`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function deletePostClassReflection(taskId: number, reflectionId: number): Promise<void> {
  return request<void>(`/tasks/${taskId}/reflections/${reflectionId}`, { method: "DELETE" });
}

export function applyPostClassReflection(taskId: number, reflectionId: number): Promise<LessonPlan> {
  return request<LessonPlan>(`/tasks/${taskId}/reflections/${reflectionId}/apply`, { method: "POST" });
}

export function revertPostClassReflection(taskId: number, reflectionId: number): Promise<LessonPlan> {
  return request<LessonPlan>(`/tasks/${taskId}/reflections/${reflectionId}/revert`, { method: "POST" });
}

export function listExports(taskId: number): Promise<ExportRecord[]> {
  return request<ExportRecord[]>(`/tasks/${taskId}/exports`);
}

export function getWorkbenchStatus(): Promise<WorkbenchStatus> {
  return request<WorkbenchStatus>("/integrations/workbench");
}

export function pushExportToWorkbench(taskId: number, exportId: number): Promise<WorkbenchPushResult> {
  return request<WorkbenchPushResult>(`/tasks/${taskId}/exports/${exportId}/push-to-workbench`, {
    method: "POST"
  });
}

export async function downloadExport(
  taskId: number,
  exportId: number
): Promise<{ blob: Blob; filename: string }> {
  const token = getStoredToken();
  const response = await fetch(`${API_BASE_URL}/tasks/${taskId}/exports/${exportId}/download`, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined
  });
  if (!response.ok) {
    throw await buildRequestError(response);
  }
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/)?.[1];
  return {
    blob: await response.blob(),
    filename: encodedName ? decodeURIComponent(encodedName) : "备课文档.docx"
  };
}

export async function exportSessionMaterial(
  taskId: number,
  materialId: number
): Promise<{ blob: Blob; filename: string }> {
  const token = getStoredToken();
  const response = await fetch(`${API_BASE_URL}/tasks/${taskId}/materials/${materialId}/export`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined
  });
  if (!response.ok) {
    // The refusals these endpoints raise are written for the teacher; throwing
    // the raw JSON body hid the sentence telling them what to fix.
    throw await buildRequestError(response);
  }
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/)?.[1];
  return {
    blob: await response.blob(),
    filename: encodedName ? decodeURIComponent(encodedName) : "备课材料.docx"
  };
}
