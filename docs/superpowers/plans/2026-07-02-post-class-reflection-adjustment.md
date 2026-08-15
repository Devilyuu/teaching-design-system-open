# 课后记录与后续课次调整实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让教师在单次课工作台用一分钟保存课后记录，并在明确确认后把规则化建议追加到下一次课教案，支持幂等应用和精准撤销。

**Architecture:** 新增独立的 `PostClassReflection` 表保存结构化记录、建议和应用状态；纯函数服务负责建议生成与带来源标记的教案区块拼接/移除；现有课次工作台 API 聚合记录和下一次课状态。前端在单次课页面底部增加轻量编辑区，课程实施大纲只返回状态标记，不被任何课后操作修改。

**Tech Stack:** FastAPI、SQLModel、Pydantic、pytest、React、TypeScript、Vitest、Testing Library、Vite。

---

## 文件结构

- Create: `apps/api/app/services/post_class_reflection.py`：建议规则、下一次课衔接区块生成和精准移除。
- Create: `apps/api/tests/test_post_class_reflection.py`：纯规则和文本区块单元测试。
- Create: `apps/api/tests/test_post_class_reflection_api.py`：记录增删改、权限、应用、撤销和教案重生成测试。
- Modify: `apps/api/app/models.py`：新增 `PostClassReflection` 表。
- Modify: `apps/api/app/schemas.py`：新增记录输入输出类型，扩展课次工作台和大纲行状态。
- Modify: `apps/api/app/routes/tasks.py`：增加记录接口、应用接口、工作台聚合和教案重生成保护。
- Modify: `apps/web/src/types.ts`：增加课后记录类型和课次状态字段。
- Modify: `apps/web/src/api.ts`：增加保存、删除、应用和撤销请求。
- Modify: `apps/web/src/api.test.ts`：验证新请求的 URL、方法和请求体。
- Modify: `apps/web/src/SessionWorkspacePage.tsx`：增加一分钟课后记录区。
- Modify: `apps/web/src/App.tsx`：课次列表展示“已记录”和“含上次课调整”。
- Modify: `apps/web/src/App.test.tsx`：覆盖完整教师交互。
- Modify: `apps/web/src/styles.css`：增加宽编辑区、分段按钮和移动端布局。
- Modify: `README.md`：记录持续备课闭环能力。

### Task 1：建立课后记录模型和规则服务

**Files:**
- Create: `apps/api/app/services/post_class_reflection.py`
- Create: `apps/api/tests/test_post_class_reflection.py`
- Modify: `apps/api/app/models.py`

- [ ] **Step 1：写建议规则和区块处理失败测试**

```python
from app.services.post_class_reflection import (
    build_adjustment_block,
    generate_adjustment_suggestion,
    remove_adjustment_block,
)


def test_partial_progress_and_average_mastery_add_review_time():
    suggestion = generate_adjustment_suggestion("partial", "average", "normal", "示范环节未完成")
    assert suggestion.suggested_minutes == 20
    assert "补讲" in suggestion.text
    assert "复习" in suggestion.text
    assert "示范环节未完成" in suggestion.text


def test_all_good_requires_no_adjustment():
    suggestion = generate_adjustment_suggestion("completed", "good", "smooth", "")
    assert suggestion.requires_adjustment is False
    assert suggestion.suggested_minutes == 0


def test_remove_adjustment_block_preserves_later_teacher_changes():
    original = "导入\n讲授新知识"
    applied = build_adjustment_block(original, 7, "第 1 次课", "复习 20 分钟")
    edited = applied + "\n教师后来新增的总结"
    assert remove_adjustment_block(edited, 7) == original + "\n教师后来新增的总结"
```

- [ ] **Step 2：运行测试并确认红灯**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_post_class_reflection.py -q`

Expected: FAIL，`app.services.post_class_reflection` 尚不存在。

- [ ] **Step 3：实现最小规则服务**

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class AdjustmentSuggestion:
    suggestion_type: str
    text: str
    suggested_minutes: int
    requires_adjustment: bool


def generate_adjustment_suggestion(progress: str, mastery: str, effect: str, note: str) -> AdjustmentSuggestion:
    actions: list[str] = []
    minutes = 0
    kinds: list[str] = []
    if progress == "partial":
        actions.append("补讲本次课未完成内容")
        minutes = 20
        kinds.append("progress")
    elif progress == "not_completed":
        actions.append("优先完成本次课遗留内容")
        minutes = 40
        kinds.append("progress")
    if mastery == "average":
        actions.append("安排复习、示范或基础练习")
        kinds.append("mastery")
    elif mastery == "weak":
        actions.append("增加分步示范和基础练习，并降低新任务难度")
        kinds.append("mastery")
    if effect == "needs_adjustment":
        actions.append("调整课堂活动组织方式或降低任务复杂度")
        kinds.append("effect")
    if not actions:
        return AdjustmentSuggestion("none", "本次课正常完成，无需调整下一次课。", 0, False)
    context = f"补充说明：{note.strip()}。" if note.strip() else ""
    return AdjustmentSuggestion("+".join(kinds), f"{context}建议" + "；".join(actions) + "。", minutes, True)


def build_adjustment_block(process: str, reflection_id: int, source_label: str, suggestion: str) -> str:
    start = f"【上次课衔接调整·记录 {reflection_id} 开始】"
    end = f"【上次课衔接调整·记录 {reflection_id} 结束】"
    return f"{start}\n来源：{source_label}\n{suggestion}\n{end}\n{process}"


def remove_adjustment_block(process: str, reflection_id: int) -> str:
    start = f"【上次课衔接调整·记录 {reflection_id} 开始】"
    end = f"【上次课衔接调整·记录 {reflection_id} 结束】"
    before, separator, rest = process.partition(start)
    if not separator:
        return process
    _, end_separator, after = rest.partition(end)
    return process if not end_separator else (before + after.lstrip("\n"))
```

- [ ] **Step 4：增加持久化模型并验证建表**

```python
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
```

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_post_class_reflection.py tests/test_session_material_models.py -q`

Expected: PASS。

- [ ] **Step 5：提交规则与模型**

```bash
git add apps/api/app/models.py apps/api/app/services/post_class_reflection.py apps/api/tests/test_post_class_reflection.py
git commit -m "feat: add post-class reflection rules"
```

### Task 2：实现课后记录读取、保存和删除接口

**Files:**
- Create: `apps/api/tests/test_post_class_reflection_api.py`
- Modify: `apps/api/app/schemas.py`
- Modify: `apps/api/app/routes/tasks.py`

- [ ] **Step 1：写记录 CRUD 与下一次课失败测试**

```python
def test_teacher_saves_reflection_and_workspace_returns_suggestion(client, auth_headers, prepared_task):
    task_id, first_row_id, second_row_id = prepared_task
    response = client.put(
        f"/tasks/{task_id}/sessions/{first_row_id}/reflection",
        headers=auth_headers,
        json={
            "progress_status": "partial",
            "mastery_level": "average",
            "classroom_effect": "normal",
            "note": "示范环节未完成",
        },
    )
    assert response.status_code == 200
    assert response.json()["target_outline_row_id"] == second_row_id
    workspace = client.get(f"/tasks/{task_id}/sessions/{first_row_id}", headers=auth_headers).json()
    assert workspace["reflection"]["suggested_minutes"] == 20
    assert workspace["next_outline"]["id"] == second_row_id


def test_last_session_saves_without_target(client, auth_headers, prepared_task):
    task_id, _, last_row_id = prepared_task
    response = client.put(
        f"/tasks/{task_id}/sessions/{last_row_id}/reflection",
        headers=auth_headers,
        json={"progress_status": "completed", "mastery_level": "good", "classroom_effect": "smooth", "note": ""},
    )
    assert response.status_code == 200
    assert response.json()["target_outline_row_id"] is None


def test_applied_reflection_cannot_be_deleted(client, auth_headers, applied_reflection):
    task_id, reflection_id = applied_reflection
    response = client.delete(f"/tasks/{task_id}/reflections/{reflection_id}", headers=auth_headers)
    assert response.status_code == 409
```

- [ ] **Step 2：运行接口测试并确认红灯**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_post_class_reflection_api.py -q`

Expected: FAIL，记录接口返回 `404`。

- [ ] **Step 3：增加请求、响应和工作台类型**

```python
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
```

- [ ] **Step 4：实现下一次课查找、保存和删除**

```python
def _get_next_outline_row(task_id: int, row: OutlineRow, session: Session) -> OutlineRow | None:
    return session.exec(
        select(OutlineRow)
        .where(OutlineRow.task_id == task_id, OutlineRow.session_no > row.session_no)
        .order_by(OutlineRow.session_no)
    ).first()


@router.put("/{task_id}/sessions/{outline_row_id}/reflection", response_model=PostClassReflectionRead)
def upsert_reflection(
    task_id: int,
    outline_row_id: int,
    payload: PostClassReflectionUpsert,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> PostClassReflection:
    task = _get_task_or_404(task_id, session, current_user)
    outline = _get_outline_row_or_404(task_id, outline_row_id, session)
    existing = session.exec(select(PostClassReflection).where(PostClassReflection.outline_row_id == outline_row_id)).first()
    if existing and existing.status == "applied":
        raise HTTPException(status_code=409, detail="Revert the applied adjustment before editing")
    suggestion = generate_adjustment_suggestion(
        payload.progress_status, payload.mastery_level, payload.classroom_effect, payload.note
    )
    target = _get_next_outline_row(task_id, outline, session)
    reflection = existing or PostClassReflection(
        task_id=task.id, outline_row_id=outline.id, owner_user_id=current_user.id
    )
    for key, value in payload.model_dump().items():
        setattr(reflection, key, value)
    reflection.suggestion_type = suggestion.suggestion_type
    reflection.suggestion_text = suggestion.text
    reflection.suggested_minutes = suggestion.suggested_minutes
    reflection.target_outline_row_id = target.id if target else None
    reflection.status = "pending"
    reflection.applied_lesson_plan_id = None
    reflection.applied_block_marker = ""
    reflection.updated_at = datetime.now(timezone.utc)
    reflection.applied_at = None
    reflection.reverted_at = None
    session.add(reflection)
    session.commit()
    session.refresh(reflection)
    return reflection
```

删除接口只允许删除 `pending` 或 `reverted` 记录：

```python
@router.delete("/{task_id}/reflections/{reflection_id}", status_code=204)
def delete_reflection(
    task_id: int,
    reflection_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Response:
    _get_task_or_404(task_id, session, current_user)
    reflection = _get_reflection_or_404(task_id, reflection_id, session)
    if reflection.status == "applied":
        raise HTTPException(status_code=409, detail="Revert the applied adjustment before deleting")
    session.delete(reflection)
    session.commit()
    return Response(status_code=204)
```

工作台读取接口同时查询当前记录、下一次课和目标教案是否存在。

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_post_class_reflection_api.py -q`

Expected: CRUD、最后一次课和权限场景 PASS。

- [ ] **Step 5：提交记录接口**

```bash
git add apps/api/app/schemas.py apps/api/app/routes/tasks.py apps/api/tests/test_post_class_reflection_api.py
git commit -m "feat: add post-class reflection api"
```

### Task 3：实现应用、撤销和教案重生成一致性

**Files:**
- Modify: `apps/api/app/services/post_class_reflection.py`
- Modify: `apps/api/app/routes/tasks.py`
- Modify: `apps/api/tests/test_post_class_reflection.py`
- Modify: `apps/api/tests/test_post_class_reflection_api.py`

- [ ] **Step 1：写应用、幂等、撤销和重生成失败测试**

```python
def test_apply_appends_once_and_revert_preserves_teacher_changes(client, auth_headers, reflection_with_next_lesson):
    task_id, reflection_id, lesson_id = reflection_with_next_lesson
    first = client.post(f"/tasks/{task_id}/reflections/{reflection_id}/apply", headers=auth_headers)
    second = client.post(f"/tasks/{task_id}/reflections/{reflection_id}/apply", headers=auth_headers)
    assert first.status_code == second.status_code == 200
    assert second.json()["teaching_process"].count(f"记录 {reflection_id} 开始") == 1

    lesson = second.json()
    lesson["teaching_process"] += "\n教师后来新增的总结"
    client.put(f"/tasks/{task_id}/lessons/{lesson_id}", headers=auth_headers, json=lesson)
    reverted = client.post(f"/tasks/{task_id}/reflections/{reflection_id}/revert", headers=auth_headers)
    assert "教师后来新增的总结" in reverted.json()["teaching_process"]
    assert f"记录 {reflection_id} 开始" not in reverted.json()["teaching_process"]


def test_apply_without_next_lesson_stays_pending(client, auth_headers, reflection_without_lesson):
    task_id, reflection_id = reflection_without_lesson
    response = client.post(f"/tasks/{task_id}/reflections/{reflection_id}/apply", headers=auth_headers)
    assert response.status_code == 409


def test_regenerating_whole_course_reapplies_active_adjustment(client, auth_headers, applied_reflection):
    task_id, reflection_id = applied_reflection
    response = client.post(f"/tasks/{task_id}/lessons/generate", headers=auth_headers)
    target = next(item for item in response.json() if f"记录 {reflection_id} 开始" in item["teaching_process"])
    assert target["outline_row_id"] is not None
```

- [ ] **Step 2：运行定向测试并确认红灯**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_post_class_reflection_api.py -q`

Expected: FAIL，应用和撤销接口尚不存在。

- [ ] **Step 3：实现应用和撤销接口**

```python
@router.post("/{task_id}/reflections/{reflection_id}/apply", response_model=LessonPlanRead)
def apply_reflection(
    task_id: int,
    reflection_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> LessonPlan:
    reflection = _get_reflection_or_404(task_id, reflection_id, session)
    if reflection.status == "applied":
        return session.get(LessonPlan, reflection.applied_lesson_plan_id)
    if reflection.target_outline_row_id is None:
        raise HTTPException(status_code=409, detail="This is the final session")
    lesson = _get_lesson_by_outline(task_id, reflection.target_outline_row_id, session)
    if lesson is None:
        raise HTTPException(status_code=409, detail="Generate the next lesson plan before applying")
    lesson.teaching_process = build_adjustment_block(
        lesson.teaching_process, reflection.id, f"第 {source.session_no} 次课", reflection.suggestion_text
    )
    reflection.status = "applied"
    reflection.applied_lesson_plan_id = lesson.id
    reflection.applied_block_marker = f"post-class-reflection:{reflection.id}"
    reflection.applied_at = datetime.now(timezone.utc)
    session.add(lesson)
    session.add(reflection)
    session.commit()
    session.refresh(lesson)
    return lesson
```

撤销接口用 `remove_adjustment_block` 只移除目标区块，清空应用教案关联并把状态改为 `reverted`：

```python
@router.post("/{task_id}/reflections/{reflection_id}/revert", response_model=LessonPlanRead)
def revert_reflection(
    task_id: int,
    reflection_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> LessonPlan:
    _get_task_or_404(task_id, session, current_user)
    reflection = _get_reflection_or_404(task_id, reflection_id, session)
    lesson = _get_lesson_by_outline(task_id, reflection.target_outline_row_id, session)
    if lesson is None:
        raise HTTPException(status_code=409, detail="The target lesson plan is not available")
    if reflection.status == "applied":
        lesson.teaching_process = remove_adjustment_block(lesson.teaching_process, reflection.id)
        reflection.status = "reverted"
        reflection.applied_lesson_plan_id = None
        reflection.applied_block_marker = ""
        reflection.reverted_at = datetime.now(timezone.utc)
        session.add(lesson)
        session.add(reflection)
        session.commit()
        session.refresh(lesson)
    return lesson
```

- [ ] **Step 4：在整门课教案重生成后恢复有效调整**

在 `generate_lessons` 删除旧教案前读取所有 `status == "applied"` 的记录；新教案写入并取得 ID 后，按 `target_outline_row_id` 重新追加区块，并更新 `applied_lesson_plan_id`。若目标课次已不存在，将记录恢复为 `pending`，不得修改大纲。

```python
active_reflections = session.exec(
    select(PostClassReflection).where(
        PostClassReflection.task_id == task_id,
        PostClassReflection.status == "applied",
    )
).all()
```

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_post_class_reflection.py tests/test_post_class_reflection_api.py -q`

Expected: 应用、幂等、撤销、无教案和重生成场景 PASS。

- [ ] **Step 5：提交应用闭环**

```bash
git add apps/api/app/services/post_class_reflection.py apps/api/app/routes/tasks.py apps/api/tests/test_post_class_reflection.py apps/api/tests/test_post_class_reflection_api.py
git commit -m "feat: apply post-class adjustments to lessons"
```

### Task 4：接入前端类型和 API

**Files:**
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/api.ts`
- Modify: `apps/web/src/api.test.ts`

- [ ] **Step 1：写前端 API 失败测试**

```typescript
it("saves and applies a post-class reflection", async () => {
  fetchMock
    .mockResolvedValueOnce(jsonResponse(reflectionFixture))
    .mockResolvedValueOnce(jsonResponse(lessonFixture));

  await upsertPostClassReflection(3, 9, {
    progress_status: "partial",
    mastery_level: "average",
    classroom_effect: "normal",
    note: "示范环节未完成"
  });
  await applyPostClassReflection(3, 12);

  expect(fetchMock).toHaveBeenNthCalledWith(1, expect.stringContaining("/tasks/3/sessions/9/reflection"), expect.objectContaining({ method: "PUT" }));
  expect(fetchMock).toHaveBeenNthCalledWith(2, expect.stringContaining("/tasks/3/reflections/12/apply"), expect.objectContaining({ method: "POST" }));
});
```

- [ ] **Step 2：运行测试并确认红灯**

Run: `cd apps/web && npm test -- --run src/api.test.ts`

Expected: FAIL，新 API 函数尚未导出。

- [ ] **Step 3：增加类型和请求函数**

```typescript
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
  suggestion_text: string;
  suggested_minutes: number;
  status: "pending" | "applied" | "reverted";
  target_outline_row_id: number | null;
  applied_lesson_plan_id: number | null;
  applied_at: string | null;
}
```

```typescript
export function upsertPostClassReflection(taskId: number, outlineRowId: number, payload: PostClassReflectionInput) {
  return request<PostClassReflection>(`/tasks/${taskId}/sessions/${outlineRowId}/reflection`, {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function applyPostClassReflection(taskId: number, reflectionId: number) {
  return request<LessonPlan>(`/tasks/${taskId}/reflections/${reflectionId}/apply`, { method: "POST" });
}
```

增加删除和撤销请求，并扩展 `SessionWorkspace`：

```typescript
export function deletePostClassReflection(taskId: number, reflectionId: number): Promise<void> {
  return request<void>(`/tasks/${taskId}/reflections/${reflectionId}`, { method: "DELETE" });
}

export function revertPostClassReflection(taskId: number, reflectionId: number) {
  return request<LessonPlan>(`/tasks/${taskId}/reflections/${reflectionId}/revert`, { method: "POST" });
}

export interface SessionWorkspace {
  outline: OutlineRow;
  lesson: LessonPlan | null;
  materials: SessionMaterial[];
  reflection: PostClassReflection | null;
  next_outline: OutlineRow | null;
  next_lesson_exists: boolean;
}
```

- [ ] **Step 4：运行测试并提交**

Run: `cd apps/web && npm test -- --run src/api.test.ts`

Expected: PASS。

```bash
git add apps/web/src/types.ts apps/web/src/api.ts apps/web/src/api.test.ts
git commit -m "feat: add post-class reflection frontend api"
```

### Task 5：实现课后记录界面和课次状态

**Files:**
- Modify: `apps/web/src/SessionWorkspacePage.tsx`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/App.test.tsx`
- Modify: `apps/web/src/styles.css`

- [ ] **Step 1：写完整交互失败测试**

```typescript
it("records a completed session and applies its suggestion to the next lesson", async () => {
  render(<App />);
  await loginAndOpenFirstSession();

  await user.click(screen.getByRole("button", { name: "部分完成" }));
  await user.click(screen.getByRole("button", { name: "一般" }));
  await user.click(screen.getByRole("button", { name: "基本正常" }));
  await user.type(screen.getByLabelText("补充说明"), "示范环节未完成");
  await user.click(screen.getByRole("button", { name: "保存课后记录" }));

  expect(await screen.findByText(/建议下一次课/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "应用到下次课教案" }));
  expect(await screen.findByText(/已应用到第 2 次课/)).toBeInTheDocument();
});

it("shows pending state when the next lesson does not exist", async () => {
  render(<App />);
  await loginAndOpenFirstSessionWithoutNextLesson();
  expect(await screen.findByText("生成下一次课教案后可应用")).toBeInTheDocument();
});
```

- [ ] **Step 2：运行测试并确认红灯**

Run: `cd apps/web && npm test -- --run src/App.test.tsx`

Expected: FAIL，页面没有课后记录控件。

- [ ] **Step 3：实现一分钟记录区**

在 `SessionWorkspacePage` 增加本地草稿，三个维度使用复用的分段按钮组件：

```tsx
<section className="post-class-section" aria-labelledby="post-class-title">
  <div className="section-title-row">
    <div><h3 id="post-class-title">课后记录</h3><span>约 1 分钟</span></div>
  </div>
  <SegmentedField label="授课进度" value={draft.progress_status} options={progressOptions} onChange={(progress_status) => setDraft({ ...draft, progress_status })} />
  <SegmentedField label="学生掌握" value={draft.mastery_level} options={masteryOptions} onChange={(mastery_level) => setDraft({ ...draft, mastery_level })} />
  <SegmentedField label="课堂效果" value={draft.classroom_effect} options={effectOptions} onChange={(classroom_effect) => setDraft({ ...draft, classroom_effect })} />
  <label>补充说明<textarea value={draft.note} maxLength={500} onChange={(event) => setDraft({ ...draft, note: event.target.value })} /></label>
  <button className="btn primary" onClick={saveReflection}>保存课后记录</button>
</section>
```

保存后展示建议文本、建议时长和状态。只有 `next_outline` 存在、`next_lesson_exists` 为真且建议需要调整时启用应用按钮；已应用时展示目标课次和撤销按钮。

- [ ] **Step 4：给课次列表增加状态标记**

扩展 `OutlineRowRead` 和前端 `OutlineRow`：

```typescript
post_class_recorded: boolean;
has_previous_adjustment: boolean;
```

后端 `list_outline_rows` 批量读取当前课程记录，生成两个 ID 集合后填充字段，避免逐行查询。前端在 `CourseSessionsPage` 中显示短标签，不新增卡片或说明面板。

- [ ] **Step 5：增加响应式样式并运行测试**

```css
.post-class-section { padding: 24px; border-top: 1px solid var(--line); }
.reflection-fields { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 18px; }
.reflection-option-group { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); }
.reflection-suggestion { border-left: 3px solid var(--primary); padding: 16px 18px; background: var(--primary-soft); }

@media (max-width: 760px) {
  .reflection-fields { grid-template-columns: 1fr; }
  .reflection-option-group { grid-template-columns: 1fr; }
}
```

Run: `cd apps/web && npm test -- --run`

Expected: 全部前端测试 PASS。

- [ ] **Step 6：提交页面**

```bash
git add apps/web/src/SessionWorkspacePage.tsx apps/web/src/App.tsx apps/web/src/App.test.tsx apps/web/src/styles.css
git commit -m "feat: add post-class reflection workspace"
```

### Task 6：全量验证、文档和部署

**Files:**
- Modify: `README.md`
- Verify: `apps/api/tests/`
- Verify: `apps/web/src/`
- Verify: `docs/deployment/tencent-lighthouse.md`

- [ ] **Step 1：更新当前能力说明**

在 README 的 MVP 范围中增加：

```markdown
- One-minute post-class reflection with teacher-confirmed adjustments appended to the next lesson plan
```

- [ ] **Step 2：运行后端全量测试**

Run: `cd apps/api && .venv/Scripts/python -m pytest -q`

Expected: 全部 PASS，仅允许已有的 Starlette 兼容性警告。

- [ ] **Step 3：运行前端全量测试和生产构建**

Run: `cd apps/web && npm test -- --run`

Expected: 全部 PASS。

Run: `cd apps/web && $env:VITE_BASE_PATH='/design/'; npm run build`

Expected: TypeScript 和 Vite 构建成功，产物写入 `apps/web/dist`。

- [ ] **Step 4：真实浏览器响应式验收**

在 `1440x900`、`1024x768` 和 `390x844` 下验证：

- 三组选项、补充说明、建议和操作按钮无重叠。
- 页面无横向溢出。
- 保存、应用和撤销会立即更新状态。
- 课次列表状态与单次课工作台一致。
- 浏览器控制台无应用错误。

- [ ] **Step 5：提交文档并推送分支**

```bash
git add README.md
git commit -m "docs: describe post-class preparation loop"
git push origin codex/mvp-outline-export-pr
```

- [ ] **Step 6：备份并部署到腾讯云独立教学系统**

部署前备份：

- `/var/lib/teaching-design-system/teaching_design.db`
- `/opt/teaching-design-system/apps/api/app`
- `/var/www/teaching-design-system/design`

只更新 `/opt/teaching-design-system` 和 `/var/www/teaching-design-system/design`，只重启 `teaching-design.service`。不得修改 `teacher-achievement.service`、端口 `8001` 或成果管理系统目录。

- [ ] **Step 7：线上验收**

验证：

- `teaching-design.service` 和 `teacher-achievement.service` 均为 `active`。
- `http://124.221.239.254/design/` 返回 `200` 并显示登录页。
- 公网登录后可保存记录、应用并撤销建议。
- `PostClassReflection` 表已自动创建。
- 新接口出现在 OpenAPI 中。
- 线上前端资源哈希与本地构建一致。

## 完成标准

- 课后记录、建议、应用和撤销形成可重复验证的闭环。
- 未经确认不会修改后续教案，任何情况下都不会修改课程实施大纲。
- 下一次课无教案、最后一次课、重复请求和整门课教案重生成都有明确行为。
- 教师和管理员沿用现有权限边界。
- 本地测试、生产构建、真实浏览器和线上检查全部通过。
