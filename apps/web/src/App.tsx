import {
  BookOpenCheck,
  Download,
  FilePlus2,
  LayoutDashboard,
  NotebookTabs,
  Plus,
  RefreshCw,
  Save,
  Search,
  Settings2,
  Sparkles,
  Table2,
  Upload
} from "lucide-react";
import { FormEvent, Fragment, ReactNode, useEffect, useMemo, useRef, useState } from "react";

import {
  changePassword,
  clearStoredToken,
  acceptOutlineRevisionCandidate,
  createOutlineRevisionCandidate,
  createMajor,
  createTask,
  createUser,
  createUsersBatch,
  deleteTask,
  exportLessonPlans,
  exportOutline,
  getCurrentUser,
  getTeacherProfile,
  getSourceReview,
  getStoredToken,
  listAdminMajors,
  listAdminUsers,
  listLessonPlans,
  listMajors,
  listOutlineRows,
  listTasks,
  login,
  regenerateOutlineSections,
  rejectOutlineRevisionCandidate,
  resetUserPassword,
  updateLessonPlan,
  updateTask,
  updateTeacherProfile,
  updateUser,
  updateOutlineRow
} from "./api";
import type { CurrentUser, LessonPlan, Major, ManagedUser, OutlineRevisionCandidate, OutlineRevisionField, OutlineRow, SourceReview, TeacherProfile, TeachingTask, TeachingTaskCreate } from "./types";
import SessionWorkspacePage from "./SessionWorkspacePage";
import AiModelConfigPanel from "./AiModelConfigPanel";
import LessonGenerationProgress from "./LessonGenerationProgress";
import LessonRevisionControl from "./LessonRevisionControl";
import CourseMaterialsPage from "./CourseMaterialsPage";
import ExportHistoryPanel from "./ExportHistoryPanel";
import { parseTeacherRoster } from "./teacherRoster";

type View = "dashboard" | "courses" | "new-task" | "course" | "admin" | "account";
type WorkspaceTab = "overview" | "materials" | "outline" | "lessons" | "sessions" | "exports";

const emptyTask: TeachingTaskCreate = {
  term: "2026-2027 第一学期",
  major: "数字媒体艺术设计",
  class_name: "数字艺术 25 级 1 班",
  course_name: "人工智能与创意设计",
  teacher_name: "",
  location: "智慧教室 / 数字媒体实训室",
  total_hours: 32,
  hours_per_session: 4
};

const pageMeta: Record<View, { title: string; subtitle: string }> = {
  dashboard: {
    title: "教师工作台",
    subtitle: "查看下一次课、待完成备课和最近使用的学期课程"
  },
  courses: {
    title: "我的课程",
    subtitle: "按学期管理课程实施大纲、整门课教案和每次课材料"
  },
  "new-task": {
    title: "新建学期课程",
    subtitle: "填写课程基本信息，保存后统一准备课程资料"
  },
  course: {
    title: "课程工作台",
    subtitle: "从学期规划到每次课备课，所有内容都保留在当前课程中"
  },
  admin: {
    title: "标准库与模板库",
    subtitle: "管理员维护人才培养方案、课程标准、公共模板、校历和 AI 配置"
  },
  account: {
    title: "个人信息与密码",
    subtitle: "个人信息会写入每门课课程实施大纲的「教师信息」；密码修改后旧密码立即失效"
  }
};

export default function App() {
  const [view, setView] = useState<View>("dashboard");
  const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>("overview");
  const [tasks, setTasks] = useState<TeachingTask[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);
  const [outlineRows, setOutlineRows] = useState<OutlineRow[]>([]);
  const [lessonPlans, setLessonPlans] = useState<LessonPlan[]>([]);
  const [selectedLessonId, setSelectedLessonId] = useState<number | null>(null);
  const [selectedOutlineRowId, setSelectedOutlineRowId] = useState<number | null>(null);
  const [taskDraft, setTaskDraft] = useState<TeachingTaskCreate>(emptyTask);
  const [sourceReview, setSourceReview] = useState<SourceReview | null>(null);
  const [outlineCandidate, setOutlineCandidate] = useState<OutlineRevisionCandidate | null>(null);
  const [outlineRevisionBusy, setOutlineRevisionBusy] = useState(false);
  const [outlineSectionsBusy, setOutlineSectionsBusy] = useState(false);
  const [exportToken, setExportToken] = useState(0);
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [authChecked, setAuthChecked] = useState(false);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [error, setError] = useState("");
  const lessonLoadSeq = useRef(0);

  // The course record's 任课教师 is the account holder unless they say otherwise.
  useEffect(() => {
    if (!currentUser) return;
    setTaskDraft((draft) => (draft.teacher_name ? draft : { ...draft, teacher_name: currentUser.name }));
  }, [currentUser]);

  const selectedTask = useMemo(
    () => tasks.find((task) => task.id === selectedTaskId) ?? tasks[0],
    [selectedTaskId, tasks]
  );

  useEffect(() => {
    let isMounted = true;
    if (!getStoredToken()) {
      setAuthChecked(true);
      setLoading(false);
      return () => {
        isMounted = false;
      };
    }
    getCurrentUser()
      .then((user) => {
        if (!isMounted) return;
        setCurrentUser(user);
      })
      .catch(() => {
        clearStoredToken();
        if (isMounted) setCurrentUser(null);
      })
      .finally(() => {
        if (isMounted) setAuthChecked(true);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (!currentUser) return;
    loadTasks();
  }, [currentUser]);

  useEffect(() => {
    if (view !== "course" || !selectedTask?.id || !["outline", "sessions"].includes(workspaceTab)) return;
    let isMounted = true;
    listOutlineRows(selectedTask.id)
      .then((rows) => {
        if (isMounted) setOutlineRows(rows);
      })
      .catch((reason: Error) => {
        if (isMounted) setError(reason.message);
      });
    if (workspaceTab === "outline") {
      setSourceReview(null);
      setOutlineCandidate(null);
      getSourceReview(selectedTask.id)
        .then((review) => {
          if (isMounted) setSourceReview(review);
        })
        .catch((reason: Error) => {
          if (isMounted) setError(reason.message);
        });
    }
    return () => {
      isMounted = false;
    };
  }, [view, workspaceTab, selectedTask?.id]);

  useEffect(() => {
    if (view !== "course" || !selectedTask?.id || !["lessons", "sessions"].includes(workspaceTab)) return;
    const loadSeq = ++lessonLoadSeq.current;
    let isMounted = true;
    listLessonPlans(selectedTask.id)
      .then((lessons) => {
        if (!isMounted || loadSeq !== lessonLoadSeq.current) return;
        setLessonPlans(lessons);
        setSelectedLessonId(lessons[0]?.id ?? null);
      })
      .catch((reason: Error) => {
        if (!isMounted || loadSeq !== lessonLoadSeq.current) return;
        setLessonPlans([]);
        setSelectedLessonId(null);
        setError(reason.message);
      });
    return () => {
      isMounted = false;
    };
  }, [view, workspaceTab, selectedTask?.id]);

  async function loadTasks() {
    setLoading(true);
    try {
      const items = await listTasks();
      setTasks(items);
      setSelectedTaskId(items[0]?.id ?? null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "任务加载失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleLogin(employeeNo: string, password: string) {
    setError("");
    setLoading(true);
    try {
      await login(employeeNo, password);
      const user = await getCurrentUser();
      setCurrentUser(user);
    } catch (reason) {
      clearStoredToken();
      setError(reason instanceof Error ? reason.message : "登录失败");
    } finally {
      setLoading(false);
      setAuthChecked(true);
    }
  }

  function handleLogout() {
    clearStoredToken();
    setCurrentUser(null);
    setTasks([]);
    setSelectedTaskId(null);
    setView("dashboard");
  }

  function activate(nextView: View) {
    setNotice("");
    setError("");
    setView(nextView);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function openCourse(taskId: number, tab: WorkspaceTab = "overview") {
    setSelectedTaskId(taskId);
    setSelectedOutlineRowId(null);
    setWorkspaceTab(tab);
    activate("course");
  }

  async function handleUpdateTask(taskId: number, payload: Partial<TeachingTaskCreate>) {
    setError("");
    const updated = await updateTask(taskId, payload);
    setTasks((current) => current.map((task) => (task.id === updated.id ? updated : task)));
    setNotice("课程信息已保存");
  }

  async function handleDeleteTask(taskId: number) {
    setError("");
    await deleteTask(taskId);
    setTasks((current) => current.filter((task) => task.id !== taskId));
    setSelectedTaskId(null);
    setView("courses");
    setNotice("课程已删除");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function handleCreateTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      const created = await createTask(taskDraft);
      setTasks((current) => [created, ...current]);
      setSelectedTaskId(created.id);
      setWorkspaceTab("materials");
      setView("course");
      setNotice("任务已创建，请继续补充课程资料");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "任务创建失败");
    }
  }

  async function handleExportOutline() {
    if (!selectedTask) {
      setError("请先选择一个备课任务");
      return;
    }
    setError("");
    setNotice("正在生成 Word 文档...");
    try {
      const { blob, filename } = await exportOutline(selectedTask.id, null);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      anchor.click();
      URL.revokeObjectURL(url);
      setExportToken((current) => current + 1);
      setNotice(`已导出：${filename}，可在「导出记录」中重新下载`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Word 导出失败");
    }
  }

  /** Re-read the course summaries without touching the selection, unlike loadTasks. */
  async function refreshTasks() {
    try {
      setTasks(await listTasks());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "课程列表刷新失败");
    }
  }

  async function reloadLessonsAfterGeneration() {
    if (!selectedTask) return;
    const lessons = await listLessonPlans(selectedTask.id);
    setLessonPlans(lessons);
    setSelectedLessonId((current) => current && lessons.some((lesson) => lesson.id === current) ? current : lessons[0]?.id ?? null);
  }

  async function handleExportLessons() {
    if (!selectedTask) {
      setError("请先选择一个备课任务");
      return;
    }
    setError("");
    setNotice("正在生成教案 Word 文档...");
    try {
      const { blob, filename } = await exportLessonPlans(selectedTask.id, null);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      anchor.click();
      URL.revokeObjectURL(url);
      setExportToken((current) => current + 1);
      setNotice(`已导出：${filename}，可在「导出记录」中重新下载`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "教案 Word 导出失败");
    }
  }

  async function saveRow(row: OutlineRow): Promise<boolean> {
    if (!selectedTask) return false;
    try {
      const saved = await updateOutlineRow(selectedTask.id, row);
      setOutlineRows((current) => current.map((item) => (item.id === saved.id ? saved : item)));
      setNotice(`第 ${saved.session_no} 次课已保存`);
      return true;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存失败");
      return false;
    }
  }

  async function createOutlineRevision(rowId: number, fieldName: OutlineRevisionField) {
    if (!selectedTask) return;
    setOutlineRevisionBusy(true);
    setError("");
    try {
      const candidate = await createOutlineRevisionCandidate(selectedTask.id, rowId, fieldName);
      setOutlineCandidate(candidate);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "AI 优化失败");
    } finally {
      setOutlineRevisionBusy(false);
    }
  }

  async function regenerateOutlineBody() {
    if (!selectedTask) return;
    setOutlineSectionsBusy(true);
    setError("");
    setNotice("正在重新生成大纲正文，约需半分钟...");
    try {
      await regenerateOutlineSections(selectedTask.id);
      setNotice("大纲正文已重新生成，下次导出即为新内容");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "重新生成大纲正文失败");
      setNotice("");
    } finally {
      setOutlineSectionsBusy(false);
    }
  }

  async function acceptOutlineRevision() {
    if (!selectedTask || !outlineCandidate) return;
    const revisedRow = outlineRows.find((row) => row.id === outlineCandidate.outline_row_id);
    setOutlineRevisionBusy(true);
    setError("");
    try {
      await acceptOutlineRevisionCandidate(selectedTask.id, outlineCandidate.id);
      const rows = await listOutlineRows(selectedTask.id);
      setOutlineRows(rows);
      setOutlineCandidate(null);
      setNotice(`第 ${revisedRow?.session_no ?? "当前"} 次课已采用 AI 建议`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "采用建议失败");
    } finally {
      setOutlineRevisionBusy(false);
    }
  }

  async function rejectOutlineRevision() {
    if (!selectedTask || !outlineCandidate) return;
    setOutlineRevisionBusy(true);
    setError("");
    try {
      await rejectOutlineRevisionCandidate(selectedTask.id, outlineCandidate.id);
      setOutlineCandidate(null);
      setNotice("已放弃本次 AI 建议，原内容保持不变");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "放弃建议失败");
    } finally {
      setOutlineRevisionBusy(false);
    }
  }

  function patchLesson(lessonId: number, patch: Partial<LessonPlan>) {
    setLessonPlans((current) => current.map((lesson) => (lesson.id === lessonId ? { ...lesson, ...patch } : lesson)));
  }

  async function saveLesson(lesson: LessonPlan): Promise<boolean> {
    if (!selectedTask) return false;
    try {
      const saved = await updateLessonPlan(selectedTask.id, lesson);
      setLessonPlans((current) => current.map((item) => (item.id === saved.id ? saved : item)));
      setNotice(`第 ${saved.session_no} 次课教案已保存`);
      return true;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "教案保存失败");
      return false;
    }
  }

  const currentCourse = selectedTask ?? {
    ...emptyTask,
    id: 0,
    status: "materials_pending"
  };

  if (!authChecked) {
    return <div className="auth-shell"><div className="auth-card" role="status" aria-live="polite">正在检查登录状态...</div></div>;
  }

  if (!currentUser) {
    return <LoginPage error={error} loading={loading} onLogin={handleLogin} />;
  }

  if (currentUser.must_change_password) {
    return (
      <FirstLoginPasswordPage
        currentUser={currentUser}
        onChanged={async () => setCurrentUser(await getCurrentUser())}
        onLogout={handleLogout}
      />
    );
  }

  // The outline prints the teacher's office, phone and biography from this
  // profile; a teacher who skips it would export a 教师信息 block with blanks.
  if (currentUser.role !== "admin" && currentUser.profile_complete === false) {
    return (
      <FirstLoginProfilePage
        currentUser={currentUser}
        onSaved={async () => setCurrentUser(await getCurrentUser())}
        onLogout={handleLogout}
      />
    );
  }

  return (
    <div className="app">
      <Sidebar view={view} currentCourse={currentCourse} currentUser={currentUser} onChange={activate} />
      <main className="main">
        <Topbar
          view={view}
          currentUser={currentUser}
          onChange={activate}
          onLogout={handleLogout}
        />
        <div className="content">
          {notice && <div className="notice" role="status" aria-live="polite">{notice}</div>}
          {error && <div className="error" role="alert">{error}</div>}
          {view === "dashboard" && (
            <Dashboard
              tasks={tasks}
              loading={loading}
              onCreate={() => activate("new-task")}
              onOpenCourse={openCourse}
            />
          )}
          {view === "courses" && (
            <CoursesPage
              tasks={tasks}
              onOpen={openCourse}
              onCreate={() => activate("new-task")}
            />
          )}
          {view === "course" && selectedTask && (
            <CourseWorkspaceHeader task={selectedTask} tab={workspaceTab} onTabChange={setWorkspaceTab}>
              {workspaceTab === "overview" && (
                <CourseOverview
                  key={selectedTask.id}
                  task={selectedTask}
                  onOpenTab={setWorkspaceTab}
                  onUpdate={(payload) => handleUpdateTask(selectedTask.id, payload)}
                  onDelete={() => handleDeleteTask(selectedTask.id)}
                  onError={setError}
                />
              )}
              {workspaceTab === "materials" && (
                <CourseMaterialsPage
                  task={selectedTask}
                  onOpenOutline={() => setWorkspaceTab("outline")}
                  onError={setError}
                  onTaskChanged={() => void refreshTasks()}
                />
              )}
              {workspaceTab === "outline" && (
                <OutlineEditor
                  task={selectedTask}
                  rows={outlineRows}
                  setRows={setOutlineRows}
                  sourceReview={sourceReview}
                  candidate={outlineCandidate}
                  revisionBusy={outlineRevisionBusy}
                  sectionsBusy={outlineSectionsBusy}
                  onSave={saveRow}
                  onCreateRevision={createOutlineRevision}
                  onAcceptRevision={acceptOutlineRevision}
                  onRejectRevision={rejectOutlineRevision}
                  onRegenerateSections={regenerateOutlineBody}
                  onExport={handleExportOutline}
                />
              )}
              {workspaceTab === "lessons" && (
                <LessonPage
                  task={selectedTask}
                  lessons={lessonPlans}
                  selectedLessonId={selectedLessonId}
                  onSelect={setSelectedLessonId}
                  onPatch={patchLesson}
                  onGenerationComplete={() => void reloadLessonsAfterGeneration()}
                  onNotice={setNotice}
                  onError={setError}
                  onSave={saveLesson}
                  onExport={handleExportLessons}
                />
              )}
              {workspaceTab === "sessions" && (
                selectedOutlineRowId ? (
                  <SessionWorkspacePage
                    task={selectedTask}
                    outlineRowId={selectedOutlineRowId}
                    onBack={() => setSelectedOutlineRowId(null)}
                    onNotice={setNotice}
                    onError={setError}
                    onStatusChange={() => {
                      listOutlineRows(selectedTask.id).then(setOutlineRows).catch((reason: Error) => setError(reason.message));
                    }}
                  />
                ) : (
                  <CourseSessionsPage
                    rows={outlineRows}
                    onOpenSession={setSelectedOutlineRowId}
                  />
                )
              )}
              {workspaceTab === "exports" && (
                <ExportHistoryPanel
                  taskId={selectedTask.id}
                  reloadToken={exportToken}
                  onError={setError}
                />
              )}
            </CourseWorkspaceHeader>
          )}
          {view === "new-task" && (
            <NewTaskPage
              draft={taskDraft}
              onChange={setTaskDraft}
              onSubmit={handleCreateTask}
            />
          )}
          {view === "account" && <AccountPage />}
          {view === "admin" && currentUser.role === "admin" && <AdminPage currentUser={currentUser} />}
        </div>
      </main>
    </div>
  );
}

function LoginPage({
  error,
  loading,
  onLogin
}: {
  error: string;
  loading: boolean;
  onLogin: (employeeNo: string, password: string) => void;
}) {
  const [employeeNo, setEmployeeNo] = useState("");
  const [password, setPassword] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onLogin(employeeNo, password);
  }

  return (
    <main className="auth-shell">
      <form className="auth-card" onSubmit={submit}>
        <div className="brand auth-brand">
          <div className="brand-mark"><BookOpenCheck /></div>
          <div>
            <h1>智能备课文档生成系统</h1>
            <p>系部教师内部使用</p>
          </div>
        </div>
        <label>工号<input autoComplete="username" value={employeeNo} onChange={(event) => setEmployeeNo(event.target.value)} /></label>
        <label>密码<input autoComplete="current-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
        {error && <div className="error" role="alert">{error}</div>}
        <button className="btn primary" type="submit" disabled={loading}>{loading ? "登录中" : "登录"}</button>
        <p className="auth-hint">账号由系部管理员创建，初始密码默认为工号，首次登录后需要改成自己的密码。</p>
      </form>
    </main>
  );
}

function FirstLoginPasswordPage({
  currentUser,
  onChanged,
  onLogout
}: {
  currentUser: CurrentUser;
  onChanged: () => Promise<void>;
  onLogout: () => void;
}) {
  return (
    <main className="auth-shell">
      <div className="auth-card first-login-card">
        <div className="brand auth-brand">
          <div className="brand-mark"><BookOpenCheck /></div>
          <div>
            <h1>首次登录，请先设置自己的密码</h1>
            <p>{currentUser.name} · {currentUser.employee_no}</p>
          </div>
        </div>
        <p className="auth-hint">现在用的是管理员分配的初始密码。你的课程资料和教案只有你自己能看到，所以请先改成一个只有你知道的密码：至少 8 位，且不能与工号相同。</p>
        <PasswordForm currentLabel="初始密码" submitLabel="设置密码并进入系统" onChanged={onChanged} />
        <button className="btn" type="button" onClick={onLogout}>退出登录</button>
      </div>
    </main>
  );
}

function TeacherProfileForm({
  submitLabel = "保存个人信息",
  onSaved
}: {
  submitLabel?: string;
  onSaved?: () => Promise<void>;
}) {
  const [profile, setProfile] = useState<TeacherProfile | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [formError, setFormError] = useState("");

  useEffect(() => {
    getTeacherProfile()
      .then(setProfile)
      .catch((reason: unknown) => setFormError(reason instanceof Error ? reason.message : "个人信息加载失败"));
  }, []);

  const canSubmit =
    profile !== null &&
    profile.office_location.trim().length > 0 &&
    profile.phone.trim().length > 0 &&
    profile.bio.trim().length > 0 &&
    !saving;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!profile) return;
    setMessage("");
    setFormError("");
    setSaving(true);
    try {
      const saved = await updateTeacherProfile({
        office_location: profile.office_location,
        phone: profile.phone,
        bio: profile.bio
      });
      setProfile(saved);
      setMessage("个人信息已保存，课程实施大纲导出时会自动写入「教师信息」");
      await onSaved?.();
    } catch (reason) {
      setFormError(reason instanceof Error ? reason.message : "个人信息保存失败");
    } finally {
      setSaving(false);
    }
  }

  if (!profile) {
    return formError ? <div className="error" role="alert">{formError}</div> : <div role="status">正在加载个人信息...</div>;
  }

  return (
    <form className="password-form profile-form" onSubmit={submit}>
      <label>教师姓名<input value={profile.name} readOnly aria-describedby="profile-name-note" /></label>
      <div className="plain-note" id="profile-name-note">姓名来自管理员导入的教师名单，需要更正请联系管理员。</div>
      <label>办公地点<input value={profile.office_location} placeholder="例如：信息楼 316" onChange={(event) => setProfile({ ...profile, office_location: event.target.value })} /></label>
      <label>联系电话<input value={profile.phone} inputMode="tel" placeholder="手机号或办公电话" onChange={(event) => setProfile({ ...profile, phone: event.target.value })} /></label>
      <label>教师简介<textarea className="large-textarea" value={profile.bio} placeholder="学历、职称、研究方向、教学与科研经历等，按大纲「教师简介」一栏的写法" onChange={(event) => setProfile({ ...profile, bio: event.target.value })} /></label>
      {message && <div className="notice" role="status">{message}</div>}
      {formError && <div className="error" role="alert">{formError}</div>}
      <div className="form-actions">
        <button className="btn primary" type="submit" disabled={!canSubmit}>{saving ? "保存中" : submitLabel}</button>
      </div>
    </form>
  );
}

function FirstLoginProfilePage({
  currentUser,
  onSaved,
  onLogout
}: {
  currentUser: CurrentUser;
  onSaved: () => Promise<void>;
  onLogout: () => void;
}) {
  return (
    <main className="auth-shell">
      <div className="auth-card first-login-card">
        <div className="brand auth-brand">
          <div className="brand-mark"><BookOpenCheck /></div>
          <div>
            <h1>请先填写个人信息</h1>
            <p>{currentUser.name} · {currentUser.employee_no}</p>
          </div>
        </div>
        <p className="auth-hint">每门课的课程实施大纲都有一节「教师信息」：教师姓名、办公地点、联系电话、教师简介。填写一次，之后每门课导出大纲时自动写入，以后可在「个人信息与密码」里修改。</p>
        <TeacherProfileForm submitLabel="保存并进入系统" onSaved={onSaved} />
        <button className="btn" type="button" onClick={onLogout}>退出登录</button>
      </div>
    </main>
  );
}

function Sidebar({
  view,
  currentCourse,
  currentUser,
  onChange
}: {
  view: View;
  currentCourse: TeachingTask;
  currentUser: CurrentUser;
  onChange: (view: View) => void;
}) {
  const entries = [
    { id: "dashboard" as const, label: "教师工作台", icon: LayoutDashboard },
    { id: "courses" as const, label: "我的课程", icon: BookOpenCheck },
    { id: "new-task" as const, label: "新建学期课程", icon: FilePlus2 }
  ];
  const activeEntry = view === "course" ? "courses" : view;

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark"><BookOpenCheck /></div>
        <div>
          <h1>智能备课文档生成系统</h1>
          <p>高职艺术设计类课程</p>
        </div>
      </div>
      <nav className="nav" aria-label="主导航">
        {entries.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            className={activeEntry === id ? "active" : ""}
            aria-current={activeEntry === id ? "page" : undefined}
            onClick={() => onChange(id)}
          >
            <Icon className="icon" aria-hidden="true" />
            <span>{label}</span>
          </button>
        ))}
        {currentUser.role === "admin" && (
          <>
            <div className="role-divider">管理员入口</div>
            <button
              className={view === "admin" ? "active" : ""}
              aria-current={view === "admin" ? "page" : undefined}
              onClick={() => onChange("admin")}
            >
              <Settings2 className="icon" aria-hidden="true" />
              <span>标准库与账号管理</span>
            </button>
          </>
        )}
      </nav>
      {view === "course" && (
        <div className="sidebar-footer">
          <div>当前课程</div>
          <strong>{currentCourse.course_name}</strong>
          <div>{currentCourse.major} / {currentCourse.total_hours} 学时 / {Math.ceil(currentCourse.total_hours / currentCourse.hours_per_session)} 次课</div>
        </div>
      )}
    </aside>
  );
}

function Topbar({
  view,
  currentUser,
  onChange,
  onLogout
}: {
  view: View;
  currentUser: CurrentUser;
  onChange: (view: View) => void;
  onLogout: () => void;
}) {
  const meta = pageMeta[view];
  return (
    <header className="topbar">
      <div className="topbar-title">
        <h2>{meta.title}</h2>
        <p>{meta.subtitle}</p>
      </div>
      <div className="topbar-actions">
        {view === "dashboard" && (
          <button className="btn primary" aria-label="从工作台新建学期课程" onClick={() => onChange("new-task")}>
            <Plus className="icon" />新建学期课程
          </button>
        )}
        <span className="user-chip">{currentUser.name} · {currentUser.employee_no}</span>
        <button className="btn" onClick={() => onChange("account")}>个人信息与密码</button>
        <button className="btn" onClick={onLogout}>退出</button>
      </div>
    </header>
  );
}

function isToday(value?: string): boolean {
  return Boolean(value) && value === new Date().toISOString().slice(0, 10);
}

function preparationLabel(task: TeachingTask): string {
  if (!task.course_standard_uploaded || !task.schedule_uploaded) return "课程资料待补充";
  if (!task.outline_rows_count) return "课程实施大纲待生成";
  if (!task.lesson_plans_count) return "整门课教案待生成";
  return "继续本次课备课";
}

function Dashboard({
  tasks,
  loading,
  onCreate,
  onOpenCourse
}: {
  tasks: TeachingTask[];
  loading: boolean;
  onCreate: () => void;
  onOpenCourse: (taskId: number, tab?: WorkspaceTab) => void;
}) {
  const focusTask = tasks.find((task) => isToday(task.next_session_date))
    ?? tasks.find((task) => task.next_session_no != null)
    ?? tasks[0];

  if (loading) return <section className="view active"><p className="muted">正在加载课程...</p></section>;
  if (!focusTask) {
    return (
      <section className="view active empty-state">
        <BookOpenCheck />
        <strong>还没有学期课程</strong>
        <p>新建课程后，下一次课和待处理事项会显示在这里。</p>
        <button className="btn primary" onClick={onCreate}><Plus className="icon" />新建学期课程</button>
      </section>
    );
  }

  const preferredTab: WorkspaceTab = focusTask.course_standard_uploaded
    && focusTask.schedule_uploaded
    && Boolean(focusTask.outline_rows_count)
    ? "sessions"
    : "overview";
  const today = isToday(focusTask.next_session_date);

  return (
    <section className="view active dashboard-focus">
      <Panel title={today ? "今天的课程" : "下一次课"} sub={focusTask.next_session_date || "排课日期待确认"}>
        <div className="focus-course-row">
          <div>
            <span className="tag">{focusTask.term}</span>
            <h3>{focusTask.course_name}</h3>
            <p>{focusTask.class_name} · 第 {focusTask.next_session_no ?? 1} 次课 · {focusTask.next_session_weekday} 第 {focusTask.next_session_periods} 节</p>
          </div>
          <button className="btn primary" onClick={() => onOpenCourse(focusTask.id, preferredTab)}>
            {today ? "进入本次课" : "继续准备"}
          </button>
        </div>
      </Panel>
      <Panel title="待处理事项" sub={`${tasks.length} 门课程`}>
        <div className="task-list">
          {tasks.map((task) => (
            <button className="task-row" key={task.id} onClick={() => onOpenCourse(task.id)}>
              <div>
                <div className="task-title">{task.course_name}</div>
                <div className="task-meta">{task.term} · {task.class_name}</div>
                <div className="task-progress">
                  <span>大纲 {task.outline_rows_count ?? 0} 行</span>
                  <span>教案 {task.lesson_plans_count ?? 0} 份</span>
                  {(task.outline_template_uploaded || task.lesson_template_uploaded) && <span>模板已保存</span>}
                </div>
              </div>
              <span className="tag">{preparationLabel(task)}</span>
              <span className="task-action">进入课程</span>
            </button>
          ))}
        </div>
      </Panel>
    </section>
  );
}

function CoursesPage({
  tasks,
  onOpen,
  onCreate
}: {
  tasks: TeachingTask[];
  onOpen: (taskId: number) => void;
  onCreate: () => void;
}) {
  const [query, setQuery] = useState("");
  const normalizedQuery = query.trim().toLocaleLowerCase("zh-CN");
  const filteredTasks = normalizedQuery
    ? tasks.filter((task) => [task.course_name, task.class_name, task.major, task.term]
      .some((value) => value.toLocaleLowerCase("zh-CN").includes(normalizedQuery)))
    : tasks;

  return (
    <section className="view active">
      <div className="page-section-head">
        <div>
          <p>按学期管理课程实施大纲、整门课教案和每次课材料。</p>
        </div>
        <button className="btn primary" onClick={onCreate}>
          <Plus className="icon" />新建学期课程
        </button>
      </div>
      <div className="course-toolbar">
        <label className="course-search">
          <Search aria-hidden="true" />
          <span className="sr-only">搜索课程</span>
          <input
            type="search"
            aria-label="搜索课程"
            placeholder="搜索课程名称、班级、专业或学期"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <span className="course-count" aria-live="polite">
          {normalizedQuery ? `找到 ${filteredTasks.length} 门课程` : `共 ${tasks.length} 门课程`}
        </span>
      </div>
      {filteredTasks.length > 0 ? (
        <div className="course-grid">
          {filteredTasks.map((task) => (
          <article className="course-card" key={task.id}>
            <div className="course-card-head">
              <span className="tag">{task.term}</span>
              <span className="muted">{task.class_name}</span>
            </div>
            <h3>{task.course_name}</h3>
            <p>{task.major} · {task.total_hours} 学时</p>
            <div className="course-progress-text">
              已完成 {task.completed_sessions_count ?? 0}/{task.session_count ?? 0} 次课
            </div>
            <button className="btn" onClick={() => onOpen(task.id)}>进入课程</button>
          </article>
          ))}
        </div>
      ) : (
        <div className="course-empty">
          <BookOpenCheck aria-hidden="true" />
          <strong>没有找到匹配的课程</strong>
          <p>请尝试课程名称、班级、专业或学期中的其他关键词。</p>
          <button className="btn" onClick={() => setQuery("")}>清除搜索</button>
        </div>
      )}
    </section>
  );
}

const workspaceTabs: Array<{ id: WorkspaceTab; label: string }> = [
  { id: "overview", label: "课程概览" },
  { id: "materials", label: "课程资料" },
  { id: "outline", label: "课程实施大纲" },
  { id: "lessons", label: "整门课教案" },
  { id: "sessions", label: "课次与材料" },
  { id: "exports", label: "导出记录" }
];

function CourseWorkspaceHeader({
  task,
  tab,
  onTabChange,
  children
}: {
  task: TeachingTask;
  tab: WorkspaceTab;
  onTabChange: (tab: WorkspaceTab) => void;
  children: ReactNode;
}) {
  return (
    <section className="workspace-shell">
      <div className="workspace-course-head">
        <div>
          <span className="tag">{task.term}</span>
          <h3>{task.course_name}</h3>
          <p>{task.class_name} · {task.major} · {task.total_hours} 学时</p>
        </div>
      </div>
      <div className="workspace-tabs" role="tablist" aria-label="课程工作台">
        {workspaceTabs.map((item) => (
          <button
            key={item.id}
            role="tab"
            aria-selected={tab === item.id}
            className={tab === item.id ? "active" : ""}
            onClick={() => onTabChange(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div className="workspace-content">{children}</div>
    </section>
  );
}

type CourseSettingsDraft = Pick<TeachingTaskCreate, "course_name" | "class_name" | "major" | "location" | "total_hours" | "hours_per_session">;

function settingsDraftOf(task: TeachingTask): CourseSettingsDraft {
  return {
    course_name: task.course_name,
    class_name: task.class_name,
    major: task.major,
    location: task.location,
    total_hours: task.total_hours,
    hours_per_session: task.hours_per_session
  };
}

function CourseOverview({
  task,
  onOpenTab,
  onUpdate,
  onDelete,
  onError
}: {
  task: TeachingTask;
  onOpenTab: (tab: WorkspaceTab) => void;
  onUpdate: (payload: Partial<TeachingTaskCreate>) => Promise<void>;
  onDelete: () => Promise<void>;
  onError: (message: string) => void;
}) {
  const expectedSessions = Math.ceil(task.total_hours / task.hours_per_session);
  const [draft, setDraft] = useState<CourseSettingsDraft>(() => settingsDraftOf(task));
  const [saving, setSaving] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const changed = Object.fromEntries(
    (Object.keys(draft) as Array<keyof CourseSettingsDraft>)
      .filter((key) => draft[key] !== task[key])
      .map((key) => [key, draft[key]])
  ) as Partial<TeachingTaskCreate>;
  const hasChanges = Object.keys(changed).length > 0;

  async function saveSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!hasChanges) return;
    setSaving(true);
    try {
      await onUpdate(changed);
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "课程信息保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function confirmDelete() {
    setDeleting(true);
    try {
      await onDelete();
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "课程删除失败");
      setDeleting(false);
    }
  }

  return (
    <div className="dashboard-focus">
      <Panel title="课程准备进度" sub={`${task.completed_sessions_count ?? 0}/${task.session_count ?? expectedSessions} 次课已完成`}>
        <div className="check-list">
          <CheckItem title="课程资料">{task.course_standard_uploaded && task.schedule_uploaded ? "课程标准和课表已上传" : "课程资料待补充"}</CheckItem>
          <CheckItem title="课程实施大纲">{task.outline_rows_count ? `已生成 ${task.outline_rows_count} 行` : "待生成"}</CheckItem>
          <CheckItem title="整门课教案">{task.lesson_plans_count ? `已生成 ${task.lesson_plans_count} 份` : "待生成"}</CheckItem>
        </div>
      </Panel>
      <Panel title="继续准备" sub={task.next_session_date || "暂无后续排课"}>
        <div className="course-quick-actions">
          <button className="btn" onClick={() => onOpenTab("outline")}>课程实施大纲</button>
          <button className="btn" onClick={() => onOpenTab("lessons")}>整门课教案</button>
          <button className="btn primary" onClick={() => onOpenTab("sessions")}>进入下一次课</button>
        </div>
      </Panel>
      <Panel title="课程信息" sub="修改后只影响课程档案，已生成的大纲和教案不会改写">
        <form className="course-settings-form" onSubmit={saveSettings} aria-label="课程信息">
          <div className="form-grid">
            <TextField label="课程名称" value={draft.course_name} onChange={(course_name) => setDraft({ ...draft, course_name })} />
            <TextField label="班级" value={draft.class_name} onChange={(class_name) => setDraft({ ...draft, class_name })} />
            <TextField label="专业" value={draft.major} onChange={(major) => setDraft({ ...draft, major })} />
            <TextField label="上课地点" value={draft.location} onChange={(location) => setDraft({ ...draft, location })} />
            <NumberField label="课程总学时" value={draft.total_hours} onChange={(total_hours) => setDraft({ ...draft, total_hours })} />
            <NumberField label="每次课学时" value={draft.hours_per_session} onChange={(hours_per_session) => setDraft({ ...draft, hours_per_session })} />
          </div>
          <div className="form-actions">
            <button className="btn primary" type="submit" disabled={!hasChanges || saving}>
              <Save className="icon" />{saving ? "保存中" : "保存课程信息"}
            </button>
          </div>
        </form>
      </Panel>
      <Panel title="删除课程" sub="连同课程资料、大纲、教案和导出记录一起删除" className="course-danger">
        {confirmingDelete ? (
          <div className="course-danger-confirm" role="alertdialog" aria-label="确认删除课程">
            <p>
              将删除「{task.course_name}」及其课程标准、人才培养方案、课表、课程实施大纲、教案、作业试卷和导出记录，
              删除后无法恢复。已导出到本地的 Word 文件不受影响。
            </p>
            <div className="course-danger-actions">
              <button className="btn danger" disabled={deleting} onClick={() => void confirmDelete()}>{deleting ? "删除中" : "确认删除"}</button>
              <button className="btn" disabled={deleting} onClick={() => setConfirmingDelete(false)}>取消</button>
            </div>
          </div>
        ) : (
          <div className="course-danger-actions">
            <button className="btn danger" onClick={() => setConfirmingDelete(true)}>删除课程</button>
          </div>
        )}
      </Panel>
    </div>
  );
}

function CourseSessionsPage({
  rows,
  onOpenSession
}: {
  rows: OutlineRow[];
  onOpenSession: (outlineRowId: number) => void;
}) {
  return (
    <div className="course-sessions-layout">
      <Panel title="全部课次" sub={`${rows.length} 次课`}>
        {rows.length === 0 && <p className="muted">请先生成课程实施大纲。</p>}
        <div className="lesson-list">
          {rows.map((row) => {
            return (
              <article className="session-row" key={row.id}>
                <div>
                  <strong>第 {row.session_no} 次课 · {row.topic}</strong>
                  <p>{row.date_text} · {row.weekday} · 第 {row.periods} 节</p>
                </div>
                <div className="status-line">
                  {row.post_class_recorded && <span className="tag">已记录</span>}
                  {row.has_previous_adjustment && <span className="tag success">含上次课调整</span>}
                  <button className="btn primary" onClick={() => onOpenSession(row.id)}>进入本次课</button>
                </div>
              </article>
            );
          })}
        </div>
      </Panel>
    </div>
  );
}

function NewTaskPage({
  draft,
  onChange,
  onSubmit
}: {
  draft: TeachingTaskCreate;
  onChange: (draft: TeachingTaskCreate) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  const estimatedSessions = Math.ceil(draft.total_hours / Math.max(draft.hours_per_session, 1));

  return (
    <section className="view active">
      <div className="page-section-head">
        <div>
          <h3>课程基本信息</h3>
          <p>先建立本学期课程，保存后再集中上传课程标准、课表和 Word 模板。</p>
        </div>
      </div>
      <div className="new-course-layout">
        <Panel title="填写课程信息" sub="先完成必需信息">
          <form className="new-course-form" onSubmit={onSubmit}>
            <fieldset className="form-section">
              <legend>课程归属</legend>
              <p>用于区分学期、专业和授课班级。</p>
              <div className="form-grid">
                <TermField value={draft.term} onChange={(term) => onChange({ ...draft, term })} />
                <TextField label="专业" value={draft.major} onChange={(major) => onChange({ ...draft, major })} />
                <TextField label="课程名称" value={draft.course_name} onChange={(course_name) => onChange({ ...draft, course_name })} />
                <TextField label="班级" value={draft.class_name} onChange={(class_name) => onChange({ ...draft, class_name })} />
              </div>
            </fieldset>
            <fieldset className="form-section">
              <legend>授课安排</legend>
              <p>学时设置将用于拆分课程实施大纲和课次。</p>
              <div className="form-grid">
                <TextField label="任课教师" value={draft.teacher_name} onChange={(teacher_name) => onChange({ ...draft, teacher_name })} />
                <TextField label="上课地点" value={draft.location} onChange={(location) => onChange({ ...draft, location })} />
                <NumberField label="课程总学时" value={draft.total_hours} onChange={(total_hours) => onChange({ ...draft, total_hours })} />
                <NumberField label="每次课学时" value={draft.hours_per_session} onChange={(hours_per_session) => onChange({ ...draft, hours_per_session })} />
              </div>
            </fieldset>
            <div className="new-course-submit">
              <p><strong>预计形成 {estimatedSessions} 次课</strong><span>{draft.total_hours} 总学时 ÷ 每次 {draft.hours_per_session} 学时</span></p>
              <button className="btn primary" type="submit"><Save className="icon" />保存并继续准备资料</button>
            </div>
          </form>
        </Panel>
        <aside className="new-course-guide" aria-label="创建后流程">
          <span className="guide-label">创建后流程</span>
          <h3>课程建档后再准备资料</h3>
          <p>保存后会直接进入课程资料页，按顺序完成以下工作。</p>
          <ol>
            <li><strong>上传课程依据</strong><span>课程标准、人才培养方案与课表</span></li>
            <li><strong>确认 Word 模板</strong><span>保留学校已有文档格式</span></li>
            <li><strong>生成并复核</strong><span>先大纲，再逐次完善教案</span></li>
          </ol>
        </aside>
      </div>
    </section>
  );
}

function OutlineEditor({
  task,
  rows,
  setRows,
  sourceReview,
  candidate,
  revisionBusy,
  sectionsBusy,
  onSave,
  onCreateRevision,
  onAcceptRevision,
  onRejectRevision,
  onRegenerateSections,
  onExport
}: {
  task: TeachingTask;
  rows: OutlineRow[];
  setRows: (rows: OutlineRow[]) => void;
  sourceReview: SourceReview | null;
  candidate: OutlineRevisionCandidate | null;
  revisionBusy: boolean;
  sectionsBusy: boolean;
  onSave: (row: OutlineRow) => Promise<boolean>;
  onCreateRevision: (rowId: number, fieldName: OutlineRevisionField) => void;
  onAcceptRevision: () => void;
  onRejectRevision: () => void;
  onRegenerateSections: () => void;
  onExport: () => void;
}) {
  const [revisionFields, setRevisionFields] = useState<Record<number, OutlineRevisionField>>({});
  const [dirtyRowIds, setDirtyRowIds] = useState<Set<number>>(() => new Set());
  const [selectedRowId, setSelectedRowId] = useState<number | null>(null);
  const selectedRow = rows.find((row) => row.id === selectedRowId) ?? rows[0];

  function patchRow(rowId: number, patch: Partial<OutlineRow>) {
    setSelectedRowId(rowId);
    setDirtyRowIds((current) => new Set(current).add(rowId));
    setRows(rows.map((row) => (row.id === rowId ? { ...row, ...patch } : row)));
  }

  async function saveChangedRow(row: OutlineRow) {
    if (!await onSave(row)) return;
    setDirtyRowIds((current) => {
      const next = new Set(current);
      next.delete(row.id);
      return next;
    });
  }

  function toggleCode(row: OutlineRow, field: "course_goal_codes" | "ability_codes", code: string) {
    const selected = parseCodeList(row[field]);
    const next = selected.includes(code) ? selected.filter((item) => item !== code) : [...selected, code];
    patchRow(row.id, { [field]: next.join(", ") });
  }

  return (
    <section className="view active">
      <div className="page-section-head">
        <div>
          <h3>课程实施大纲</h3>
          <p>确认日期、课次、教学内容、课程目标和能力指标。</p>
        </div>
        <div className="status-line">
          {/* The body is written on the first export and kept, so a teacher who
              wants different prose has to be able to ask for it. */}
          <button
            className="btn"
            disabled={sectionsBusy || rows.length === 0}
            onClick={onRegenerateSections}
            title="重写课程简介、预期学习成果、学习方法和学习要求；学习进程表、学习资源和考核方式不变"
          >
            <RefreshCw className="icon" />{sectionsBusy ? "正在重写正文..." : "重写大纲正文"}
          </button>
          {/* Exporting before generation only earns a refusal from the API;
              greying the button says the same thing without a round trip. */}
          <button
            className="btn primary"
            disabled={rows.length === 0 || dirtyRowIds.size > 0}
            title={rows.length === 0 ? "请先生成课程实施大纲" : undefined}
            onClick={onExport}
          >
            <Download className="icon" />导出课程实施大纲
          </button>
        </div>
      </div>
      <div className="layout-aside-main outline-layout">
        <Panel title="生成依据" sub="自动读取">
          <div className="goal-list">
            <GoalItem title="课程标准" description="读取课程目标、项目模块、参考课时和考核方式。" tags={["M1-M4"]} />
            <GoalItem title="课表" description={`识别 ${rows.length || Math.ceil(task.total_hours / task.hours_per_session)} 次课，每次连续 ${task.hours_per_session} 节。`} tags={["Excel", `1-${task.hours_per_session} 节`]} />
            <GoalItem title="Word 模板" description="按上传模板填充内容，导出后可继续在 WPS/Office 修改。" tags={["保持格式"]} />
            <GoalItem title="能力指标" description="关联人才培养方案并自动校验代码。" tags={["自动校验"]} />
          </div>
        </Panel>

        <Panel
          title="课程实施大纲 · 先确认这张表"
          action={<div className="status-line"><span className={`tag ${dirtyRowIds.size ? "amber" : "green"}`}>{dirtyRowIds.size ? `${dirtyRowIds.size} 项未保存` : "全部修改已保存"}</span><span className="tag">{rows.length || 0} 次课</span></div>}
          className="outline-main-panel"
        >
          <div className="plain-note">
            这里主要调整上课日期、周次、节次和教学内容。课程目标、能力指标和其他细节也会一并写入 Word。
          </div>
          {rows.length === 0 ? (
            <div className="empty-state">
              <Table2 />
              <strong>暂未生成授课计划表</strong>
              <p>请先上传课程标准和课表，再生成课程实施大纲。</p>
            </div>
          ) : (
            <div className="table-wrap">
              <table aria-label="课程实施大纲编辑表">
                <colgroup>
                  <col className="outline-col-session" />
                  <col className="outline-col-date" />
                  <col className="outline-col-week" />
                  <col className="outline-col-periods" />
                  <col className="outline-col-topic" />
                  <col className="outline-col-content" />
                  <col className="outline-col-goals" />
                  <col className="outline-col-abilities" />
                  <col className="outline-col-actions" />
                </colgroup>
                <thead>
                  <tr>
                    <th>课次</th>
                    <th>日期</th>
                    <th>周次</th>
                    <th>节次</th>
                    <th>教学主题</th>
                    <th>教学内容</th>
                    <th>课程目标</th>
                    <th>能力指标</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => {
                    const selectedGoals = parseCodeList(row.course_goal_codes);
                    const selectedAbilities = parseCodeList(row.ability_codes);
                    const abilityOptions = (sourceReview?.goals ?? [])
                      .filter((goal) => selectedGoals.includes(goal.code))
                      .flatMap((goal) => goal.indicators)
                      .filter((indicator, index, all) => all.findIndex((item) => item.code === indicator.code) === index);
                    const validAbilityCodes = new Set(abilityOptions.map((indicator) => indicator.code));
                    const invalidAbilityCodes = selectedAbilities.filter((code) => !validAbilityCodes.has(code));
                    const revisionField = revisionFields[row.id] ?? "teaching_content";
                    const rowCandidate = candidate?.outline_row_id === row.id ? candidate : null;

                    return (
                      <Fragment key={row.id}>
                        <tr
                          className={`${dirtyRowIds.has(row.id) ? "outline-row-dirty" : ""} ${selectedRow?.id === row.id ? "outline-row-selected" : ""}`.trim()}
                          onFocus={() => setSelectedRowId(row.id)}
                        >
                          <td>第 {row.session_no} 次</td>
                          <td><input aria-label="日期" value={row.date_text} onChange={(event) => patchRow(row.id, { date_text: event.target.value })} /></td>
                          <td><input aria-label="周次" type="number" value={row.week_no} onChange={(event) => patchRow(row.id, { week_no: Number(event.target.value) })} /></td>
                          <td><input aria-label="节次" value={row.periods} onChange={(event) => patchRow(row.id, { periods: event.target.value })} /></td>
                          <td><input aria-label="主题" value={row.topic} onChange={(event) => patchRow(row.id, { topic: event.target.value })} /></td>
                          <td><textarea aria-label="教学内容" value={row.teaching_content} onChange={(event) => patchRow(row.id, { teaching_content: event.target.value })} /></td>
                          <td>
                            <CodePicker
                              label={`第 ${row.session_no} 次课课程目标`}
                              options={(sourceReview?.goals ?? []).map((goal) => ({ code: goal.code, description: goal.description }))}
                              selected={selectedGoals}
                              onToggle={(code) => toggleCode(row, "course_goal_codes", code)}
                            />
                          </td>
                          <td>
                            <CodePicker
                              label={`第 ${row.session_no} 次课能力指标`}
                              options={abilityOptions.map((indicator) => ({ code: indicator.code, description: indicator.description }))}
                              selected={selectedAbilities}
                              onToggle={(code) => toggleCode(row, "ability_codes", code)}
                            />
                            {invalidAbilityCodes.length > 0 && <small className="code-error">请重新选择：{invalidAbilityCodes.join("、")}</small>}
                          </td>
                          <td>
                            <div className="outline-row-actions">
                              <button
                                className={`btn ${dirtyRowIds.has(row.id) ? "primary" : ""}`}
                                disabled={invalidAbilityCodes.length > 0 || !dirtyRowIds.has(row.id)}
                                onClick={() => void saveChangedRow(row)}
                              >
                                {dirtyRowIds.has(row.id) ? "保存修改" : "已保存"}
                              </button>
                              <select
                                aria-label={`优化字段（第 ${row.session_no} 次课）`}
                                value={revisionField}
                                onChange={(event) => setRevisionFields((current) => ({ ...current, [row.id]: event.target.value as OutlineRevisionField }))}
                              >
                                <option value="topic">教学主题</option>
                                <option value="teaching_content">教学内容</option>
                                <option value="teaching_methods">教学方法</option>
                                <option value="tasks">课前课中课后任务</option>
                                <option value="all">整行内容</option>
                              </select>
                              <button
                                className="btn"
                                disabled={revisionBusy || dirtyRowIds.has(row.id)}
                                aria-label={`AI 优化第 ${row.session_no} 次课`}
                                title={dirtyRowIds.has(row.id) ? "请先保存本行修改" : undefined}
                                onClick={() => onCreateRevision(row.id, revisionField)}
                              >
                                <Sparkles className="icon" />AI 优化
                              </button>
                            </div>
                          </td>
                        </tr>
                        {rowCandidate && (
                          <tr className="outline-revision-row">
                            <td colSpan={9}>
                              <div className="outline-revision-candidate" aria-label={`第 ${row.session_no} 次课 AI 优化建议`}>
                                <div>
                                  <span>原内容</span>
                                  <p>{rowCandidate.original_content || "（空）"}</p>
                                </div>
                                <div className="suggested">
                                  <span>AI 建议</span>
                                  <p>{rowCandidate.proposed_content}</p>
                                </div>
                                <div className="status-line">
                                  <button className="btn primary" disabled={revisionBusy} onClick={onAcceptRevision}>采用建议</button>
                                  <button className="btn" disabled={revisionBusy} onClick={onRejectRevision}>放弃建议</button>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

        <Panel title={selectedRow ? `第 ${selectedRow.session_no} 次课详情` : "当前课次详情"} sub="自动带入 Word" className="outline-detail-panel">
          <div className="check-list">
            <CheckItem title="课程目标">{selectedRow?.course_goal_codes || "等待生成后匹配 M 目标。"}</CheckItem>
            <CheckItem title="课程思政" tone="warn">{selectedRow?.ideological_point || "技术向善、职业规范，可在详情中调整。"}</CheckItem>
            <CheckItem title="能力指标">{selectedRow?.ability_codes || "等待关联人才培养方案。"}</CheckItem>
            <CheckItem title="导出提醒" tone="alert">导出 Word 后可以继续在 WPS/Office 中修改最终文字。</CheckItem>
          </div>
        </Panel>
      </div>
    </section>
  );
}

function parseCodeList(value: string): string[] {
  return value.split(/[\s,，、]+/).map((code) => code.trim()).filter(Boolean);
}

function CodePicker({
  label,
  options,
  selected,
  onToggle
}: {
  label: string;
  options: { code: string; description: string }[];
  selected: string[];
  onToggle: (code: string) => void;
}) {
  return (
    <div className="code-picker" aria-label={label}>
      {options.length === 0 ? (
        <small>暂无可选代码</small>
      ) : options.map((option) => (
        <label key={option.code} title={option.description}>
          <input
            type="checkbox"
            checked={selected.includes(option.code)}
            onChange={() => onToggle(option.code)}
          />
          <span>{option.code}</span>
        </label>
      ))}
    </div>
  );
}

function LessonPage({
  task,
  lessons,
  selectedLessonId,
  onSelect,
  onPatch,
  onGenerationComplete,
  onNotice,
  onError,
  onSave,
  onExport
}: {
  task: TeachingTask;
  lessons: LessonPlan[];
  selectedLessonId: number | null;
  onSelect: (lessonId: number) => void;
  onPatch: (lessonId: number, patch: Partial<LessonPlan>) => void;
  onGenerationComplete: () => void;
  onNotice: (message: string) => void;
  onError: (message: string) => void;
  onSave: (lesson: LessonPlan) => Promise<boolean>;
  onExport: () => void;
}) {
  const selectedLesson = lessons.find((lesson) => lesson.id === selectedLessonId) ?? lessons[0] ?? null;
  const [dirtyLessonIds, setDirtyLessonIds] = useState<Set<number>>(() => new Set());

  function patchLessonDraft(lessonId: number, patch: Partial<LessonPlan>) {
    setDirtyLessonIds((current) => new Set(current).add(lessonId));
    onPatch(lessonId, patch);
  }

  async function saveLessonDraft(lesson: LessonPlan) {
    if (!await onSave(lesson)) return;
    setDirtyLessonIds((current) => {
      const next = new Set(current);
      next.delete(lesson.id);
      return next;
    });
  }

  if (!selectedLesson) {
    return (
      <section className="view active">
        <div className="page-section-head">
          <div>
            <h3>整门课教案</h3>
            <p>一次生成全部课次，按课次检查后统一导出。</p>
          </div>
        </div>
        <div className="layout-main-aside">
          <Panel title="教案生成" sub="从定稿课程实施大纲生成">
            <div className="empty-state">
              <NotebookTabs />
              <strong>还没有生成教案</strong>
              <p>请先确认课程实施大纲，再按课次生成可编辑的教案初稿。</p>
              <LessonGenerationProgress taskId={task.id} onCompleted={onGenerationComplete} onNotice={onNotice} onError={onError} />
            </div>
          </Panel>
          <Panel title="生成依据" sub="当前任务">
            <div className="check-list">
              <CheckItem title="课程">{task.course_name}</CheckItem>
              <CheckItem title="授课班级">{task.class_name}</CheckItem>
              <CheckItem title="课时规则">每次课 {task.hours_per_session} 节，共 {task.total_hours} 学时。</CheckItem>
              <CheckItem title="导出方式" tone="warn">导出时使用教师上传的教案 Word 模板，保留模板格式并填充内容。</CheckItem>
            </div>
          </Panel>
        </div>
      </section>
    );
  }

  return (
    <section className="view active">
      <div className="page-section-head">
        <div>
          <h3>整门课教案</h3>
          <p>一次生成全部课次，按课次检查后统一导出。</p>
        </div>
        <div className="status-line">
          <LessonGenerationProgress taskId={task.id} compact onCompleted={onGenerationComplete} onNotice={onNotice} onError={onError} />
          <span className={`tag ${dirtyLessonIds.size ? "amber" : "green"}`}>{dirtyLessonIds.size ? `${dirtyLessonIds.size} 份教案未保存` : "全部教案已保存"}</span>
          <button
            className="btn primary"
            disabled={lessons.length === 0 || dirtyLessonIds.size > 0}
            title={lessons.length === 0 ? "请先生成整门课教案" : undefined}
            onClick={onExport}
          >
            <Download className="icon" />导出整门课教案
          </button>
        </div>
      </div>
      <div className="layout-aside-main lesson-layout">
        <Panel title="课次" sub={`${lessons.length} 次课`}>
          <div className="lesson-list">
            {lessons.map((lesson) => (
              <button
                className={`lesson-item ${lesson.id === selectedLesson.id ? "active" : ""} ${dirtyLessonIds.has(lesson.id) ? "dirty" : ""}`.trim()}
                key={lesson.id}
                onClick={() => onSelect(lesson.id)}
              >
                <strong>第 {lesson.session_no} 次课</strong><p>{lesson.title}</p>
              </button>
            ))}
          </div>
        </Panel>
        <Panel title="教案预览" action={<div className="status-line"><span className="tag green">单次课</span><span className="tag">可编辑</span></div>} className="lesson-preview-panel">
          <div className="plain-note">网页里主要确认结构、目标和课次内容。导出 Word 后仍可在 WPS 或 Office 中继续润色和排版。</div>
          <div className="doc-section">
            <h4>一、教学基本情况</h4>
            <div className="form-grid">
              <label>课程名称<input value={task.course_name} readOnly /></label>
              <label>本次课标题<input aria-label="本次课标题" value={selectedLesson.title} onChange={(event) => patchLessonDraft(selectedLesson.id, { title: event.target.value })} /></label>
              <label>授课班级<input value={task.class_name} readOnly /></label>
              <label>授课时长<input aria-label="授课时长" type="number" value={selectedLesson.duration_minutes} onChange={(event) => patchLessonDraft(selectedLesson.id, { duration_minutes: Number(event.target.value) })} /></label>
            </div>
          </div>
          <div className="doc-section">
            <h4>本次课教学目标</h4>
            <div className="lesson-editor-grid">
              <label>教学目标<textarea aria-label="教学目标" value={selectedLesson.teaching_goals} onChange={(event) => patchLessonDraft(selectedLesson.id, { teaching_goals: event.target.value })} /><LessonRevisionControl taskId={task.id} lessonId={selectedLesson.id} fieldName="teaching_goals" onAccepted={(content) => patchLessonDraft(selectedLesson.id, { teaching_goals: content })} onError={onError} /></label>
              <label>课程目标代码<input aria-label="课程目标代码" value={selectedLesson.course_goal_codes} readOnly /></label>
              <label>能力指标代码<input aria-label="能力指标代码" value={selectedLesson.ability_codes} readOnly /></label>
            </div>
          </div>
          <div className="doc-section">
            <h4>二、重点难点</h4>
            <div className="lesson-editor-grid two-col">
              <label>教学重点<textarea aria-label="教学重点" value={selectedLesson.key_points} onChange={(event) => patchLessonDraft(selectedLesson.id, { key_points: event.target.value })} /><LessonRevisionControl taskId={task.id} lessonId={selectedLesson.id} fieldName="key_points" onAccepted={(content) => patchLessonDraft(selectedLesson.id, { key_points: content })} onError={onError} /></label>
              <label>教学难点<textarea aria-label="教学难点" value={selectedLesson.difficult_points} onChange={(event) => patchLessonDraft(selectedLesson.id, { difficult_points: event.target.value })} /><LessonRevisionControl taskId={task.id} lessonId={selectedLesson.id} fieldName="difficult_points" onAccepted={(content) => patchLessonDraft(selectedLesson.id, { difficult_points: content })} onError={onError} /></label>
            </div>
          </div>
          <div className="doc-section">
            <h4>三、教学实施过程</h4>
            <label>教学准备<textarea aria-label="教学准备" value={selectedLesson.teaching_preparation} onChange={(event) => patchLessonDraft(selectedLesson.id, { teaching_preparation: event.target.value })} /><LessonRevisionControl taskId={task.id} lessonId={selectedLesson.id} fieldName="teaching_preparation" onAccepted={(content) => patchLessonDraft(selectedLesson.id, { teaching_preparation: content })} onError={onError} /></label>
            <label>教学过程<textarea className="large-textarea" aria-label="教学过程" value={selectedLesson.teaching_process} onChange={(event) => patchLessonDraft(selectedLesson.id, { teaching_process: event.target.value })} /><LessonRevisionControl taskId={task.id} lessonId={selectedLesson.id} fieldName="teaching_process" onAccepted={(content) => patchLessonDraft(selectedLesson.id, { teaching_process: content })} onError={onError} /></label>
            <label>课堂小结<textarea aria-label="课堂小结" value={selectedLesson.summary} onChange={(event) => patchLessonDraft(selectedLesson.id, { summary: event.target.value })} /><LessonRevisionControl taskId={task.id} lessonId={selectedLesson.id} fieldName="summary" onAccepted={(content) => patchLessonDraft(selectedLesson.id, { summary: content })} onError={onError} /></label>
          </div>
          <div className="doc-section">
            <h4>四、课后任务与反思</h4>
            <div className="lesson-editor-grid two-col">
              <label>课后任务<textarea aria-label="课后任务" value={selectedLesson.homework} onChange={(event) => patchLessonDraft(selectedLesson.id, { homework: event.target.value })} /><LessonRevisionControl taskId={task.id} lessonId={selectedLesson.id} fieldName="homework" onAccepted={(content) => patchLessonDraft(selectedLesson.id, { homework: content })} onError={onError} /></label>
              <label>教学反思<textarea aria-label="教学反思" value={selectedLesson.reflection} onChange={(event) => patchLessonDraft(selectedLesson.id, { reflection: event.target.value })} /></label>
            </div>
          </div>
          <div className="form-actions lesson-actions">
            <button className="btn primary" disabled={!dirtyLessonIds.has(selectedLesson.id)} onClick={() => void saveLessonDraft(selectedLesson)}><Save className="icon" />{dirtyLessonIds.has(selectedLesson.id) ? "保存教案修改" : "教案已保存"}</button>
          </div>
        </Panel>
        <Panel title="指标校验" sub="K → M → 代码" className="lesson-detail-panel">
          <div className="check-list">
            <CheckItem title="课程目标">{selectedLesson.course_goal_codes || "尚未填写课程目标代码。"}</CheckItem>
            <CheckItem title="能力指标">{selectedLesson.ability_codes || "尚未填写能力指标代码。"}</CheckItem>
            <CheckItem title="时长合计" tone="warn">当前课次 {selectedLesson.duration_minutes} 分钟，艺术设计类课程通常为 4 节连上。</CheckItem>
            <CheckItem title="保存提醒" tone="alert">网页修改后请先保存，再导出教案 Word。</CheckItem>
          </div>
        </Panel>
      </div>
    </section>
  );
}

function PasswordForm({
  currentLabel = "当前密码",
  submitLabel = "保存新密码",
  onChanged
}: {
  currentLabel?: string;
  submitLabel?: string;
  onChanged?: () => Promise<void>;
}) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const meetsLength = newPassword.length >= 8;
  const hasConfirmation = confirmPassword.length > 0;
  const passwordsMatch = hasConfirmation && newPassword === confirmPassword;
  const canSubmit = currentPassword.length > 0 && meetsLength && passwordsMatch && !saving;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("");
    setPasswordError("");
    if (newPassword !== confirmPassword) {
      setPasswordError("两次输入的新密码不一致");
      return;
    }
    if (newPassword.length < 8) {
      setPasswordError("新密码至少需要 8 位");
      return;
    }

    setSaving(true);
    try {
      await changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setMessage("密码已修改");
      await onChanged?.();
    } catch (reason) {
      setPasswordError(reason instanceof Error ? reason.message : "密码修改失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="password-form" onSubmit={submit}>
      <label>{currentLabel}<input autoComplete="current-password" type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} /></label>
      <label>新密码<input aria-describedby="password-requirements" autoComplete="new-password" type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} /></label>
      <label>确认新密码<input aria-describedby="password-requirements" autoComplete="new-password" type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} /></label>
      <div className="password-requirements" id="password-requirements" aria-live="polite">
        <span className={meetsLength ? "met" : ""}>{meetsLength ? "已达到 8 位" : "至少 8 位"}</span>
        <span className={passwordsMatch ? "met" : hasConfirmation ? "unmet" : ""}>{passwordsMatch ? "两次输入一致" : hasConfirmation ? "两次输入不一致" : "请再次输入新密码"}</span>
      </div>
      {message && <div className="notice">{message}</div>}
      {passwordError && <div className="error">{passwordError}</div>}
      <div className="form-actions">
        <button className="btn primary" type="submit" disabled={!canSubmit}>{saving ? "保存中" : submitLabel}</button>
      </div>
    </form>
  );
}

function AccountPage() {
  return (
    <section className="view active account-layout">
      <Panel title="个人信息" sub="课程实施大纲「教师信息」一节按这里的内容填写">
        <TeacherProfileForm />
      </Panel>
      <Panel title="修改密码" sub="用于当前登录账号">
        <PasswordForm />
      </Panel>
      <Panel title="使用提醒" sub="账号安全">
        <div className="check-list">
          <CheckItem title="修改后立即生效">保存后旧密码会失效，下次登录请使用新密码。</CheckItem>
          <CheckItem title="忘记密码">教师忘记密码时，可联系管理员在账号管理中重置。</CheckItem>
        </div>
      </Panel>
    </section>
  );
}

function AdminPage({ currentUser }: { currentUser: CurrentUser }) {
  const [section, setSection] = useState<"accounts" | "libraries" | "ai">("accounts");
  const [composer, setComposer] = useState<"major" | "user" | "batch" | null>(null);
  const [majors, setMajors] = useState<Major[]>([]);
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [majorDraft, setMajorDraft] = useState({ name: "", short_name: "", is_active: true });
  const [resetDrafts, setResetDrafts] = useState<Record<number, string>>({});
  const [userDraft, setUserDraft] = useState({
    employee_no: "",
    name: "",
    password: "",
    role: "teacher" as const,
    major_ids: [] as number[],
    is_active: true
  });
  const [batchText, setBatchText] = useState("");
  const [batchMajorIds, setBatchMajorIds] = useState<number[]>([]);
  const [batchBusy, setBatchBusy] = useState(false);
  const [editingUserId, setEditingUserId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState({ name: "", major_ids: [] as number[] });
  const [adminNotice, setAdminNotice] = useState("");
  const [adminError, setAdminError] = useState("");
  const roster = useMemo(() => parseTeacherRoster(batchText), [batchText]);
  const pendingInitialPassword = users.filter((user) => user.must_change_password && user.is_active).length;

  useEffect(() => {
    Promise.all([listAdminMajors(), listAdminUsers()])
      .then(([majorItems, userItems]) => {
        setMajors(majorItems);
        setUsers(userItems);
      })
      .catch((reason: Error) => setAdminError(reason.message));
  }, []);

  function majorNames(ids: number[]): string {
    const names = ids.map((id) => majors.find((major) => major.id === id)?.short_name || majors.find((major) => major.id === id)?.name).filter(Boolean);
    return names.length ? names.join("、") : "未绑定专业";
  }

  function toggleId(ids: number[], id: number): number[] {
    return ids.includes(id) ? ids.filter((item) => item !== id) : [...ids, id];
  }

  async function submitMajor(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAdminError("");
    try {
      const created = await createMajor(majorDraft);
      setMajors((current) => [...current, created]);
      setMajorDraft({ name: "", short_name: "", is_active: true });
      setComposer(null);
      setAdminNotice("专业已新增");
    } catch (reason) {
      setAdminError(reason instanceof Error ? reason.message : "专业创建失败");
    }
  }

  async function submitUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAdminError("");
    try {
      const created = await createUser(userDraft);
      setUsers((current) => [...current, created]);
      setUserDraft({ employee_no: "", name: "", password: "", role: "teacher", major_ids: [], is_active: true });
      setComposer(null);
      setAdminNotice(
        userDraft.password.trim()
          ? `已新增 ${created.name} 的账号，首次登录需修改密码`
          : `已新增 ${created.name} 的账号，初始密码为工号 ${created.employee_no}，首次登录需修改`
      );
    } catch (reason) {
      setAdminError(reason instanceof Error ? reason.message : "教师账号创建失败");
    }
  }

  async function submitBatch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAdminError("");
    setAdminNotice("");
    setBatchBusy(true);
    try {
      const result = await createUsersBatch(roster.items, batchMajorIds);
      setUsers((current) => [...current, ...result.created]);
      setBatchText("");
      setComposer(null);
      const skippedNote = result.skipped.length
        ? `；${result.skipped.length} 个工号已有账号，未重复创建：${result.skipped.join("、")}`
        : "";
      setAdminNotice(`已新增 ${result.created.length} 位教师，初始密码均为本人工号，首次登录需修改${skippedNote}`);
    } catch (reason) {
      setAdminError(reason instanceof Error ? reason.message : "批量导入失败");
    } finally {
      setBatchBusy(false);
    }
  }

  function startEdit(user: ManagedUser) {
    if (editingUserId === user.id) {
      setEditingUserId(null);
      return;
    }
    setEditingUserId(user.id);
    setEditDraft({ name: user.name, major_ids: user.major_ids });
  }

  async function submitEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (editingUserId === null) return;
    setAdminError("");
    try {
      const updated = await updateUser(editingUserId, editDraft);
      setUsers((current) => current.map((user) => (user.id === updated.id ? updated : user)));
      setEditingUserId(null);
      setAdminNotice(`${updated.name} 的账号信息已保存`);
    } catch (reason) {
      setAdminError(reason instanceof Error ? reason.message : "账号信息保存失败");
    }
  }

  async function toggleActive(user: ManagedUser) {
    setAdminError("");
    try {
      const updated = await updateUser(user.id, { is_active: !user.is_active });
      setUsers((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setAdminNotice(updated.is_active ? `${updated.name} 的账号已启用` : `${updated.name} 的账号已停用，课程资料保留，重新启用即可继续使用`);
    } catch (reason) {
      setAdminError(reason instanceof Error ? reason.message : "账号状态修改失败");
    }
  }

  async function resetPassword(user: ManagedUser) {
    setAdminNotice("");
    setAdminError("");
    const password = resetDrafts[user.id]?.trim() ?? "";
    if (password && password.length < 8) {
      setAdminError("新密码至少需要 8 位，留空则重置为工号");
      return;
    }
    try {
      await resetUserPassword(user.id, password);
      setResetDrafts((current) => ({ ...current, [user.id]: "" }));
      setUsers((current) => current.map((item) => (item.id === user.id ? { ...item, must_change_password: true } : item)));
      setAdminNotice(password ? "密码已重置" : `${user.name} 的密码已重置为工号 ${user.employee_no}，下次登录需重新设置`);
    } catch (reason) {
      setAdminError(reason instanceof Error ? reason.message : "密码重置失败");
    }
  }

  return (
    <section className="view active admin-page">
      <div className="admin-intro">
        <div>
          <h3>标准库与账号管理</h3>
          <p>按管理任务分区维护，避免账号、教学标准和生成服务相互干扰。</p>
        </div>
        <div className="admin-summary" aria-label="管理数据概况">
          <span>{users.length} 个账号</span>
          <span>{majors.length} 个专业</span>
          <span>{pendingInitialPassword} 人尚未修改初始密码</span>
        </div>
      </div>

      <div className="admin-tabs" role="tablist" aria-label="管理内容">
        <button role="tab" aria-selected={section === "accounts"} className={section === "accounts" ? "active" : ""} onClick={() => setSection("accounts")}><BookOpenCheck className="icon" />账号与专业</button>
        <button role="tab" aria-selected={section === "libraries"} className={section === "libraries" ? "active" : ""} onClick={() => setSection("libraries")}><NotebookTabs className="icon" />标准与模板</button>
        <button role="tab" aria-selected={section === "ai"} className={section === "ai" ? "active" : ""} onClick={() => setSection("ai")}><Settings2 className="icon" />AI 生成配置</button>
      </div>

      {section === "accounts" && (
        <div className="admin-account-section" role="tabpanel">
          {adminNotice && <div className="notice" role="status">{adminNotice}</div>}
          {adminError && <div className="error" role="alert">{adminError}</div>}
          <div className="admin-account-grid">
            <Panel title="专业管理" action={<button className="btn" type="button" aria-expanded={composer === "major"} onClick={() => setComposer(composer === "major" ? null : "major")}><Plus className="icon" />新增专业</button>}>
              {composer === "major" && (
                <form className="admin-composer inline-form" onSubmit={submitMajor}>
                  <label>专业名称<input required value={majorDraft.name} onChange={(event) => setMajorDraft({ ...majorDraft, name: event.target.value })} /></label>
                  <label>简称<input value={majorDraft.short_name} onChange={(event) => setMajorDraft({ ...majorDraft, short_name: event.target.value })} /></label>
                  <button className="btn primary" type="submit">保存专业</button>
                </form>
              )}
              <p className="section-description">维护课程归属的教学专业，专业简称将用于紧凑列表。</p>
              <div className="library-list admin-list">
                {majors.map((major) => (
                  <div className="library-item" key={major.id}>
                    <div><strong>{major.name}</strong><p>{major.short_name || "未设置简称"}</p></div>
                    <span className={`tag ${major.is_active ? "green" : "rose"}`}>{major.is_active ? "启用" : "停用"}</span>
                  </div>
                ))}
              </div>
            </Panel>

            <Panel
              title="教师账号"
              action={(
                <div className="panel-action-group">
                  <button className="btn" type="button" aria-expanded={composer === "batch"} onClick={() => setComposer(composer === "batch" ? null : "batch")}><Upload className="icon" />批量导入</button>
                  <button className="btn primary" type="button" aria-expanded={composer === "user"} onClick={() => setComposer(composer === "user" ? null : "user")}><Plus className="icon" />新增教师</button>
                </div>
              )}
            >
              {composer === "batch" && (
                <form className="admin-composer batch-form" onSubmit={submitBatch}>
                  <label>教师名单
                    <textarea
                      value={batchText}
                      onChange={(event) => setBatchText(event.target.value)}
                      rows={8}
                      placeholder={"每行一位教师：工号 姓名\n可直接从 Excel 复制「工号」「姓名」两列粘贴，例如：\n2019001\t张明\n2019002\t李华"}
                    />
                  </label>
                  <div className="field-block">
                    <span>统一绑定的授课专业（可选，之后可逐人调整）</span>
                    <div className="checkbox-grid">
                      {majors.map((major) => (
                        <label key={major.id}><input type="checkbox" checked={batchMajorIds.includes(major.id)} onChange={() => setBatchMajorIds((current) => toggleId(current, major.id))} />{major.name}</label>
                      ))}
                    </div>
                    <small>初始密码为各自的工号，老师首次登录时系统会要求改成自己的密码。已有账号的工号会跳过，不会重置任何人的密码。</small>
                  </div>
                  <div className="batch-preview" aria-live="polite">
                    {roster.items.length > 0 && <span>识别到 {roster.items.length} 位教师</span>}
                    {roster.invalid.length > 0 && <span className="unmet">有 {roster.invalid.length} 行无法识别，请补成「工号 姓名」：{roster.invalid.slice(0, 3).join("；")}{roster.invalid.length > 3 ? " …" : ""}</span>}
                  </div>
                  <div className="form-actions">
                    <button className="btn primary" type="submit" disabled={batchBusy || roster.items.length === 0 || roster.invalid.length > 0}>
                      {batchBusy ? "导入中" : `导入 ${roster.items.length} 位教师`}
                    </button>
                  </div>
                </form>
              )}
              {composer === "user" && (
                <form className="admin-composer form-grid" onSubmit={submitUser}>
                  <label>工号<input required value={userDraft.employee_no} onChange={(event) => setUserDraft({ ...userDraft, employee_no: event.target.value })} /></label>
                  <label>姓名<input required value={userDraft.name} onChange={(event) => setUserDraft({ ...userDraft, name: event.target.value })} /></label>
                  <label>初始密码<input value={userDraft.password} placeholder="留空则以工号作为初始密码" onChange={(event) => setUserDraft({ ...userDraft, password: event.target.value })} /></label>
                  <div className="field-block">
                    <span>可授课专业</span>
                    <div className="checkbox-grid">
                      {majors.map((major) => (
                        <label key={major.id}><input type="checkbox" checked={userDraft.major_ids.includes(major.id)} onChange={() => setUserDraft((current) => ({ ...current, major_ids: toggleId(current.major_ids, major.id) }))} />{major.name}</label>
                      ))}
                    </div>
                  </div>
                  <div className="form-actions"><button className="btn primary" type="submit">保存教师账号</button></div>
                </form>
              )}
              <p className="section-description">教师用工号登录。新账号的初始密码为工号，首次登录必须改成自己的密码；停用账号后本人无法登录，课程资料保留，重新启用即可继续。</p>
              <div className="library-list admin-list user-admin-list">
                {users.map((user) => (
                  <div className="library-item" key={user.id}>
                    <div className="admin-user-main">
                      <div><strong>{user.name} · {user.employee_no}</strong><p>{user.role === "admin" ? "管理员" : "教师"} / {majorNames(user.major_ids)}</p></div>
                      <div className="tag-row">
                        {user.must_change_password && user.is_active && <span className="tag amber">初始密码未修改</span>}
                        <span className={`tag ${user.is_active ? "green" : "rose"}`}>{user.is_active ? "启用" : "停用"}</span>
                      </div>
                    </div>
                    <div className="admin-user-actions">
                      <button className="btn" type="button" aria-expanded={editingUserId === user.id} onClick={() => startEdit(user)}>{editingUserId === user.id ? "收起" : `编辑 ${user.name}`}</button>
                      {user.id !== currentUser.id && (
                        <button className="btn" type="button" onClick={() => toggleActive(user)}>{user.is_active ? `停用 ${user.name}` : `启用 ${user.name}`}</button>
                      )}
                    </div>
                    {editingUserId === user.id && (
                      <form className="admin-composer form-grid" onSubmit={submitEdit}>
                        <label>姓名<input required value={editDraft.name} onChange={(event) => setEditDraft({ ...editDraft, name: event.target.value })} /></label>
                        <div className="field-block">
                          <span>可授课专业</span>
                          <div className="checkbox-grid">
                            {majors.map((major) => (
                              <label key={major.id}><input type="checkbox" checked={editDraft.major_ids.includes(major.id)} onChange={() => setEditDraft((current) => ({ ...current, major_ids: toggleId(current.major_ids, major.id) }))} />{major.name}</label>
                            ))}
                          </div>
                        </div>
                        <div className="form-actions"><button className="btn primary" type="submit">保存修改</button></div>
                      </form>
                    )}
                    <div className="reset-row">
                      <label>重置 {user.name} 密码
                        <input type="password" value={resetDrafts[user.id] ?? ""} onChange={(event) => setResetDrafts((current) => ({ ...current, [user.id]: event.target.value }))} placeholder="留空则重置为工号" />
                      </label>
                      <button className="btn" type="button" onClick={() => resetPassword(user)}>重置 {user.name} 密码</button>
                    </div>
                  </div>
                ))}
              </div>
            </Panel>
          </div>
        </div>
      )}

      {section === "libraries" && (
        <div className="admin-library-grid" role="tabpanel">
          <LibraryPanel title="人才培养方案库" items={[
            ["数字媒体艺术设计 · 2025 版", "已抽取知识能力素养集和课程对应关系。", "已入库"],
            ["视觉传达设计 · 2024 版", "等待确认课程与能力指标映射。", "待确认"]
          ]} />
          <LibraryPanel title="课程标准库" items={[
            ["人工智能与创意设计", "M1-M4 已绑定知识能力素养代码。", "可用"],
            ["UI 界面设计", "模板字段完整，课程目标待复核。", "待复核"]
          ]} />
          <LibraryPanel title="模板库" items={[
            ["课程实施大纲模板", "包含日期、周次、节次、教学内容和学习任务字段。", "推荐"],
            ["教案模板", "包含教学基本情况、K 目标、教学过程与反思。", "15 个占位符"]
          ]} />
        </div>
      )}

      {section === "ai" && <div className="admin-model-section" role="tabpanel"><AiModelConfigPanel /></div>}
    </section>
  );
}

function LibraryPanel({ title, items }: { title: string; items: string[][] }) {
  return (
    <Panel title={title} action={<button className="btn"><Upload className="icon" />上传</button>}>
      <div className="library-list">
        {items.map(([name, description, status]) => {
          const statusTone = status.startsWith("待")
            ? "amber"
            : ["已入库", "可用", "推荐"].includes(status) ? "green" : "";
          return (
            <div className="library-item" key={name}>
              <strong>{name}</strong>
              <p>{description}</p>
              <span className={`tag ${statusTone}`.trim()}>{status}</span>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

function Panel({
  title,
  sub,
  action,
  className = "",
  children
}: {
  title: string;
  sub?: string;
  action?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-head">
        <h3>{title}</h3>
        {action ?? (sub ? <span className="sub">{sub}</span> : null)}
      </div>
      <div className="panel-body">{children}</div>
    </section>
  );
}

function CheckItem({
  title,
  tone = "",
  children
}: {
  title: string;
  tone?: "warn" | "alert" | "";
  children: React.ReactNode;
}) {
  return (
    <div className={`check-item ${tone}`}>
      <strong>{title}</strong>
      <p>{children}</p>
    </div>
  );
}

function GoalItem({ title, description, tags }: { title: string; description: string; tags: string[] }) {
  return (
    <div className="goal-item">
      <strong>{title}</strong>
      <p>{description}</p>
      <div className="status-line">{tags.map((tag) => <span className="tag green" key={tag}>{tag}</span>)}</div>
    </div>
  );
}

function TextField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label>{label}<input value={value} onChange={(event) => onChange(event.target.value)} /></label>;
}

type TermHalf = "一" | "二";

const TERM_PATTERN = /^(\d{4})-(\d{4})\s*第([一二])学期$/;

/** 8 月起算新学年，跟学校的作息一致。 */
function currentAcademicYear(): number {
  const now = new Date();
  return now.getMonth() + 1 >= 8 ? now.getFullYear() : now.getFullYear() - 1;
}

function parseTerm(value: string): { startYear: number; half: TermHalf } {
  const match = TERM_PATTERN.exec(value.trim());
  if (match) return { startYear: Number(match[1]), half: match[3] as TermHalf };
  return { startYear: currentAcademicYear(), half: "一" };
}

function formatTerm(startYear: number, half: TermHalf): string {
  return `${startYear}-${startYear + 1} 第${half}学期`;
}

/**
 * 学期只给选、不给填。
 *
 * 它是要拿来分组和排序的，而手输一定会飘：线上已经有 `2025-2026第二学期` 和
 * `2025-2026 第二学期` 两条记录指同一个学期，回流到工作台之后就是两格。
 * 后端 `normalize_term()` 会兜住直接调 API 的路径，这里则让老师根本写不出
 * 第二种形式。
 *
 * 认不出来的旧值（老师从别处粘来的写法）不会被静默改写——`parseTerm` 落到当前
 * 学年，但只有老师真的动了下拉才会写回去。
 */
function TermField({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const { startYear, half } = parseTerm(value);
  const base = currentAcademicYear();
  const years = [base - 1, base, base + 1];
  if (!years.includes(startYear)) years.unshift(startYear);
  return (
    <label>学期
      <span className="term-field">
        <select
          value={startYear}
          onChange={(event) => onChange(formatTerm(Number(event.target.value), half))}
        >
          {years.map((year) => <option key={year} value={year}>{year}-{year + 1}</option>)}
        </select>
        <select
          aria-label="第几学期"
          value={half}
          onChange={(event) => onChange(formatTerm(startYear, event.target.value as TermHalf))}
        >
          <option value="一">第一学期</option>
          <option value="二">第二学期</option>
        </select>
      </span>
    </label>
  );
}

function NumberField({ label, value, onChange }: { label: string; value: number; onChange: (value: number) => void }) {
  return <label>{label}<input type="number" min={1} value={value} onChange={(event) => onChange(Number(event.target.value))} /></label>;
}
