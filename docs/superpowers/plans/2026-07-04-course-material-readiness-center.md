# Course Material Readiness Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a recoverable course-material workspace where teachers can safely replace authoritative sources, review schedule changes, see exact generation blockers, and continue the first outline-generation flow from an existing course.

**Architecture:** Persist current material metadata separately from parsed domain records, stage every replacement before switching the effective record, and expose one backend-owned readiness projection to the frontend. Schedule uploads become pending candidates with explicit diff confirmation; the existing course workspace gains a dedicated materials tab and the new-course screen stops duplicating material maintenance.

**Tech Stack:** FastAPI, SQLModel, SQLite, Pydantic, python-docx, openpyxl, React, TypeScript, Vitest

---

## File Structure

- Modify `apps/api/app/models.py`: add current material metadata, schedule candidate rows, and review notices.
- Modify `apps/api/app/schemas.py`: define readiness, material, schedule-diff, and notice API contracts.
- Create `apps/api/app/services/course_readiness.py`: compute blockers and recommended next action from authoritative backend state.
- Create `apps/api/app/services/task_material_store.py`: validate, stage, and activate uniquely named uploaded files.
- Create `apps/api/app/services/schedule_candidate.py`: compare, apply, and discard schedule candidates.
- Modify `apps/api/app/routes/tasks.py`: expose material, readiness, schedule candidate, and notice endpoints; use safe replacement in existing uploads.
- Create `apps/api/tests/test_course_readiness.py`: unit coverage for blocker rules and legacy fallback.
- Create `apps/api/tests/test_task_material_workflow.py`: API coverage for safe replacement, schedule confirmation, permissions, and notices.
- Modify `apps/api/tests/test_outline_workflow_api.py`: keep outline generation and export compatible with active material metadata.
- Modify `apps/web/src/types.ts`: frontend readiness contracts.
- Modify `apps/web/src/api.ts`: readiness, upload, schedule confirmation, and notice APIs.
- Create `apps/web/src/CourseMaterialsPage.tsx`: dedicated material maintenance workspace.
- Create `apps/web/src/CourseMaterialsPage.test.tsx`: focused interaction tests.
- Modify `apps/web/src/App.tsx`: add the materials tab, simplify new-course creation, and route generation through readiness.
- Modify `apps/web/src/App.test.tsx`: course navigation and new-course continuation tests.
- Modify `apps/web/src/styles.css`: large editing surface and responsive states.

### Task 1: Persist Material State and Compute Readiness

**Files:**
- Modify: `apps/api/app/models.py`
- Modify: `apps/api/app/schemas.py`
- Create: `apps/api/app/services/course_readiness.py`
- Create: `apps/api/tests/test_course_readiness.py`

- [ ] **Step 1: Write failing readiness tests**

Create `test_course_readiness.py` with focused cases:

```python
def test_readiness_lists_each_missing_requirement():
    result = build_course_readiness(
        task=task(total_hours=32),
        materials=[],
        goals=[],
        projects=[],
        indicators=[],
        confirmation=None,
        schedule=[],
        outline_rows=[],
        ai_config=None,
        notices=[],
        legacy_templates=set(),
    )
    assert result.can_generate_outline is False
    assert [item.code for item in result.blocking_reasons] == [
        "talent_plan_missing",
        "course_standard_missing",
        "schedule_missing",
        "outline_template_missing",
        "sources_unconfirmed",
        "ai_model_unavailable",
    ]


def test_readiness_allows_first_generation_only_when_every_condition_is_ready():
    result = build_course_readiness(**ready_inputs())
    assert result.can_generate_outline is True
    assert result.next_action == "generate_outline"


def test_readiness_routes_existing_outline_to_editor_instead_of_generation():
    inputs = ready_inputs()
    inputs["outline_rows"] = [outline_row(session_no=1)]
    result = build_course_readiness(**inputs)
    assert result.can_generate_outline is False
    assert result.next_action == "open_outline"
    assert result.blocking_reasons == []


def test_readiness_recognizes_legacy_parsed_sources_and_templates():
    result = build_course_readiness(
        **ready_inputs(materials=[], legacy_templates={"outline", "lesson"})
    )
    assert result.materials["course_standard"].status == "ready"
    assert "原文件名未记录" in result.materials["course_standard"].message
```

- [ ] **Step 2: Run the tests and confirm the missing module failure**

Run:

```powershell
cd apps/api
.\.venv\Scripts\python.exe -m pytest tests/test_course_readiness.py -q
```

Expected: FAIL because `course_readiness` and the new contracts do not exist.

- [ ] **Step 3: Add the persistence models**

Add these SQLModel tables to `models.py`:

```python
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


class CourseReviewNotice(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(index=True)
    artifact_type: str
    reason: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None
```

`SQLModel.metadata.create_all()` creates these tables on startup, so no destructive migration is required.

- [ ] **Step 4: Define the readiness schemas**

Add exact response contracts in `schemas.py`:

```python
class MaterialReadinessRead(BaseModel):
    kind: str
    status: Literal["missing", "ready", "attention"]
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
    pending_schedule: "ScheduleCandidateRead | None" = None
    review_notices: list[ReviewNoticeRead] = Field(default_factory=list)
```

- [ ] **Step 5: Implement the pure readiness projection**

In `course_readiness.py`, define `CourseReadinessResult`, `MaterialReadiness`, `ReadinessBlocker`, and:

```python
def build_course_readiness(
    *, task, materials, goals, projects, indicators, confirmation,
    schedule, outline_rows, ai_config, notices, legacy_templates,
    pending_schedule=None, uploader_names=None,
) -> CourseReadinessResult:
    ...
```

Rules must be deterministic and ordered as the tests specify. Treat parsed goals/projects as legacy course-standard evidence, parsed indicators as legacy talent-plan evidence, existing schedule rows as legacy schedule evidence, and fixed template files as legacy template evidence. Return `open_outline` whenever outline rows exist, even if later source replacement produced review notices.

- [ ] **Step 6: Run readiness tests and commit**

Run the Task 1 test command and expect PASS.

```powershell
git add apps/api/app/models.py apps/api/app/schemas.py apps/api/app/services/course_readiness.py apps/api/tests/test_course_readiness.py
git commit -m "feat: model course material readiness"
```

### Task 2: Safely Replace Sources and Templates

**Files:**
- Create: `apps/api/app/services/task_material_store.py`
- Modify: `apps/api/app/routes/tasks.py`
- Create: `apps/api/tests/test_task_material_workflow.py`
- Modify: `apps/api/tests/test_outline_workflow_api.py`

- [ ] **Step 1: Write failing safe-replacement API tests**

Cover these behaviors with a temporary `TASK_FILE_DIR`:

```python
def test_invalid_course_standard_keeps_previous_asset_and_confirmation(client, tmp_path, monkeypatch):
    task_id = prepare_confirmed_course(client, tmp_path, monkeypatch)
    before = client.get(f"/tasks/{task_id}/readiness").json()

    response = upload_docx(client, task_id, "course-standard", empty_docx(tmp_path))

    assert response.status_code == 400
    after = client.get(f"/tasks/{task_id}/readiness").json()
    assert after["materials"]["course_standard"]["filename"] == before["materials"]["course_standard"]["filename"]
    assert after["source_review"]["confirmed"] is True


def test_valid_source_replacement_invalidates_confirmation_but_keeps_artifacts(client, tmp_path, monkeypatch):
    task_id = prepare_course_with_outline_lesson_and_material(client, tmp_path, monkeypatch)
    response = upload_docx(client, task_id, "course-standard", replacement_standard(tmp_path))
    assert response.status_code == 200
    readiness = client.get(f"/tasks/{task_id}/readiness").json()
    assert readiness["source_review"]["confirmed"] is False
    assert client.get(f"/tasks/{task_id}/outline").json()
    assert {item["artifact_type"] for item in readiness["review_notices"]} == {"outline", "lesson", "material"}


def test_template_replacement_changes_active_export_template(client, tmp_path, monkeypatch):
    task_id = prepare_outline(client, tmp_path)[0]
    upload_template(client, task_id, "outline", template_with_marker(tmp_path, "NEW"))
    response = client.post(f"/tasks/{task_id}/outline/export")
    assert response.status_code == 200
    assert "NEW" in rendered_docx_text(response.content)
```

- [ ] **Step 2: Verify the tests fail on current direct-write behavior**

Run:

```powershell
cd apps/api
.\.venv\Scripts\python.exe -m pytest tests/test_task_material_workflow.py tests/test_outline_workflow_api.py -q
```

Expected: new tests FAIL because metadata/readiness and active asset lookup do not exist.

- [ ] **Step 3: Implement unique file storage**

Create `task_material_store.py`:

```python
ALLOWED_SUFFIXES = {
    "talent_plan": ".docx",
    "course_standard": ".docx",
    "schedule": ".xlsx",
    "outline_template": ".docx",
    "lesson_template": ".docx",
}


def validate_upload_filename(kind: str, filename: str) -> str:
    expected = ALLOWED_SUFFIXES[kind]
    suffix = Path(filename).suffix.lower()
    if suffix != expected:
        raise MaterialUploadError(f"{kind} 仅支持 {expected} 文件")
    return suffix


def write_unique_asset(root: Path, task_id: int, kind: str, suffix: str, content: bytes) -> Path:
    path = root / str(task_id) / "assets" / kind / f"{uuid4().hex}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def active_asset(session: Session, task_id: int, kind: str) -> TaskMaterialAsset | None:
    return session.exec(
        select(TaskMaterialAsset)
        .where(TaskMaterialAsset.task_id == task_id, TaskMaterialAsset.kind == kind)
        .order_by(TaskMaterialAsset.updated_at.desc())
    ).first()
```

Only create/switch `TaskMaterialAsset` after parsing succeeds. On database commit failure, delete the newly written unreferenced file. Keep old files until a later cleanup job; this phase does not need history UI.

- [ ] **Step 4: Convert authoritative source uploads**

Refactor `upload_course_standard` and `upload_talent_plan` to:

1. validate the original filename;
2. read and parse temporary bytes;
3. reject empty required structures before any delete;
4. write a unique file;
5. replace parsed rows, replace the current asset metadata, invalidate `SourceConfirmation`, create review notices when artifacts exist, then commit once;
6. return `ParseSummary` unchanged for compatibility.

Do not commit inside shared helpers. Preserve the current successful behavior covered by `test_outline_workflow_api.py`.

- [ ] **Step 5: Convert template uploads and export lookup**

Store outline/lesson templates as unique active assets. Change `_resolve_template_path` to:

```python
asset = active_asset(session, task_id, f"{kind}_template")
if asset is not None and Path(asset.storage_path).exists():
    return Path(asset.storage_path)
legacy = _task_template_path(task_id, kind)
if legacy.exists():
    return legacy
raise HTTPException(status_code=400, detail=f"{kind} template is required")
```

Pass `session` into `_resolve_template_path`. Keep legacy fixed-path fallback for deployed courses.

- [ ] **Step 6: Run tests and commit**

Run the Task 2 command, then the full backend suite. Expect PASS.

```powershell
git add apps/api/app/services/task_material_store.py apps/api/app/routes/tasks.py apps/api/tests/test_task_material_workflow.py apps/api/tests/test_outline_workflow_api.py
git commit -m "feat: safely replace course materials"
```

### Task 3: Stage and Confirm Schedule Changes

**Files:**
- Create: `apps/api/app/services/schedule_candidate.py`
- Modify: `apps/api/app/routes/tasks.py`
- Modify: `apps/api/app/schemas.py`
- Modify: `apps/api/tests/test_task_material_workflow.py`

- [ ] **Step 1: Write failing schedule candidate tests**

```python
def test_schedule_upload_creates_candidate_without_replacing_active_schedule(client, tmp_path):
    task_id = prepare_course_with_schedule(client, tmp_path)
    response = upload_schedule_candidate(client, task_id, changed_schedule(tmp_path))
    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    readiness = client.get(f"/tasks/{task_id}/readiness").json()
    assert readiness["pending_schedule"]["changed_count"] == 1
    assert readiness["schedule_hours"] == 8


def test_discard_schedule_candidate_keeps_active_schedule(client, tmp_path):
    candidate = create_candidate(client, tmp_path)
    response = client.post(f"/tasks/{candidate.task_id}/schedule-candidates/{candidate.id}/discard")
    assert response.status_code == 200
    assert response.json()["status"] == "discarded"


def test_confirm_same_count_schedule_updates_outline_calendar_fields(client, tmp_path):
    task_id, row = prepare_outline(client, tmp_path)
    candidate = create_same_count_changed_candidate(client, task_id, tmp_path)
    response = client.post(f"/tasks/{task_id}/schedule-candidates/{candidate.id}/confirm")
    assert response.status_code == 200
    updated = client.get(f"/tasks/{task_id}/outline").json()[0]
    assert updated["date_text"] == "2026-09-08"
    assert updated["topic"] == row["topic"]


def test_confirm_different_count_schedule_is_blocked_when_outline_exists(client, tmp_path):
    task_id, _ = prepare_outline(client, tmp_path)
    candidate = create_three_session_candidate(client, task_id, tmp_path)
    response = client.post(f"/tasks/{task_id}/schedule-candidates/{candidate.id}/confirm")
    assert response.status_code == 409
    assert "课次数量" in response.json()["detail"]
```

- [ ] **Step 2: Run tests and verify candidate endpoints are missing**

Run the Task 2 command. Expected: candidate requests return 404 or current `/schedule` immediately replaces data.

- [ ] **Step 3: Define schedule diff contracts**

Add:

```python
class ScheduleChangeRead(BaseModel):
    session_no: int
    change_type: Literal["added", "removed", "changed"]
    fields: list[str]
    before: dict | None = None
    after: dict | None = None


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
```

- [ ] **Step 4: Implement comparison and application service**

In `schedule_candidate.py`, compare fields:

```python
SCHEDULE_FIELDS = ("week_no", "date_text", "weekday", "periods", "course_name", "class_name", "location", "hours")
```

Match by `session_no`; report added/removed/changed. `apply_schedule_candidate()` must:

- reject non-pending candidates;
- reject candidate/active count mismatch when outline rows exist;
- replace `ScheduleSessionRecord` in one transaction;
- update only `date_text`, `week_no`, `weekday`, and `periods` on matching outline rows;
- set `OutlineRow.updated_at`;
- create one unresolved `outline` review notice when an outline exists;
- switch the active `schedule` material metadata to the candidate file;
- mark the candidate `applied`.

- [ ] **Step 5: Replace direct schedule upload with candidate endpoints**

Use:

```text
POST /tasks/{task_id}/schedule-candidates
POST /tasks/{task_id}/schedule-candidates/{candidate_id}/confirm
POST /tasks/{task_id}/schedule-candidates/{candidate_id}/discard
```

Uploading a new pending candidate discards the previous pending candidate for the same task. Do not delete its active schedule.

Update `prepare_outline`, `prepare_confirmed_sources`, and every existing API test that posts to `/schedule` so the helper uploads a candidate and immediately confirms it. Keep one explicit test proving `/schedule` no longer performs a direct replacement, then remove the obsolete route.

- [ ] **Step 6: Run tests and commit**

Run targeted and full backend tests. Expect PASS.

```powershell
git add apps/api/app/services/schedule_candidate.py apps/api/app/routes/tasks.py apps/api/app/schemas.py apps/api/tests/test_task_material_workflow.py
git commit -m "feat: review schedule replacements"
```

### Task 4: Expose Readiness and Resolve Review Notices

**Files:**
- Modify: `apps/api/app/routes/tasks.py`
- Modify: `apps/api/tests/test_task_material_workflow.py`

- [ ] **Step 1: Add failing readiness API and permission tests**

```python
def test_readiness_returns_materials_blockers_candidate_and_notices(client, tmp_path):
    task_id = prepare_partially_ready_course(client, tmp_path)
    response = client.get(f"/tasks/{task_id}/readiness")
    assert response.status_code == 200
    body = response.json()
    assert set(body["materials"]) == {
        "talent_plan", "course_standard", "schedule", "outline_template", "lesson_template"
    }
    assert body["blocking_reasons"]


def test_teacher_cannot_read_or_change_another_teachers_readiness(teacher_client, other_task_id):
    assert teacher_client.get(f"/tasks/{other_task_id}/readiness").status_code == 404


def test_teacher_can_resolve_review_notice_for_owned_course(client, tmp_path):
    notice_id = prepare_replaced_source_notice(client, tmp_path)
    response = client.post(f"/tasks/1/review-notices/{notice_id}/resolve")
    assert response.status_code == 200
    assert response.json()["status"] == "resolved"
```

- [ ] **Step 2: Verify failures**

Run `pytest tests/test_task_material_workflow.py -q`. Expected: readiness/resolve endpoints return 404.

- [ ] **Step 3: Add `GET /tasks/{task_id}/readiness`**

Load all required rows in the route, call `build_course_readiness`, and serialize to `CourseReadinessRead`. Resolve uploader names in one user query. Pass a pending candidate projection from `schedule_candidate.py`. Use the enabled/connected `AiModelConfig` query already used by outline generation.

- [ ] **Step 4: Add notice resolution**

Add:

```text
POST /tasks/{task_id}/review-notices/{notice_id}/resolve
```

Verify notice ownership through the task, require `resolved_at is None`, set UTC now, commit, and return `{ "status": "resolved" }`.

- [ ] **Step 5: Make outline generation trust readiness**

Before calling the AI service, calculate readiness. If `can_generate_outline` is false, return `409` with the first blocking reason. Keep the existing explicit no-overwrite guard. This makes the UI and generation endpoint use the same rules.

- [ ] **Step 6: Run all backend tests and commit**

```powershell
cd apps/api
.\.venv\Scripts\python.exe -m pytest -q
git add apps/api/app/routes/tasks.py apps/api/tests/test_task_material_workflow.py
git commit -m "feat: expose course generation readiness"
```

### Task 5: Build the Course Materials Workspace

**Files:**
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/api.ts`
- Create: `apps/web/src/CourseMaterialsPage.tsx`
- Create: `apps/web/src/CourseMaterialsPage.test.tsx`
- Modify: `apps/web/src/styles.css`

- [ ] **Step 1: Write failing component tests**

Test the component with injected API functions or mocked `fetch`:

```tsx
it("shows exact blockers and uploads a missing source", async () => {
  renderMaterialsPage(partialReadiness);
  expect(screen.getByText("还需完成 3 项")).toBeInTheDocument();
  expect(screen.getByText("尚未上传课程标准")).toBeInTheDocument();
  await user.upload(screen.getByLabelText("上传课程标准"), standardFile);
  expect(uploadCourseStandard).toHaveBeenCalledWith(1, standardFile);
  expect(getCourseReadiness).toHaveBeenCalledTimes(2);
});


it("reviews and confirms a pending schedule diff", async () => {
  renderMaterialsPage(readinessWithCandidate);
  expect(screen.getByText("变更 1 次课")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "确认使用新课表" }));
  expect(confirmScheduleCandidate).toHaveBeenCalledWith(1, 91);
});


it("opens the outline instead of offering regeneration when rows exist", () => {
  renderMaterialsPage(existingOutlineReadiness);
  expect(screen.queryByRole("button", { name: "AI 生成课程实施大纲" })).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "进入课程实施大纲" })).toBeInTheDocument();
});
```

- [ ] **Step 2: Verify component tests fail because the page is missing**

Run:

```powershell
cd apps/web
npm test -- --run src/CourseMaterialsPage.test.tsx
```

Expected: FAIL with missing module/component.

- [ ] **Step 3: Add frontend contracts and APIs**

Mirror the backend types exactly in `types.ts`. Add in `api.ts`:

```ts
export function getCourseReadiness(taskId: number): Promise<CourseReadiness>;
export function uploadScheduleCandidate(taskId: number, file: File): Promise<ScheduleCandidate>;
export function confirmScheduleCandidate(taskId: number, candidateId: number): Promise<ScheduleCandidate>;
export function discardScheduleCandidate(taskId: number, candidateId: number): Promise<ScheduleCandidate>;
export function resolveReviewNotice(taskId: number, noticeId: number): Promise<{ status: string }>;
```

Keep existing source/template upload functions and update `uploadSchedule` callers to the candidate API.

- [ ] **Step 4: Implement `CourseMaterialsPage`**

Props:

```ts
interface CourseMaterialsPageProps {
  task: TeachingTask;
  onOpenOutline: () => void;
  onTaskRefresh: () => Promise<void>;
  onNotice: (message: string) => void;
  onError: (message: string) => void;
}
```

The page owns readiness loading and per-kind upload state. Render:

- a top readiness band with exact backend blockers;
- five un-nested material rows with filename, summary, status, and upload/replace action;
- source-review section using the existing visual language;
- schedule candidate diff with confirm/discard commands;
- unresolved review notices with “已完成复核”;
- exactly one primary action based on `next_action`.

For `generate_outline`, call source confirmation if not already confirmed, then `generateOutline`, refresh task state, and open the outline tab. Do not show generation when an outline exists.

- [ ] **Step 5: Add responsive styling**

Use the current restrained blue workspace design. The desktop material row grid should be `minmax(180px, .7fr) minmax(260px, 1.4fr) minmax(220px, 1fr) auto`; collapse to one column below 760px. Do not add decorative statistics, nested cards, or explanatory marketing copy.

- [ ] **Step 6: Run component tests and commit**

```powershell
npm test -- --run src/CourseMaterialsPage.test.tsx
git add apps/web/src/types.ts apps/web/src/api.ts apps/web/src/CourseMaterialsPage.tsx apps/web/src/CourseMaterialsPage.test.tsx apps/web/src/styles.css
git commit -m "feat: add course materials workspace"
```

### Task 6: Integrate the Tab and Simplify New-Course Creation

**Files:**
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/App.test.tsx`

- [ ] **Step 1: Write failing navigation and recovery tests**

```tsx
it("opens a dedicated course materials tab for an existing course", async () => {
  openCourse();
  await user.click(screen.getByRole("tab", { name: "课程资料" }));
  expect(await screen.findByRole("heading", { name: "课程资料与生成准备" })).toBeInTheDocument();
});


it("continues a newly saved course in the materials tab", async () => {
  await user.click(screen.getByRole("button", { name: "新建学期课程" }));
  await user.click(screen.getByRole("button", { name: "保存并继续准备资料" }));
  expect(await screen.findByRole("tab", { name: "课程资料" })).toHaveAttribute("aria-selected", "true");
});


it("opens missing materials from the course overview", async () => {
  openCourse(partialTask);
  await user.click(screen.getByRole("button", { name: "补充课程资料" }));
  expect(await screen.findByRole("heading", { name: "课程资料与生成准备" })).toBeInTheDocument();
});
```

- [ ] **Step 2: Verify the tests fail on the four-tab and duplicated upload flow**

Run `npm test -- --run src/App.test.tsx`. Expected: missing tab/button failures.

- [ ] **Step 3: Add the fifth workspace tab**

Change:

```ts
type WorkspaceTab = "overview" | "materials" | "outline" | "lessons" | "sessions";
```

Insert `{ id: "materials", label: "课程资料" }` after overview and render `CourseMaterialsPage` with the selected task.

- [ ] **Step 4: Simplify `NewTaskPage`**

Remove the five upload items and source-review/generation panel from new-course creation. Keep course identity fields and change the submit command to “保存并继续准备资料”. On successful creation:

```ts
setSelectedTaskId(created.id);
setWorkspaceTab("materials");
setView("course");
```

Delete draft-only `materials`, `sourceReview`, `handleReviewSources`, and duplicate generation orchestration from `App` after all call sites move to `CourseMaterialsPage`. Keep export template overrides only where currently needed, or pass `null` so exports use stored active templates.

- [ ] **Step 5: Update overview recovery action**

When required materials are missing, show “补充课程资料”; otherwise show “查看课程资料”. The action opens the new tab. Preserve outline, lesson, and next-session commands.

- [ ] **Step 6: Run frontend tests/build and commit**

```powershell
cd apps/web
npm test -- --run
$env:VITE_BASE_PATH='/design/'
$env:VITE_API_BASE_URL='/design/api'
npm run build
git add apps/web/src/App.tsx apps/web/src/App.test.tsx
git commit -m "feat: continue course setup from materials tab"
```

### Task 7: Full Verification, Push, and Deploy

- [ ] **Step 1: Run all local verification**

```powershell
cd apps/api
.\.venv\Scripts\python.exe -m pytest -q

cd ..\web
npm test -- --run
$env:VITE_BASE_PATH='/design/'
$env:VITE_API_BASE_URL='/design/api'
npm run build
```

Expected: all commands exit 0 with no test failures.

- [ ] **Step 2: Verify the real document parsers**

Parse the provided course standard and talent plan locally. Assert three projects, 32 reference hours, 16 practice hours, and no course-standard ability code outside the parsed talent-plan indicator set.

- [ ] **Step 3: Push the existing branch**

```powershell
git push origin codex/mvp-outline-export-pr
```

- [ ] **Step 4: Back up production before deployment**

Back up:

- `/opt/teaching-design-system/apps/api/app`
- `/var/lib/teaching-design-system/teaching_design.db`
- `/var/www/teaching-design-system/design`

Use a new timestamped directory under `/opt/teaching-design-system/backups`. Do not modify or restart `teacher-achievement.service`.

- [ ] **Step 5: Deploy backend and frontend**

Deploy the committed backend app and built frontend, then restart only `teaching-design.service`. Confirm `nginx -t`, `/health`, `/design/`, and both service states.

- [ ] **Step 6: Perform online non-destructive checks**

With an authenticated test course or the administrator account already available to the user:

- load `/tasks/{id}/readiness`;
- confirm legacy course data is recognized;
- upload an invalid replacement and verify the old source remains ready;
- upload and discard a schedule candidate;
- confirm an existing outline still has no full regeneration action.

Do not replace production authoritative materials during verification. Use a dedicated temporary course and remove only that temporary course if a delete endpoint exists; otherwise leave it clearly named as a test course and report it.
