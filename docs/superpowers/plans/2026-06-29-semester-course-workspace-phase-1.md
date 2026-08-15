# 学期课程工作台第一阶段实施计划

> **优先级说明（2026-06-30）：** 本计划暂缓执行。先完成 `docs/superpowers/specs/2026-06-30-trusted-source-validation-design.md` 中的可信资料校验闭环，再继续本工作台计划。已完成的课程进度计算保留。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有一次性备课任务界面调整为以“工作台、我的课程、课程工作台”为主线的学期课程产品骨架，同时完整保留课程实施大纲、整门课教案、作业试卷原型和 Word 导出能力。

**Architecture:** 继续将现有 `TeachingTask` 作为第一阶段的“学期课程”，避免数据库迁移；后端通过纯函数从排课记录计算课程进度摘要并扩展任务读取接口。前端保留现有生成和导出状态，将顶层导航收敛为教师工作台、我的课程和新建学期课程，并在课程工作台内部通过四个页签承载现有功能。

**Tech Stack:** FastAPI、SQLModel、pytest、React 19、TypeScript、Vite、Vitest、Testing Library、Lucide React、现有 CSS。

---

## 文件结构

本阶段不拆解现有 `App.tsx` 中的编辑器组件，先完成低风险的信息架构迁移。新增文件只承担可独立测试的课程进度计算职责。

- Create: `apps/api/app/services/course_progress.py`：根据排课记录计算课次数、已完成课次和下一次课。
- Create: `apps/api/tests/test_course_progress.py`：课程进度纯函数测试。
- Modify: `apps/api/app/schemas.py`：扩展学期课程读取字段。
- Modify: `apps/api/app/routes/tasks.py`：在任务列表和创建结果中返回课程进度摘要。
- Modify: `apps/api/tests/test_outline_workflow_api.py`：验证课程进度字段出现在 API 中。
- Modify: `apps/web/src/types.ts`：扩展 `TeachingTask` 类型。
- Modify: `apps/web/src/App.test.tsx`：为新导航、教师首页、我的课程和课程工作台补充回归测试。
- Modify: `apps/web/src/App.tsx`：调整顶层导航、课程工作台和现有功能入口。
- Modify: `apps/web/src/styles.css`：增加课程卡片、课程工作台页签和响应式布局。
- Modify: `README.md`：更新当前产品入口和第一阶段范围。

## Task 1：课程进度摘要服务

**Files:**
- Create: `apps/api/app/services/course_progress.py`
- Create: `apps/api/tests/test_course_progress.py`

- [ ] **Step 1：编写课程进度失败测试**

创建 `apps/api/tests/test_course_progress.py`：

```python
from datetime import date
from types import SimpleNamespace

from app.services.course_progress import summarize_course_sessions


def session(no: int, date_text: str):
    return SimpleNamespace(
        session_no=no,
        date_text=date_text,
        weekday="周一",
        periods="1-4",
    )


def test_summarize_course_sessions_finds_today_and_next_session():
    result = summarize_course_sessions(
        [
            session(1, "2026-06-22"),
            session(2, "2026-06-29"),
            session(3, "2026-07-06"),
        ],
        today=date(2026, 6, 29),
    )

    assert result.session_count == 3
    assert result.completed_sessions_count == 1
    assert result.next_session_no == 2
    assert result.next_session_date == "2026-06-29"
    assert result.next_session_weekday == "周一"
    assert result.next_session_periods == "1-4"


def test_summarize_course_sessions_returns_no_next_session_after_course_end():
    result = summarize_course_sessions(
        [session(1, "2026-06-01"), session(2, "2026-06-08")],
        today=date(2026, 6, 29),
    )

    assert result.session_count == 2
    assert result.completed_sessions_count == 2
    assert result.next_session_no is None
    assert result.next_session_date == ""


def test_summarize_course_sessions_ignores_invalid_dates_for_next_session():
    result = summarize_course_sessions(
        [session(1, "第一周"), session(2, "2026-07-06")],
        today=date(2026, 6, 29),
    )

    assert result.session_count == 2
    assert result.completed_sessions_count == 0
    assert result.next_session_no == 2
```

- [ ] **Step 2：运行测试确认失败**

Run:

```powershell
cd apps/api
pytest tests/test_course_progress.py -q
```

Expected: FAIL，提示 `app.services.course_progress` 不存在。

- [ ] **Step 3：实现最小课程进度服务**

创建 `apps/api/app/services/course_progress.py`：

```python
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Protocol


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
    sessions: Iterable[ScheduledSession],
    today: date | None = None,
) -> CourseProgress:
    current_date = today or date.today()
    session_list = list(sessions)
    dated_sessions = [
        (item, parsed_date)
        for item in session_list
        if (parsed_date := _parse_date(item.date_text)) is not None
    ]
    dated_sessions.sort(key=lambda pair: (pair[1], pair[0].session_no))
    completed_count = sum(1 for _, session_date in dated_sessions if session_date < current_date)
    next_item = next(
        (item for item, session_date in dated_sessions if session_date >= current_date),
        None,
    )

    return CourseProgress(
        session_count=len(session_list),
        completed_sessions_count=completed_count,
        next_session_no=next_item.session_no if next_item else None,
        next_session_date=next_item.date_text if next_item else "",
        next_session_weekday=next_item.weekday if next_item else "",
        next_session_periods=next_item.periods if next_item else "",
    )
```

- [ ] **Step 4：运行课程进度测试确认通过**

Run: `pytest tests/test_course_progress.py -q`

Expected: `3 passed`。

- [ ] **Step 5：提交课程进度服务**

```powershell
git add apps/api/app/services/course_progress.py apps/api/tests/test_course_progress.py
git commit -m "feat: summarize semester course progress"
```

## Task 2：在课程 API 返回进度摘要

**Files:**
- Modify: `apps/api/app/schemas.py:67-78`
- Modify: `apps/api/app/routes/tasks.py:16-26,378-406`
- Modify: `apps/api/tests/test_outline_workflow_api.py`

- [ ] **Step 1：扩展 API 失败测试**

在 `test_task_list_returns_material_and_generation_progress` 中增加：

```python
    assert task["session_count"] == 2
    assert task["completed_sessions_count"] >= 0
    assert "next_session_no" in task
    assert "next_session_date" in task
    assert "next_session_weekday" in task
    assert "next_session_periods" in task
```

- [ ] **Step 2：运行测试确认字段缺失**

Run:

```powershell
pytest tests/test_outline_workflow_api.py::test_task_list_returns_material_and_generation_progress -q
```

Expected: FAIL，提示缺少 `session_count`。

- [ ] **Step 3：扩展读取模型**

在 `TeachingTaskRead` 中加入：

```python
    session_count: int = 0
    completed_sessions_count: int = 0
    next_session_no: int | None = None
    next_session_date: str = ""
    next_session_weekday: str = ""
    next_session_periods: str = ""
```

- [ ] **Step 4：在 `_task_read` 计算进度**

在 `tasks.py` 导入：

```python
from app.services.course_progress import summarize_course_sessions
```

在 `_task_read` 中一次查询排课记录：

```python
    schedule_records = session.exec(
        select(ScheduleSessionRecord)
        .where(ScheduleSessionRecord.task_id == task_id)
        .order_by(ScheduleSessionRecord.session_no)
    ).all()
    progress = summarize_course_sessions(schedule_records)
```

将原来的 `schedule_count` 改为 `len(schedule_records)`，并在返回字典中加入：

```python
        "session_count": progress.session_count,
        "completed_sessions_count": progress.completed_sessions_count,
        "next_session_no": progress.next_session_no,
        "next_session_date": progress.next_session_date,
        "next_session_weekday": progress.next_session_weekday,
        "next_session_periods": progress.next_session_periods,
```

- [ ] **Step 5：运行 API 测试与全量后端测试**

Run:

```powershell
pytest tests/test_outline_workflow_api.py::test_task_list_returns_material_and_generation_progress -q
pytest -q
```

Expected: 目标测试 PASS，全量后端测试无失败。

- [ ] **Step 6：提交 API 进度摘要**

```powershell
git add apps/api/app/schemas.py apps/api/app/routes/tasks.py apps/api/tests/test_outline_workflow_api.py
git commit -m "feat: expose course schedule progress"
```

## Task 3：调整顶层导航并建立“我的课程”

**Files:**
- Modify: `apps/web/src/types.ts:7-24`
- Modify: `apps/web/src/App.test.tsx`
- Modify: `apps/web/src/App.tsx:54-104,532-584,665-731`

- [ ] **Step 1：扩展前端课程类型和测试数据**

在 `TeachingTask` 增加：

```typescript
  session_count?: number;
  completed_sessions_count?: number;
  next_session_no?: number | null;
  next_session_date?: string;
  next_session_weekday?: string;
  next_session_periods?: string;
```

在 `App.test.tsx` 的课程数据加入：

```typescript
    session_count: 8,
    completed_sessions_count: 2,
    next_session_no: 3,
    next_session_date: new Date().toISOString().slice(0, 10),
    next_session_weekday: "周一",
    next_session_periods: "1-4"
```

- [ ] **Step 2：编写新顶层导航失败测试**

增加：

```typescript
  it("uses semester courses as the primary teacher navigation", async () => {
    render(<App />);

    expect(await screen.findByRole("button", { name: "教师工作台" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "我的课程" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "新建学期课程" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "教案生成" })).not.toBeInTheDocument();
  });

  it("lists the current teacher's semester courses", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "我的课程" }));

    expect(screen.getByRole("heading", { name: "我的课程" })).toBeInTheDocument();
    expect(screen.getByText("人工智能与创意设计")).toBeInTheDocument();
    expect(screen.getByText(/已完成 2\/8 次课/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "进入课程" })).toBeInTheDocument();
  });
```

- [ ] **Step 3：运行测试确认旧导航不符合要求**

Run:

```powershell
npm test -- --run src/App.test.tsx -t "semester courses|current teacher"
```

Expected: FAIL，找不到“我的课程”或仍存在“教案生成”顶层按钮。

- [ ] **Step 4：收敛顶层 View 和侧栏入口**

将顶层类型改为：

```typescript
type View = "dashboard" | "courses" | "new-task" | "course" | "admin" | "account";
type WorkspaceTab = "overview" | "outline" | "lessons" | "sessions";
```

同步将 `pageMeta` 收敛为 `dashboard`、`courses`、`new-task`、`course`、`admin`、`account` 六项，其中新增：

```typescript
courses: {
  title: "我的课程",
  subtitle: "按学期管理课程实施大纲、整门课教案和每次课材料"
},
course: {
  title: "课程工作台",
  subtitle: "从学期规划到每次课备课，所有内容都保留在当前课程中"
}
```

侧栏教师入口改为：

```typescript
const entries = [
  { id: "dashboard" as const, label: "教师工作台", icon: LayoutDashboard },
  { id: "courses" as const, label: "我的课程", icon: BookOpenCheck },
  { id: "new-task" as const, label: "新建学期课程", icon: FilePlus2 }
];
```

保留管理员入口和修改密码入口。将 `new-task` 的页面标题改为“新建学期课程”。

- [ ] **Step 5：增加“我的课程”页面**

在 `App.tsx` 新增组件：

```tsx
function CoursesPage({
  tasks,
  onOpen,
  onCreate
}: {
  tasks: TeachingTask[];
  onOpen: (taskId: number) => void;
  onCreate: () => void;
}) {
  return (
    <section className="view active">
      <div className="page-section-head">
        <div>
          <h3>我的课程</h3>
          <p>按学期管理课程实施大纲、整门课教案和每次课材料。</p>
        </div>
        <button className="btn primary" onClick={onCreate}>
          <Plus className="icon" />新建学期课程
        </button>
      </div>
      <div className="course-grid">
        {tasks.map((task) => (
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
            <button className="btn primary" onClick={() => onOpen(task.id)}>进入课程</button>
          </article>
        ))}
      </div>
    </section>
  );
}
```

在主渲染区加入 `view === "courses"` 分支，并让“进入课程”选择课程后进入 `course`。

- [ ] **Step 6：运行导航和课程列表测试**

Run: `npm test -- --run src/App.test.tsx -t "semester courses|current teacher"`

Expected: 2 tests PASS。

- [ ] **Step 7：提交顶层导航和我的课程**

```powershell
git add apps/web/src/types.ts apps/web/src/App.test.tsx apps/web/src/App.tsx
git commit -m "feat: add semester course navigation"
```

## Task 4：教师首页和课程工作台四页签

**Files:**
- Modify: `apps/web/src/App.test.tsx`
- Modify: `apps/web/src/App.tsx:107-490,586-663,826-1070`

- [ ] **Step 1：编写教师首页失败测试**

```typescript
  it("shows today's course and pending preparation on the teacher dashboard", async () => {
    render(<App />);

    expect(await screen.findByRole("heading", { name: "今天的课程" })).toBeInTheDocument();
    expect(screen.getByText(/第 3 次课/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "进入本次课" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "待处理事项" })).toBeInTheDocument();
  });
```

- [ ] **Step 2：编写课程工作台失败测试**

```typescript
  it("opens a course workspace with four stable tabs", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "我的课程" }));
    await user.click(screen.getByRole("button", { name: "进入课程" }));

    expect(screen.getByRole("tab", { name: "课程概览" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "课程实施大纲" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "整门课教案" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "课次与材料" })).toBeInTheDocument();
  });
```

- [ ] **Step 3：运行测试确认失败**

Run:

```powershell
npm test -- --run src/App.test.tsx -t "today's course|course workspace"
```

Expected: FAIL，首页和课程页签尚不存在。

- [ ] **Step 4：将 Dashboard 改成持续备课首页**

Dashboard 使用 `next_session_date` 与浏览器当天日期比较，展示“今天的课程”或“下一次课”。无课程时展示明确空状态。待处理事项只基于现有可计算状态：

```typescript
function isToday(value?: string): boolean {
  return Boolean(value) && value === new Date().toISOString().slice(0, 10);
}

function preparationLabel(task: TeachingTask): string {
  if (!task.course_standard_uploaded || !task.schedule_uploaded) return "课程资料待补充";
  if (!task.outline_rows_count) return "课程实施大纲待生成";
  if (!task.lesson_plans_count) return "整门课教案待生成";
  return "继续本次课备课";
}
```

首页主操作统一调用课程打开函数，今天课程优先进入 `sessions`，资料未完成的课程进入 `overview`：

```tsx
const preferredTab: WorkspaceTab =
  task.course_standard_uploaded && task.schedule_uploaded && task.outline_rows_count
    ? "sessions"
    : "overview";

<button className="btn primary" onClick={() => onOpenCourse(task.id, preferredTab)}>
  {isToday(task.next_session_date) ? "进入本次课" : "继续准备"}
</button>
```

- [ ] **Step 5：建立课程工作台状态和页签**

在 `App` 增加：

```typescript
const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>("overview");

function openCourse(taskId: number, tab: WorkspaceTab = "overview") {
  setSelectedTaskId(taskId);
  setWorkspaceTab(tab);
  activate("course");
}
```

将现有只在 `view === "lesson"` 时读取教案的 effect 替换为两个课程页签 effect：

```typescript
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
      setSelectedLessonId((current) => current ?? lessons[0]?.id ?? null);
    })
    .catch((reason: Error) => {
      if (!isMounted || loadSeq !== lessonLoadSeq.current) return;
      setError(reason.message);
    });
  return () => {
    isMounted = false;
  };
}, [view, workspaceTab, selectedTask?.id]);
```

课程工作台页签使用标准 tab 语义：

```tsx
<div className="workspace-tabs" role="tablist" aria-label="课程工作台">
  {[
    ["overview", "课程概览"],
    ["outline", "课程实施大纲"],
    ["lessons", "整门课教案"],
    ["sessions", "课次与材料"]
  ].map(([id, label]) => (
    <button
      key={id}
      role="tab"
      aria-selected={workspaceTab === id}
      className={workspaceTab === id ? "active" : ""}
      onClick={() => setWorkspaceTab(id as WorkspaceTab)}
    >
      {label}
    </button>
  ))}
</div>
```

- [ ] **Step 6：迁移现有页面而不复制逻辑**

`course` 视图根据 `workspaceTab` 复用现有组件：

```tsx
{view === "course" && selectedTask && (
  <CourseWorkspaceHeader task={selectedTask} tab={workspaceTab} onTabChange={setWorkspaceTab}>
    {workspaceTab === "overview" && <CourseOverview task={selectedTask} onOpenTab={setWorkspaceTab} />}
    {workspaceTab === "outline" && (
      <OutlineEditor
        task={selectedTask}
        rows={outlineRows}
        setRows={setOutlineRows}
        onSave={saveRow}
        onGenerate={handleGenerateOutline}
        onExport={handleExportOutline}
      />
    )}
    {workspaceTab === "lessons" && (
      <LessonPage
        task={selectedTask}
        lessons={lessonPlans}
        selectedLessonId={selectedLessonId}
        generating={generating}
        onSelect={setSelectedLessonId}
        onPatch={patchLesson}
        onGenerate={handleGenerateLessons}
        onSave={saveLesson}
        onExport={handleExportLessons}
      />
    )}
    {workspaceTab === "sessions" && (
      <CourseSessionsPage
        rows={outlineRows}
        lessons={lessonPlans}
        onOpenLesson={(lessonId) => {
          setSelectedLessonId(lessonId);
          setWorkspaceTab("lessons");
        }}
      />
    )}
  </CourseWorkspaceHeader>
)}
```

在 `App.tsx` 中增加以下最小组件。`CourseWorkspaceHeader` 只负责课程标题与页签，不获取数据：

```tsx
const workspaceTabs: Array<{ id: WorkspaceTab; label: string }> = [
  { id: "overview", label: "课程概览" },
  { id: "outline", label: "课程实施大纲" },
  { id: "lessons", label: "整门课教案" },
  { id: "sessions", label: "课次与材料" }
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
  children: React.ReactNode;
}) {
  return (
    <section className="workspace-shell">
      <div className="page-section-head">
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
      {children}
    </section>
  );
}
```

`CourseOverview` 只显示当前已有进度并通过回调切换页签：

```tsx
function CourseOverview({
  task,
  onOpenTab
}: {
  task: TeachingTask;
  onOpenTab: (tab: WorkspaceTab) => void;
}) {
  const expectedSessions = Math.ceil(task.total_hours / task.hours_per_session);
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
    </div>
  );
}
```

`CourseSessionsPage` 将课次与已有教案关联，并在本阶段复用现有作业试卷原型：

```tsx
function CourseSessionsPage({
  rows,
  lessons,
  onOpenLesson
}: {
  rows: OutlineRow[];
  lessons: LessonPlan[];
  onOpenLesson: (lessonId: number) => void;
}) {
  const [assessmentRowId, setAssessmentRowId] = useState<number | null>(null);
  return (
    <div className="course-sessions-layout">
      <Panel title="全部课次" sub={`${rows.length} 次课`}>
        <div className="lesson-list">
          {rows.map((row) => {
            const lesson = lessons.find((item) => item.outline_row_id === row.id);
            return (
              <article className="session-row" key={row.id}>
                <div>
                  <strong>第 {row.session_no} 次课 · {row.topic}</strong>
                  <p>{row.date_text} · {row.weekday} · 第 {row.periods} 节</p>
                </div>
                <div className="status-line">
                  {lesson && <button className="btn" onClick={() => onOpenLesson(lesson.id)}>查看教案</button>}
                  <button className="btn" onClick={() => setAssessmentRowId(row.id)}>设计作业/测试</button>
                </div>
              </article>
            );
          })}
        </div>
      </Panel>
      {assessmentRowId !== null && <AssessmentPage />}
    </div>
  );
}
```

调用 `CourseOverview` 时传入 `onOpenTab={setWorkspaceTab}`。`CourseSessionsPage` 的作业试卷仍是现有原型，本阶段仅迁移入口，不新增学生提交、成绩或题库逻辑。

- [ ] **Step 7：调整 Topbar 操作**

顶栏在 `course` 视图只显示用户信息和通用操作。生成与导出按钮移动到对应页签内容头部：

- 课程实施大纲：生成/重新生成、导出实施大纲。
- 整门课教案：生成整门课教案、导出整门课教案。
- 课次与材料：当前课次操作。

现有 `handleGenerateOutline`、`handleExportOutline`、`handleGenerateLessons`、`handleExportLessons` 函数保持不变，只调整调用位置。

将 `Topbar` 收敛为页面标题、首页新建入口和账号操作：

```tsx
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
          <button className="btn primary" onClick={() => onChange("new-task")}>
            <Plus className="icon" />新建学期课程
          </button>
        )}
        <span className="user-chip">{currentUser.name} · {currentUser.employee_no}</span>
        <button className="btn" onClick={() => onChange("account")}>修改密码</button>
        <button className="btn" onClick={onLogout}>退出</button>
      </div>
    </header>
  );
}
```

对应删除 `App` 调用 `Topbar` 时的生成和导出 props。

为 `OutlineEditor` 增加 `onGenerate`、`onExport`，并在表格之前加入：

```tsx
<div className="page-section-head">
  <div>
    <h3>课程实施大纲</h3>
    <p>确认日期、课次、教学内容、课程目标和能力指标。</p>
  </div>
  <div className="status-line">
    <button className="btn" onClick={onGenerate}><RefreshCw className="icon" />重新生成</button>
    <button className="btn primary" onClick={onExport}><Download className="icon" />导出课程实施大纲</button>
  </div>
</div>
```

Props 类型同步增加：

```typescript
onGenerate: () => void;
onExport: () => void;
```

为 `LessonPage` 增加 `onExport`，在有教案和无教案两种分支中都提供明确操作。有教案时在布局之前加入：

```tsx
<div className="page-section-head">
  <div>
    <h3>整门课教案</h3>
    <p>一次生成全部课次，按课次检查后统一导出。</p>
  </div>
  <div className="status-line">
    <button className="btn" disabled={generating} onClick={onGenerate}>
      <RefreshCw className="icon" />重新生成整门课
    </button>
    <button className="btn primary" onClick={onExport}>
      <Download className="icon" />导出整门课教案
    </button>
  </div>
</div>
```

Props 类型同步增加：

```typescript
onExport: () => void;
```

- [ ] **Step 8：更新旧前端测试入口**

将原先直接点击“教案生成”“编辑大纲”的测试改为：

```typescript
await user.click(await screen.findByRole("button", { name: "我的课程" }));
await user.click(screen.getByRole("button", { name: "进入课程" }));
await user.click(screen.getByRole("tab", { name: "课程实施大纲" }));
```

教案测试使用“整门课教案”页签。所有原有生成 URL、保存 URL 和导出 URL 断言保持不变。

- [ ] **Step 9：运行完整前端测试**

Run: `npm test -- --run`

Expected: 所有测试 PASS，原有上传、生成、保存、账号和导出测试均保留。

- [ ] **Step 10：提交首页和课程工作台**

```powershell
git add apps/web/src/App.test.tsx apps/web/src/App.tsx
git commit -m "feat: add semester course workspace"
```

## Task 5：课程工作台视觉与响应式布局

**Files:**
- Modify: `apps/web/src/styles.css`
- Modify: `apps/web/src/App.test.tsx`

- [ ] **Step 1：增加结构稳定性测试**

```typescript
  it("keeps the course workspace controls available at narrow widths", async () => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 390 });
    window.dispatchEvent(new Event("resize"));
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "我的课程" }));
    await user.click(screen.getByRole("button", { name: "进入课程" }));

    expect(screen.getByRole("tablist", { name: "课程工作台" })).toBeInTheDocument();
    expect(screen.getAllByRole("tab")).toHaveLength(4);
  });
```

- [ ] **Step 2：增加课程布局样式**

在 `styles.css` 增加：

```css
.page-section-head {
  margin-bottom: 16px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.page-section-head h3, .page-section-head p { margin: 0; }
.page-section-head p { margin-top: 4px; color: var(--muted); }
.course-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
.course-card { padding: 16px; display: grid; gap: 10px; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); box-shadow: var(--shadow); }
.course-card-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.course-card h3, .course-card p { margin: 0; }
.course-progress-text { color: #4f6388; font-size: 12px; }
.workspace-shell { display: grid; gap: 14px; }
.workspace-tabs { display: flex; gap: 4px; overflow-x: auto; border-bottom: 1px solid var(--line); background: var(--surface); }
.workspace-tabs button { min-height: 44px; padding: 10px 14px; border: 0; border-bottom: 3px solid transparent; background: transparent; white-space: nowrap; }
.workspace-tabs button.active { border-bottom-color: var(--blue); color: var(--blue-dark); font-weight: 700; }
.dashboard-focus { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.6fr); gap: 16px; }
```

在 `@media (max-width: 1120px)` 中将 `.course-grid` 改为两列；在 `@media (max-width: 760px)` 中将 `.course-grid`、`.dashboard-focus` 改为一列，并让 `.page-section-head` 纵向排列。

- [ ] **Step 3：运行前端测试与生产构建**

```powershell
cd apps/web
npm test -- --run
$env:VITE_BASE_PATH='/design/'
$env:VITE_API_BASE_URL='/design/api'
npm run build
Remove-Item Env:\VITE_BASE_PATH
Remove-Item Env:\VITE_API_BASE_URL
```

Expected: 测试全部 PASS，Vite 构建成功。

- [ ] **Step 4：启动本地服务并做桌面/移动视觉检查**

启动 API 和前端，使用浏览器检查 `1440x900`、`1024x768`、`390x844` 三个视口：

- 页面填满浏览器，不出现嵌套卡片堆叠。
- 四个课程页签不换行挤压，窄屏允许横向滚动。
- “整门课教案”和“课程实施大纲”编辑区保持最大可用宽度。
- 顶栏、页签和操作按钮没有重叠。
- 原有表格在窄屏通过容器横向滚动，不压缩字段内容。

- [ ] **Step 5：提交响应式样式**

```powershell
git add apps/web/src/styles.css apps/web/src/App.test.tsx
git commit -m "style: refine course workspace layout"
```

## Task 6：文档、全量回归和部署

**Files:**
- Modify: `README.md`

- [ ] **Step 1：更新 README 产品入口**

将 MVP Scope 更新为：

```markdown
## Current Scope

- Teacher and administrator accounts
- Semester course dashboard and course workspace
- Course standard and Excel schedule import
- Editable course implementation outline
- Whole-course lesson plan generation and editing
- DOCX export using uploaded school templates

The product remains a teacher-side preparation tool. Student submission and LMS delivery stay in the school's existing platforms.
```

- [ ] **Step 2：运行全量验证**

```powershell
cd apps/api
pytest -q
cd ../web
npm test -- --run
$env:VITE_BASE_PATH='/design/'
$env:VITE_API_BASE_URL='/design/api'
npm run build
Remove-Item Env:\VITE_BASE_PATH
Remove-Item Env:\VITE_API_BASE_URL
```

Expected: 后端、前端测试和生产构建全部通过。

- [ ] **Step 3：提交文档更新**

```powershell
git add README.md
git commit -m "docs: describe semester course workspace"
```

- [ ] **Step 4：部署至腾讯云教学设计系统路径**

使用现有私钥路径和部署结构，将应用更新到：

- API：`/opt/teaching-design-system`，监听 `127.0.0.1:8002`。
- Web：`/var/www/teaching-design-system/design`。
- 公网入口：`http://124.221.239.254/design/`。

仅重启 `teaching-design.service`，不得修改 `teacher-achievement.service` 或根路径 Nginx 配置。

- [ ] **Step 5：部署后健康检查**

```powershell
ssh -i "$env:USERPROFILE\.ssh\teacher_achievement_tencent_ed25519" ubuntu@124.221.239.254 "systemctl is-active teaching-design.service; systemctl is-active teacher-achievement.service; curl -s -o /dev/null -w 'design=%{http_code}\n' http://127.0.0.1/design/; curl -s -o /dev/null -w 'api=%{http_code}\n' http://127.0.0.1:8002/health; curl -s -o /dev/null -w 'root=%{http_code}\n' http://127.0.0.1/"
```

Expected:

```text
active
active
design=200
api=200
root=200 或 root=303
```

- [ ] **Step 6：浏览器线上验收**

登录线上系统并验证：

1. 首页显示今天/下一次课和待处理事项。
2. “我的课程”可以进入课程工作台。
3. 四个课程页签均可访问。
4. 实施大纲可以编辑和导出。
5. 整门课教案可以生成、编辑和导出。
6. 管理员账号管理和修改密码仍可使用。

## 第一阶段完成标准

- 教师顶层导航不再把大纲、教案、作业试卷作为互不关联的模块。
- 首页以今天课程、下一次课和待处理事项组织持续使用入口。
- “我的课程”与课程工作台成为主要业务入口。
- 课程实施大纲、整门课教案和课次材料处于同一课程上下文中。
- 所有现有后端接口和 Word 导出流程保持兼容。
- 学生端、提交、批改和正式成绩管理没有进入本阶段范围。
