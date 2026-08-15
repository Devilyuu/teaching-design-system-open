# Single Course Setup Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the course materials workspace the only file-upload, source-review, and first-outline-generation entry point.

**Architecture:** Keep `NewTaskPage` responsible only for creating `TeachingTask` records. Remove its draft file state and orchestration; after creation, route directly to the existing `CourseMaterialsPage`, which already owns the readiness-driven workflow.

**Tech Stack:** React, TypeScript, Vitest, Vite

---

### Task 1: Lock the Single-Entry Behavior With Tests

**Files:**
- Modify: `apps/web/src/App.test.tsx`

- [ ] **Step 1: Replace legacy new-task tests with the desired behavior**

```tsx
it("keeps file uploads out of the new course form", async () => {
  await user.click(await screen.findByRole("button", { name: "新建学期课程" }));
  expect(screen.queryByLabelText("上传课程标准")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "解析并检查课程依据" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "AI 生成课程实施大纲" })).not.toBeInTheDocument();
});

it("continues a newly created course in the materials workspace", async () => {
  await user.click(await screen.findByRole("button", { name: "新建学期课程" }));
  await user.click(screen.getByRole("button", { name: "保存并继续准备资料" }));
  expect(await screen.findByRole("tab", { name: "课程资料" })).toHaveAttribute("aria-selected", "true");
  expect(screen.getByRole("heading", { name: "课程资料与生成准备" })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run tests and confirm the first test fails**

Run: `cd apps/web && npm test -- --run src/App.test.tsx`

Expected: FAIL because the new-course page still contains upload and generation controls.

### Task 2: Remove Legacy Draft Material Flow

**Files:**
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/App.test.tsx`

- [ ] **Step 1: Remove obsolete state and handlers**

Delete `MaterialKey`, `MaterialFiles`, `materials`, `draftTaskId`, `selectMaterial`, `ensureDraftTask`, `handleReviewSources`, and the old `handleGenerateOutline`. Remove their now-unused API and icon imports.

- [ ] **Step 2: Simplify `NewTaskPage` props**

Use this contract:

```ts
function NewTaskPage({ draft, onChange, onSubmit }: {
  draft: TeachingTaskCreate;
  onChange: (draft: TeachingTaskCreate) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
})
```

Render only the page heading, eight course fields, and `保存并继续准备资料`. Delete the steps, upload list, source review, and generation panel.

- [ ] **Step 3: Keep creation failure and success deterministic**

On success:

```ts
setTasks((current) => [created, ...current]);
setSelectedTaskId(created.id);
setWorkspaceTab("materials");
setView("course");
setNotice("任务已创建，请继续补充课程资料");
```

On failure, only set the error; do not clear `taskDraft` or navigate.

- [ ] **Step 4: Use stored templates for exports**

Call `exportOutline(selectedTask.id, null)` and `exportLessonPlans(selectedTask.id, null)`. The server resolves the currently active template.

- [ ] **Step 5: Run focused and full frontend verification**

```powershell
cd apps/web
npm test -- --run src/App.test.tsx
npm test -- --run
$env:VITE_BASE_PATH='/design/'
$env:VITE_API_BASE_URL='/design/api'
npm run build
```

Expected: all tests and build PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/web/src/App.tsx apps/web/src/App.test.tsx
git commit -m "refactor: use one course material setup flow"
```

### Task 3: Verify and Deploy

- [ ] **Step 1: Run backend regression tests**

Run: `cd apps/api && .\.venv\Scripts\python.exe -m pytest -q`

Expected: all backend tests PASS.

- [ ] **Step 2: Push and deploy the frontend build**

Push `codex/mvp-outline-export-pr`, back up the current online frontend, deploy `apps/web/dist`, and restart only `teaching-design.service` if backend files changed. For this frontend-only change, do not restart either application service.

- [ ] **Step 3: Verify online isolation**

Confirm `/design/` and `/` both return HTTP 200 and both `teaching-design.service` and `teacher-achievement.service` remain active.
