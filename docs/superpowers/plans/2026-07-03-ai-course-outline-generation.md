# AI 课程实施大纲生成实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从课程标准真实项目表、已核验代码和课表一次生成整门课课程实施大纲，并支持受控代码选择与单行字段候选优化。

**Architecture:** 课程标准上传时确定性提取并持久化教学项目；首次大纲生成时构建最小证据包，调用现有 OpenAI 兼容客户端并整批校验后事务写入。已有大纲禁止整表覆盖，单行优化使用独立候选记录，教师接受后才更新原行。

**Tech Stack:** FastAPI、SQLModel、Pydantic、python-docx、React、TypeScript、Vitest、DeepSeek OpenAI-compatible API

---

## 文件结构

- Modify: `apps/api/app/services/course_standard_parser.py`：提取课程目标和教学项目。
- Modify: `apps/api/tests/test_course_standard_parser.py`：覆盖项目行、描述行、合并单元格和参考学时。
- Modify: `apps/api/app/models.py`：增加 `CourseProject`、`OutlineRevisionCandidate` 和大纲更新时间。
- Modify: `apps/api/app/db.py`：为现有 SQLite 补充大纲更新时间列。
- Create: `apps/api/app/services/ai_outline_generation.py`：证据、AI 输出结构、整批校验和生成入口。
- Create: `apps/api/tests/test_ai_outline_generation.py`：覆盖行数、课次、项目、学时和代码关系。
- Create: `apps/api/app/services/outline_revision.py`：单行字段候选生成。
- Modify: `apps/api/app/schemas.py`：增加项目数、代码选项和候选接口类型。
- Modify: `apps/api/app/routes/tasks.py`：持久化项目、AI 首次生成、代码校验与候选接口。
- Modify: `apps/api/tests/test_outline_workflow_api.py`：覆盖接口事务和权限。
- Modify: `apps/web/src/types.ts`、`apps/web/src/api.ts`：新增代码选项与候选契约。
- Modify: `apps/web/src/App.tsx`：首次 AI 生成、多选代码和局部候选交互。
- Modify: `apps/web/src/App.test.tsx`、`apps/web/src/styles.css`：行为测试和紧凑表格样式。

### Task 1：解析并保存课程教学项目

**Files:**
- Modify: `apps/api/app/services/course_standard_parser.py`
- Modify: `apps/api/tests/test_course_standard_parser.py`
- Modify: `apps/api/app/models.py`
- Modify: `apps/api/app/schemas.py`
- Modify: `apps/api/app/routes/tasks.py`
- Modify: `apps/api/tests/test_outline_workflow_api.py`

- [ ] **Step 1：先写项目表解析失败测试**

构造包含“项目名称、教学内容、教学方法建议、教学目标、知识能力素养集、参考课时”的表格。每个项目后跟一个合并单元格“项目描述”行。

```python
result = parse_course_standard(path)
assert len(result.projects) == 2
assert result.projects[0].name == "项目一：工具探索"
assert result.projects[0].reference_hours == 8
assert result.projects[0].practice_hours == 4
assert result.projects[0].course_goal_codes == ["M1", "M2"]
assert result.projects[0].ability_codes == ["1-3-4", "2-3-4"]
assert "入门阶段" in result.projects[0].description
```

- [ ] **Step 2：运行解析测试确认失败**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_course_standard_parser.py -q`

Expected: FAIL，`ParsedCourseStandard` 尚无 `projects`。

- [ ] **Step 3：实现确定性项目解析**

增加：

```python
@dataclass(frozen=True)
class ParsedCourseProject:
    name: str
    description: str
    teaching_content: str
    suggested_methods: str
    course_goal_codes: list[str]
    ability_codes: list[str]
    reference_hours: int
    practice_hours: int
```

识别项目表头后，只把参考课时符合 `总学时/实践学时` 的行作为项目主行。相同项目名的下一行若包含“项目描述”，提取一次描述文本并合并到主项目。M 代码和三级能力代码在教学目标到能力列范围内分别正则提取并去重。

- [ ] **Step 4：写项目持久化接口测试**

课程标准上传成功后断言 `ParseSummary.projects_count == 2`，数据库中存在两条 `CourseProject`；重新上传时旧项目被替换且 `SourceConfirmation` 失效。

- [ ] **Step 5：增加模型并在上传路由保存项目**

```python
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
```

`ParseSummary` 增加 `projects_count: int = 0`。上传路由在同一事务中替换 `CourseGoal` 和 `CourseProject`。

- [ ] **Step 6：运行目标测试并提交**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_course_standard_parser.py tests/test_outline_workflow_api.py -q`

Expected: PASS。

```bash
git add apps/api/app/services/course_standard_parser.py apps/api/tests/test_course_standard_parser.py apps/api/app/models.py apps/api/app/schemas.py apps/api/app/routes/tasks.py apps/api/tests/test_outline_workflow_api.py
git commit -m "feat: extract course standard projects"
```

### Task 2：建立整门课 AI 大纲证据与校验

**Files:**
- Create: `apps/api/app/services/ai_outline_generation.py`
- Create: `apps/api/tests/test_ai_outline_generation.py`

- [ ] **Step 1：写整批校验失败测试**

覆盖正确 8 行、行数错误、课次重复、空字段、未知目标、目标与能力关系错误、项目未覆盖和总学时不一致。

```python
with pytest.raises(OutlineValidationError, match="课次数量"):
    validate_outline_payload(payload_with_rows(7), evidence_for_sessions(8))

with pytest.raises(OutlineValidationError, match="2-3-6"):
    validate_outline_payload(payload_with_unknown_ability(), evidence_for_sessions(8))
```

- [ ] **Step 2：运行测试确认模块缺失**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_ai_outline_generation.py -q`

Expected: FAIL，模块不存在。

- [ ] **Step 3：实现证据和 Pydantic 输出结构**

```python
@dataclass(frozen=True)
class OutlineEvidence:
    course_name: str
    total_hours: int
    hours_per_session: int
    projects: list[dict]
    goals: dict[str, dict]
    sessions: list[dict]

    def to_prompt_payload(self) -> dict:
        return asdict(self)
```

`AiOutlineRow` 包含 `session_no`、`project_name` 和九个可编辑字段。`AiOutlinePayload` 包含 `rows`。

- [ ] **Step 4：实现严格校验和课表合并**

```python
def validate_outline_payload(payload: dict, evidence: OutlineEvidence) -> list[GeneratedOutlineRow]:
    parsed = AiOutlinePayload.model_validate(payload)
    _validate_session_numbers(parsed.rows, len(evidence.sessions))
    _validate_project_coverage(parsed.rows, evidence.projects)
    _validate_goal_ability_pairs(parsed.rows, evidence.goals)
    return [_merge_schedule(row, evidence.sessions[row.session_no - 1]) for row in parsed.rows]
```

证据构建前校验 `sum(session.hours) == task.total_hours`，否则抛出 `OutlineEvidenceError`。

- [ ] **Step 5：实现 AI 调用入口并运行测试**

```python
def generate_ai_outline(config, evidence, client_factory=OpenAICompatibleClient):
    payload = client_factory(config).generate_json(SYSTEM_PROMPT, evidence.to_prompt_payload())
    return validate_outline_payload(payload, evidence)
```

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_ai_outline_generation.py -q`

Expected: PASS。

- [ ] **Step 6：提交服务层**

```bash
git add apps/api/app/services/ai_outline_generation.py apps/api/tests/test_ai_outline_generation.py
git commit -m "feat: validate ai course outlines"
```

### Task 3：将首次大纲生成接口切换到 AI

**Files:**
- Modify: `apps/api/app/routes/tasks.py`
- Modify: `apps/api/tests/test_outline_workflow_api.py`

- [ ] **Step 1：写接口失败测试**

断言未启用模型返回 409、没有教学项目返回 409、总学时不一致返回 422、模型和校验失败不写入、成功一次写入全部课次、已有大纲再次生成返回 409。

```python
response = client.post(f"/tasks/{task_id}/outline/generate")
assert response.status_code == 200
assert len(response.json()) == 8
second = client.post(f"/tasks/{task_id}/outline/generate")
assert second.status_code == 409
```

- [ ] **Step 2：运行接口测试确认旧规则行为失败**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_outline_workflow_api.py -q`

Expected: 新增测试 FAIL，当前路由仍调用规则生成器并允许覆盖。

- [ ] **Step 3：实现事务化 AI 生成路由**

路由读取已启用且已连接的 `AiModelConfig`、`CourseProject`、`CourseGoal`、`AbilityIndicator` 和 `ScheduleSessionRecord`。若已存在 `OutlineRow` 立即返回 409。调用服务成功后才批量 `session.add()` 并提交。

错误映射：配置和项目缺失为 409，证据错误和结构校验为 422，供应商错误为 502。

- [ ] **Step 4：运行后端全量测试并提交**

Run: `cd apps/api && .venv/Scripts/python -m pytest -q`

Expected: 全部 PASS。

```bash
git add apps/api/app/routes/tasks.py apps/api/tests/test_outline_workflow_api.py
git commit -m "feat: generate course outlines with ai"
```

### Task 4：约束代码编辑并增加单行候选

**Files:**
- Modify: `apps/api/app/models.py`
- Modify: `apps/api/app/db.py`
- Modify: `apps/api/app/schemas.py`
- Create: `apps/api/app/services/outline_revision.py`
- Modify: `apps/api/app/routes/tasks.py`
- Modify: `apps/api/tests/test_outline_workflow_api.py`

- [ ] **Step 1：写保存校验和候选失败测试**

覆盖自由输入未知目标、错误能力关系、候选生成、接受、拒绝，以及候选生成后原行已修改时禁止接受。

- [ ] **Step 2：运行测试确认接口缺失**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_outline_workflow_api.py -q`

Expected: 新候选接口 404，未知代码仍可保存。

- [ ] **Step 3：增加更新时间和候选模型**

`OutlineRow` 增加 `updated_at`，SQLite 启动迁移补列。新增：

```python
class OutlineRevisionCandidate(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(index=True)
    outline_row_id: int = Field(index=True)
    field_name: str
    original_content: str
    proposed_content: str
    source_updated_at: datetime
    status: str = "pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 4：实现代码关系校验**

`PUT /outline/{row_id}` 保存前解析目标与能力代码。目标必须存在；每个能力代码必须属于至少一个已选目标并存在于已核验指标中。失败返回 422，原行不修改。

- [ ] **Step 5：实现候选服务和接口**

支持字段：`topic`、`teaching_content`、`teaching_methods`、`tasks`、`all`。候选生成输入只含当前行、相邻行和允许代码。接受时比较 `source_updated_at`；不一致返回 409。`tasks` 和 `all` 使用 JSON 内容承载多个字段，接受时一次更新。

- [ ] **Step 6：运行测试并提交**

Run: `cd apps/api && .venv/Scripts/python -m pytest -q`

Expected: 全部 PASS。

```bash
git add apps/api/app/models.py apps/api/app/db.py apps/api/app/schemas.py apps/api/app/services/outline_revision.py apps/api/app/routes/tasks.py apps/api/tests/test_outline_workflow_api.py
git commit -m "feat: review outline row revisions"
```

### Task 5：接入前端多选与局部优化

**Files:**
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/api.ts`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/App.test.tsx`
- Modify: `apps/web/src/styles.css`

- [ ] **Step 1：写前端失败测试**

断言首次按钮为“AI 生成课程实施大纲”；已有表格不显示全表重新生成；目标和能力用复选控件；错误关系无法保存；单行候选可生成、采用和放弃。

- [ ] **Step 2：运行测试确认失败**

Run: `cd apps/web && npm test -- --run src/App.test.tsx`

Expected: FAIL，当前仍有“重新生成”和自由文本代码输入。

- [ ] **Step 3：增加前端契约和 API**

增加 `OutlineRevisionCandidate` 及创建、接受、拒绝方法。复用 `SourceReview.goals` 作为目标与能力选项，不新增重复选项接口。

- [ ] **Step 4：改造大纲表格**

移除已有表格的全表重新生成按钮。代码单元格显示紧凑复选菜单；能力选项由当前所选目标的 `indicators` 合并得出。若取消目标导致现有能力失效，保留当前值并显示错误，直到教师重新选择。

每行增加“AI 优化”菜单；候选在行下方展开，明确显示原内容和建议内容，教师选择采用或放弃。

- [ ] **Step 5：运行前端测试和生产构建**

Run: `cd apps/web && npm test -- --run`

Expected: 全部 PASS。

Run: `cd apps/web && $env:VITE_BASE_PATH='/design/'; $env:VITE_API_BASE_URL='/design/api'; npm run build`

Expected: PASS。

- [ ] **Step 6：提交前端**

```bash
git add apps/web/src/types.ts apps/web/src/api.ts apps/web/src/App.tsx apps/web/src/App.test.tsx apps/web/src/styles.css
git commit -m "feat: edit and refine ai course outlines"
```

### Task 6：真实案例验证与部署

- [ ] **Step 1：运行本地全量验证**

Run: `cd apps/api && .venv/Scripts/python -m pytest -q`

Run: `cd apps/web && npm test -- --run`

Run: `cd apps/web && $env:VITE_BASE_PATH='/design/'; $env:VITE_API_BASE_URL='/design/api'; npm run build`

Expected: 三项均成功。

- [ ] **Step 2：使用案例文档执行解析验证**

解析《人工智能与创意设计》课程标准，确认得到 3 个项目、参考总学时 32、实践学时 16，且项目目标和能力代码均在已核验集合内。

- [ ] **Step 3：提交并推送**

```bash
git push origin codex/mvp-outline-export-pr
```

- [ ] **Step 4：备份并部署**

备份涉及的后端文件、前端目录和数据库。只更新教学设计系统并重启 `teaching-design.service`，不得修改或重启 `teacher-achievement.service`。

- [ ] **Step 5：线上真实生成验证**

使用已启用 DeepSeek 和现有案例课程执行不落库整门课生成，确认课次数量、项目覆盖、目标能力代码和课表日期全部通过校验。随后检查公网 200、两套服务 active 和数据库新增结构。
