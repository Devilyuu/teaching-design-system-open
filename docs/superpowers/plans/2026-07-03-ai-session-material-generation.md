# AI 作业与测试生成实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在单次课工作台中使用已启用的模型生成经过严格代码校验的作业和测试，并继续复用现有编辑、保存和 Word 导出流程。

**Architecture:** 新增独立的课次材料证据和校验服务，通过现有 `OpenAICompatibleClient.generate_json` 调用 DeepSeek。生成接口同步执行，只有通过字段、题量、分值及目标代码校验后才写入 `SessionMaterial`；失败不保存任何材料。

**Tech Stack:** FastAPI、SQLModel、Pydantic、httpx、React、TypeScript、Vitest、Testing Library、DeepSeek OpenAI-compatible API

---

## 文件结构

- Create: `apps/api/app/services/session_material_ai.py`：证据构建、提示词、AI 返回结构和严格校验。
- Create: `apps/api/tests/test_session_material_ai.py`：作业、测试、代码集合和错误场景的纯服务测试。
- Modify: `apps/api/app/models.py`：为 `SessionMaterial` 增加 `generation_method`。
- Modify: `apps/api/app/db.py`：为现有 SQLite 数据库补充材料生成方式列。
- Modify: `apps/api/app/schemas.py`：在材料读取结果中暴露生成方式。
- Modify: `apps/api/app/routes/tasks.py`：把材料生成端点切换到已启用模型。
- Modify: `apps/api/tests/test_session_workspace_api.py`：覆盖模型配置、成功保存和失败不落库。
- Modify: `apps/web/src/types.ts`：增加 `generation_method` 类型。
- Modify: `apps/web/src/SessionWorkspacePage.tsx`：显示 AI 生成状态和来源。
- Modify: `apps/web/src/App.test.tsx`：覆盖新按钮文本、等待状态和错误保留。
- Modify: `README.md`：说明作业和测试已使用管理员启用的模型。

### Task 1：建立课次材料证据和校验服务

**Files:**
- Create: `apps/api/tests/test_session_material_ai.py`
- Create: `apps/api/app/services/session_material_ai.py`

- [ ] **Step 1：写作业和测试校验失败测试**

测试构造当前课次证据和假的 JSON 客户端，覆盖：作业成功、测试题量成功、未知能力代码失败、缺少提交要求失败、题量不符失败。

```python
def test_rejects_unknown_ability_code():
    payload = assignment_payload()
    payload["ability_codes"] = ["9-9-9"]
    with pytest.raises(SessionMaterialValidationError, match="9-9-9"):
        validate_session_material_payload(payload, evidence(material_type="assignment"))


def test_rejects_wrong_test_question_count():
    payload = test_payload(question_count=2)
    with pytest.raises(SessionMaterialValidationError, match="3"):
        validate_session_material_payload(payload, evidence(material_type="test", question_count=3))
```

- [ ] **Step 2：运行测试并确认缺少模块**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_session_material_ai.py -q`

Expected: FAIL，提示 `app.services.session_material_ai` 不存在。

- [ ] **Step 3：实现证据、Pydantic 输出结构和格式化**

`SessionMaterialEvidence` 包含课程、课次、教学内容、教案摘要、生成参数和严格允许的代码数组，并提供 `to_prompt_payload()`。实现以下公共接口：

```python
class SessionMaterialValidationError(ValueError):
    pass


def build_session_material_evidence(task, outline, lesson, request) -> SessionMaterialEvidence:
    return SessionMaterialEvidence(
        course_name=task.course_name,
        major=task.major,
        class_name=task.class_name,
        session_no=outline.session_no,
        topic=outline.topic,
        teaching_content=outline.teaching_content,
        lesson_context=_lesson_context(lesson),
        material_type=request.material_type,
        difficulty=request.difficulty,
        estimated_minutes=request.estimated_minutes,
        question_count=request.question_count,
        course_goal_codes=_codes(outline.course_goal_codes),
        ability_codes=_codes(outline.ability_codes),
    )


def validate_session_material_payload(
    payload: dict,
    evidence: SessionMaterialEvidence,
) -> GeneratedSessionMaterial:
    parsed = _parse_payload(payload, evidence.material_type)
    _require_exact_codes(parsed.course_goal_codes, evidence.course_goal_codes, "课程目标")
    _require_exact_codes(parsed.ability_codes, evidence.ability_codes, "能力指标")
    return _format_material(parsed, evidence)
```

作业模型包含 `title`、`task_requirements`、`submission_requirements`、`reference_points`、`grading_criteria` 和两组代码。测试模型包含 `title`、`questions` 和两组代码；每道题包含 `number`、`question`、`points`、`answer`、`grading_notes`，且 `points > 0`。

- [ ] **Step 4：实现统一 AI 调用入口**

```python
SYSTEM_PROMPT = """你是高职院校教师备课助手。只能使用输入证据，不得新增课程目标或能力指标代码。返回一个 JSON 对象。"""


def generate_ai_session_material(config, task, outline, lesson, request, client_factory=OpenAICompatibleClient):
    evidence = build_session_material_evidence(task, outline, lesson, request)
    payload = client_factory(config).generate_json(SYSTEM_PROMPT, evidence.to_prompt_payload())
    return validate_session_material_payload(payload, evidence)
```

- [ ] **Step 5：运行服务测试**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_session_material_ai.py -q`

Expected: PASS。

- [ ] **Step 6：提交服务层**

```bash
git add apps/api/app/services/session_material_ai.py apps/api/tests/test_session_material_ai.py
git commit -m "feat: validate ai session materials"
```

### Task 2：接入材料生成 API 和持久化来源

**Files:**
- Modify: `apps/api/app/models.py`
- Modify: `apps/api/app/db.py`
- Modify: `apps/api/app/schemas.py`
- Modify: `apps/api/app/routes/tasks.py`
- Modify: `apps/api/tests/test_session_workspace_api.py`

- [ ] **Step 1：写接口失败测试**

新增测试断言：未启用模型返回 409；模型超时返回 502；校验失败返回 422；三种失败均不会新增材料；成功时 `generation_method == "ai"` 并保留既有材料。

```python
def test_ai_validation_failure_does_not_save_material(prepared_course, monkeypatch):
    monkeypatch.setattr(
        "app.routes.tasks.generate_ai_session_material",
        lambda *args, **kwargs: (_ for _ in ()).throw(SessionMaterialValidationError("题量必须为 3")),
    )
    response = client.post(endpoint, json=test_request())
    assert response.status_code == 422
    assert client.get(workspace_url).json()["materials"] == []
```

- [ ] **Step 2：运行接口测试并确认失败**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_session_workspace_api.py -q`

Expected: FAIL，当前端点仍调用规则生成器且响应缺少 `generation_method`。

- [ ] **Step 3：增加数据库字段和兼容迁移**

模型增加：

```python
generation_method: str = "rule"
```

`init_db()` 调用 `_ensure_session_material_ai_columns()`，仅对 SQLite 执行：

```python
if "generation_method" not in columns:
    connection.exec_driver_sql(
        "ALTER TABLE sessionmaterial ADD COLUMN generation_method TEXT NOT NULL DEFAULT 'rule'"
    )
```

`SessionMaterialRead` 同步增加 `generation_method: str`。

- [ ] **Step 4：把生成端点切换到 AI 服务**

端点先查询 `enabled == True` 且 `connection_status == "connected"` 的配置；没有配置返回 409。调用服务后写入 `generation_method="ai"`。

```python
try:
    generated = generate_ai_session_material(config, task, outline, lesson, payload)
except SessionMaterialValidationError as exc:
    raise HTTPException(status_code=422, detail=str(exc)) from exc
except ModelProviderError as exc:
    raise HTTPException(status_code=502, detail="AI 生成失败，请稍后重试") from exc
```

异常发生在 `session.add(material)` 之前，保证失败不会落库。

- [ ] **Step 5：运行接口和后端全量测试**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_session_workspace_api.py tests/test_session_material_ai.py -q`

Expected: PASS。

Run: `cd apps/api && .venv/Scripts/python -m pytest -q`

Expected: 全部 PASS。

- [ ] **Step 6：提交 API**

```bash
git add apps/api/app/models.py apps/api/app/db.py apps/api/app/schemas.py apps/api/app/routes/tasks.py apps/api/tests/test_session_workspace_api.py
git commit -m "feat: generate session materials with ai"
```

### Task 3：接入前端生成状态和来源

**Files:**
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/SessionWorkspacePage.tsx`
- Modify: `apps/web/src/App.test.tsx`

- [ ] **Step 1：写前端失败测试**

断言按钮显示“AI 生成作业/测试”；请求进行中显示“AI 生成中”并禁用；成功材料显示“AI 生成”；接口失败后原材料和参数仍存在。

```typescript
await user.click(screen.getByRole("button", { name: "AI 生成测试" }));
expect(screen.getByRole("button", { name: "AI 生成中" })).toBeDisabled();
expect(await screen.findByText("AI 生成")).toBeInTheDocument();
```

- [ ] **Step 2：运行前端测试并确认失败**

Run: `cd apps/web && npm test -- --run src/App.test.tsx`

Expected: FAIL，当前按钮仍显示“生成测试”且类型中没有生成方式。

- [ ] **Step 3：更新类型与页面**

`SessionMaterial` 增加：

```typescript
generation_method: "rule" | "ai";
```

生成按钮使用现有 `busy` 状态：

```tsx
<button className="btn primary" disabled={busy} onClick={generateMaterial}>
  <Sparkles className="icon" />
  {busy ? "AI 生成中" : `AI 生成${materialType === "assignment" ? "作业" : "测试"}`}
</button>
```

材料列表在原有依据状态旁显示 `generation_method === "ai" ? "AI 生成" : "规则草稿"`。失败处理继续使用 `onError`，不得清空 `materials`、`selectedMaterial` 或生成参数。

- [ ] **Step 4：运行前端测试和生产构建**

Run: `cd apps/web && npm test -- --run`

Expected: 全部 PASS。

Run: `cd apps/web && $env:VITE_BASE_PATH='/design/'; $env:VITE_API_BASE_URL='/design/api'; npm run build`

Expected: PASS，产物路径以 `/design/` 为基础路径。

- [ ] **Step 5：提交前端**

```bash
git add apps/web/src/types.ts apps/web/src/SessionWorkspacePage.tsx apps/web/src/App.test.tsx
git commit -m "feat: show ai material generation state"
```

### Task 4：文档、真实 DeepSeek 验证与部署

**Files:**
- Modify: `README.md`

- [ ] **Step 1：更新 MVP 说明**

将单次课材料描述改为：作业与测试使用管理员启用的模型生成，服务端严格校验当前课次的课程目标和能力代码，教师确认后编辑和导出。

- [ ] **Step 2：执行本地全量验证**

Run: `cd apps/api && .venv/Scripts/python -m pytest -q`

Expected: 全部 PASS。

Run: `cd apps/web && npm test -- --run`

Expected: 全部 PASS。

Run: `cd apps/web && $env:VITE_BASE_PATH='/design/'; $env:VITE_API_BASE_URL='/design/api'; npm run build`

Expected: PASS。

- [ ] **Step 3：提交文档并推送分支**

```bash
git add README.md
git commit -m "docs: describe ai session materials"
git push origin codex/mvp-outline-export-pr
```

- [ ] **Step 4：备份并部署**

备份 `/opt/teaching-design-system` 中本次涉及的后端文件、前端目录和 `/var/lib/teaching-design-system/teaching_design.db`。更新后端文件与前端 `dist`，仅重启 `teaching-design.service`，不得修改或重启 `teacher-achievement.service`。

- [ ] **Step 5：执行线上数据库迁移和健康检查**

服务启动时由 `init_db()` 自动增加 `generation_method`。确认：

```text
teaching-design.service = active
teacher-achievement.service = active
GET /design/ = 200
GET /design/api/health = 200
sessionmaterial.generation_method 存在
```

- [ ] **Step 6：使用已启用 DeepSeek 做一次真实材料生成**

选择测试课程中的一个课次生成一份测试，确认：返回成功、题量一致、课程目标和能力代码未变化、材料可编辑和导出。测试材料保留给教师检查，除非明确标记为测试数据。
