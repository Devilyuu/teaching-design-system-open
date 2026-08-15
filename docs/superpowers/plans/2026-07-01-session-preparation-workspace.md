# 单次课备课工作台实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立可持久化的单次课工作台，使教师能够查看课次依据、修改本次教案、生成并编辑作业或测试，并导出独立 Word。

**Architecture:** 保留 `TeachingTask`、`OutlineRow` 和 `LessonPlan` 作为课程、课次和教案边界，新增独立 `SessionMaterial` 表保存课次材料。后端将规则生成、Word 导出和路由分别放入独立模块；前端新增独立 `SessionWorkspacePage`，由课程工作台维护当前课次选择，避免继续扩大 `App.tsx`。

**Tech Stack:** FastAPI、SQLModel、Pydantic、python-docx、React、TypeScript、Vitest、Testing Library、Vite。

---

## 文件结构

- Create: `apps/api/app/services/session_material_generator.py`：纯函数生成作业和测试内容。
- Create: `apps/api/app/services/session_material_exporter.py`：将单份材料导出为独立 Word。
- Create: `apps/api/tests/test_session_material_generator.py`：规则生成器单元测试。
- Create: `apps/api/tests/test_session_material_exporter.py`：Word 内容测试。
- Create: `apps/api/tests/test_session_workspace_api.py`：课次详情、权限、材料 CRUD 和导出测试。
- Modify: `apps/api/app/models.py`：新增 `SessionMaterial` 表。
- Modify: `apps/api/app/schemas.py`：新增课次工作台和材料读写模型。
- Modify: `apps/api/app/routes/tasks.py`：新增课次详情和材料接口。
- Create: `apps/web/src/SessionWorkspacePage.tsx`：独立的单次课工作台组件。
- Modify: `apps/web/src/types.ts`：新增课次工作台和材料类型。
- Modify: `apps/web/src/api.ts`：新增课次详情、材料 CRUD 和导出方法。
- Modify: `apps/web/src/App.tsx`：把课次选择接入独立工作台，移除静态 `AssessmentPage`。
- Modify: `apps/web/src/App.test.tsx`：覆盖完整课次备课用户路径。
- Modify: `apps/web/src/styles.css`：放大编辑区并完成窄屏适配。
- Modify: `README.md`：补充单次课备课闭环能力。

### Task 1：建立课次材料模型与生成器

**Files:**
- Create: `apps/api/tests/test_session_material_generator.py`
- Create: `apps/api/app/services/session_material_generator.py`
- Modify: `apps/api/app/models.py`
- Modify: `apps/api/app/schemas.py`

- [ ] **Step 1：先写规则生成失败测试**

测试使用简单对象构造大纲和教案，分别断言作业与测试继承已有目标代码，且无教案时标记为 `outline_only`：

```python
from types import SimpleNamespace

from app.services.session_material_generator import generate_session_material


def make_outline():
    return SimpleNamespace(
        topic="AIGC 与创意设计导入",
        teaching_content="理解 AIGC 基础并完成案例拆解",
        post_task="提交案例分析记录",
        course_goal_codes="M1",
        ability_codes="1-3-4",
    )


def test_generates_assignment_from_outline_and_lesson():
    lesson = SimpleNamespace(
        teaching_goals="理解 AIGC 基础",
        key_points="案例拆解",
        homework="提交调研记录",
    )
    result = generate_session_material(make_outline(), lesson, "assignment", "medium", 40, 5)
    assert result.material_type == "assignment"
    assert result.source_status == "outline_and_lesson"
    assert result.course_goal_codes == "M1"
    assert result.ability_codes == "1-3-4"
    assert "提交" in result.content
    assert result.reference_answer
    assert result.grading_criteria


def test_generates_numbered_test_without_lesson():
    result = generate_session_material(make_outline(), None, "test", "basic", 20, 3)
    assert result.source_status == "outline_only"
    assert result.content.count("题") >= 3
    assert result.course_goal_codes == "M1"
    assert result.ability_codes == "1-3-4"
```

- [ ] **Step 2：运行测试并确认因模块不存在而失败**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_session_material_generator.py -q`

Expected: FAIL，提示 `app.services.session_material_generator` 不存在。

- [ ] **Step 3：实现最小规则生成器**

新增不可变结果对象和单一入口：

```python
from dataclasses import dataclass
from typing import Literal


MaterialType = Literal["assignment", "test"]


@dataclass(frozen=True)
class GeneratedSessionMaterial:
    material_type: MaterialType
    title: str
    content: str
    reference_answer: str
    grading_criteria: str
    difficulty: str
    estimated_minutes: int
    course_goal_codes: str
    ability_codes: str
    source_status: str


def generate_session_material(outline, lesson, material_type, difficulty, estimated_minutes, question_count):
    source_status = "outline_and_lesson" if lesson is not None else "outline_only"
    if material_type == "assignment":
        task = (getattr(lesson, "homework", "") if lesson else "") or outline.post_task or outline.teaching_content
        return GeneratedSessionMaterial(
            material_type="assignment",
            title=f"{outline.topic}实践作业",
            content=f"围绕“{outline.topic}”完成以下任务：{task}",
            reference_answer=f"成果应能体现：{outline.teaching_content}",
            grading_criteria="任务完成度 40 分；方法运用 30 分；成果表达 20 分；规范性 10 分。",
            difficulty=difficulty,
            estimated_minutes=estimated_minutes,
            course_goal_codes=outline.course_goal_codes,
            ability_codes=outline.ability_codes,
            source_status=source_status,
        )
    questions = "\n".join(f"第 {index} 题：结合本次课内容说明{outline.topic}的关键要点。" for index in range(1, question_count + 1))
    return GeneratedSessionMaterial(
        material_type="test",
        title=f"{outline.topic}课堂测试",
        content=questions,
        reference_answer=f"答案应覆盖：{outline.teaching_content}",
        grading_criteria=f"共 {question_count} 题，按要点完整性、准确性和表达规范评分。",
        difficulty=difficulty,
        estimated_minutes=estimated_minutes,
        course_goal_codes=outline.course_goal_codes,
        ability_codes=outline.ability_codes,
        source_status=source_status,
    )
```

生成器校验 `material_type`、正整数用时和测试题量；无效输入抛出 `ValueError`。

- [ ] **Step 4：新增持久化模型与 Pydantic 模型**

在 `models.py` 新增 `SessionMaterial`，字段与设计规格一致，`created_at` 和 `updated_at` 使用 UTC。`schemas.py` 新增：

```python
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
    created_at: datetime
    updated_at: datetime


class SessionMaterialUpdate(BaseModel):
    title: str
    content: str
    reference_answer: str
    grading_criteria: str
    difficulty: Literal["basic", "medium", "advanced"]
    estimated_minutes: int = Field(gt=0, le=600)


class SessionWorkspaceRead(BaseModel):
    outline: OutlineRowRead
    lesson: LessonPlanRead | None
    materials: list[SessionMaterialRead]
```

- [ ] **Step 5：运行生成器测试和模型建表检查**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_session_material_generator.py -q`

Expected: PASS。

- [ ] **Step 6：提交模型与生成器**

```bash
git add apps/api/app/models.py apps/api/app/schemas.py apps/api/app/services/session_material_generator.py apps/api/tests/test_session_material_generator.py
git commit -m "feat: add session material model and generator"
```

### Task 2：实现课次详情与材料增删改接口

**Files:**
- Create: `apps/api/tests/test_session_workspace_api.py`
- Modify: `apps/api/app/routes/tasks.py`

- [ ] **Step 1：写课次详情和生成接口失败测试**

复用 `test_outline_workflow_api.py` 的文档、课表和课程创建帮助函数，在独立测试文件中建立已生成大纲和教案的课程。断言：

```python
def test_session_workspace_returns_outline_lesson_and_materials(prepared_course):
    client, task_id, outline_row_id = prepared_course
    response = client.get(f"/tasks/{task_id}/sessions/{outline_row_id}")
    assert response.status_code == 200
    assert response.json()["outline"]["id"] == outline_row_id
    assert response.json()["lesson"]["outline_row_id"] == outline_row_id
    assert response.json()["materials"] == []


def test_generating_material_preserves_existing_materials(prepared_course):
    client, task_id, outline_row_id = prepared_course
    endpoint = f"/tasks/{task_id}/sessions/{outline_row_id}/materials/generate"
    first = client.post(endpoint, json={"material_type": "assignment", "difficulty": "medium", "estimated_minutes": 40, "question_count": 5})
    second = client.post(endpoint, json={"material_type": "test", "difficulty": "basic", "estimated_minutes": 20, "question_count": 3})
    assert first.status_code == 200
    assert second.status_code == 200
    workspace = client.get(f"/tasks/{task_id}/sessions/{outline_row_id}").json()
    assert [item["material_type"] for item in workspace["materials"]] == ["assignment", "test"]
```

- [ ] **Step 2：运行测试并确认端点返回 404/405**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_session_workspace_api.py -q`

Expected: FAIL，课次工作台端点尚不存在。

- [ ] **Step 3：实现课次归属帮助函数和两个读取/生成端点**

`tasks.py` 新增 `_get_outline_row_or_404(task_id, outline_row_id, session)`，必须同时匹配 ID 和 `task_id`。读取端点查询同一 `outline_row_id` 的教案及按创建时间排序的材料；生成端点先调用 `_get_task_or_404()`，再调用纯生成器并保存 `owner_user_id=current_user.id`。

- [ ] **Step 4：写编辑、删除和越权失败测试**

测试以下行为：

- 更新标题、内容、答案、评分标准、难度和用时后可重新读取。
- 删除返回 204，刷新课次详情后材料消失。
- 用教师 B 的 token 读取教师 A 的课程、更新或删除其材料均返回 404。
- 使用属于同一教师另一门课程的 `outline_row_id` 返回 404。

- [ ] **Step 5：运行测试并确认 CRUD 端点缺失**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_session_workspace_api.py -q`

Expected: 新增 CRUD 测试 FAIL，已有详情和生成测试 PASS。

- [ ] **Step 6：实现更新与删除接口**

更新前同时校验课程权限、材料 `task_id` 和材料存在；设置 `updated_at=datetime.now(timezone.utc)`。删除成功返回 `Response(status_code=204)`，不存在或不属于课程统一返回 404。

- [ ] **Step 7：运行目标测试与后端全量测试**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_session_workspace_api.py -q`

Expected: PASS。

Run: `cd apps/api && .venv/Scripts/python -m pytest -q`

Expected: 全部 PASS。

- [ ] **Step 8：提交材料 API**

```bash
git add apps/api/app/routes/tasks.py apps/api/tests/test_session_workspace_api.py
git commit -m "feat: add session workspace material api"
```

### Task 3：实现单份材料 Word 导出

**Files:**
- Create: `apps/api/app/services/session_material_exporter.py`
- Create: `apps/api/tests/test_session_material_exporter.py`
- Modify: `apps/api/app/routes/tasks.py`
- Modify: `apps/api/tests/test_session_workspace_api.py`

- [ ] **Step 1：写 Word 导出失败测试**

```python
from docx import Document

from app.services.session_material_exporter import export_session_material_docx


def test_exports_material_context_answer_and_codes(tmp_path):
    output = tmp_path / "material.docx"
    export_session_material_docx(output, task, outline, material)
    document = Document(output)
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "人工智能与创意设计" in text
    assert "第 1 次课" in text
    assert "参考答案" in text
    assert "评分标准" in text
    assert "M1" in text
    assert "1-3-4" in text
```

- [ ] **Step 2：运行测试并确认导出模块不存在**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_session_material_exporter.py -q`

Expected: FAIL，提示导出模块不存在。

- [ ] **Step 3：实现简洁的系统内置 Word 格式**

使用 `Document()` 创建标题、课程信息表和“材料内容 / 参考答案 / 评分标准 / 关联依据”四个段落区块。函数只接收输出路径、课程、课次和材料，不访问数据库。

- [ ] **Step 4：新增导出 API 测试与实现**

测试 `POST /tasks/{task_id}/materials/{material_id}/export` 返回 DOCX 媒体类型和 UTF-8 文件名；下载后用 `python-docx` 读取并断言课程、课次、答案、评分标准及能力代码存在。路由使用临时文件生成字节响应，并在 `finally` 删除临时文件。

- [ ] **Step 5：运行导出测试与后端全量测试**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_session_material_exporter.py tests/test_session_workspace_api.py -q`

Expected: PASS。

Run: `cd apps/api && .venv/Scripts/python -m pytest -q`

Expected: 全部 PASS。

- [ ] **Step 6：提交材料导出**

```bash
git add apps/api/app/services/session_material_exporter.py apps/api/app/routes/tasks.py apps/api/tests/test_session_material_exporter.py apps/api/tests/test_session_workspace_api.py
git commit -m "feat: export session materials to word"
```

### Task 4：接入前端类型和 API

**Files:**
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/api.ts`
- Modify: `apps/web/src/App.test.tsx`

- [ ] **Step 1：在前端测试 mock 中增加课次数据**

新增 `sessionWorkspace` fixture，包含 `outlineRows[0]`、`lessonPlans[0]` 和一份作业材料；mock 以下 URL：

- `GET /tasks/1/sessions/11`
- `POST /tasks/1/sessions/11/materials/generate`
- `PUT /tasks/1/materials/31`
- `DELETE /tasks/1/materials/31`
- `POST /tasks/1/materials/31/export`

- [ ] **Step 2：新增 TypeScript 类型**

在 `types.ts` 新增：

```typescript
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
  created_at: string;
  updated_at: string;
}

export interface SessionWorkspace {
  outline: OutlineRow;
  lesson: LessonPlan | null;
  materials: SessionMaterial[];
}

export interface SessionMaterialGenerateInput {
  material_type: SessionMaterialType;
  difficulty: SessionMaterialDifficulty;
  estimated_minutes: number;
  question_count: number;
}
```

- [ ] **Step 3：新增 API 方法**

实现 `getSessionWorkspace`、`generateSessionMaterial`、`updateSessionMaterial`、`deleteSessionMaterial` 和 `exportSessionMaterial`。导出复用现有 blob、`Content-Disposition` 和 token 处理模式，默认文件名为 `备课材料.docx`。

- [ ] **Step 4：运行现有测试和 TypeScript 构建确认 API 契约正确**

Run: `cd apps/web && npm test -- --run`

Expected: 现有测试全部 PASS。

Run: `cd apps/web && npm run build`

Expected: PASS。

- [ ] **Step 5：提交前端数据边界**

```bash
git add apps/web/src/types.ts apps/web/src/api.ts apps/web/src/App.test.tsx
git commit -m "feat: add session workspace frontend api"
```

### Task 5：实现单次课工作台页面

**Files:**
- Create: `apps/web/src/SessionWorkspacePage.tsx`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/App.test.tsx`
- Modify: `apps/web/src/styles.css`

- [ ] **Step 1：补齐完整用户流程失败测试**

测试以下真实行为：

1. 从“我的课程 → 进入课程 → 课次与材料 → 进入本次课”，显示大纲依据和已有教案，并出现“本次课概况”“本次教案”“备课材料”。
2. 修改“教学重点”并点击“保存本次教案”，断言调用现有教案更新 URL。
3. 选择“测试”、题量 3、用时 20 分钟并点击“生成测试”，断言调用生成 URL 和正确 JSON。
4. 修改生成材料标题并点击“保存材料”，断言调用材料更新 URL。
5. 点击“导出 Word”，断言调用单份材料导出 URL。
6. 点击“删除材料”确认后，材料从列表消失并调用 DELETE。
7. 没有教案时显示“未引用教案”，但仍允许生成材料。
8. 课程目标或能力指标为空时，点击导出先显示确认提示；教师确认后才请求导出接口。

- [ ] **Step 2：运行测试并确认页面行为缺失**

Run: `cd apps/web && npm test -- --run src/App.test.tsx`

Expected: 新增课次工作台测试 FAIL。

- [ ] **Step 3：建立独立页面组件**

`SessionWorkspacePage` 接收：

```typescript
interface SessionWorkspacePageProps {
  task: TeachingTask;
  outlineRowId: number;
  onBack: () => void;
  onNotice: (message: string) => void;
  onError: (message: string) => void;
}
```

组件负责加载课次详情并维护教案、材料列表、当前材料和生成参数。页面包含：返回按钮、本次课概况、本次教案、材料列表、生成参数和材料编辑器。材料列表显示类型、标题、难度、预计用时、更新时间和“已引用教案 / 未引用教案”。所有输入都使用受控状态；保存成功后用接口返回值替换本地对象。

- [ ] **Step 4：替换 App 中的静态 AssessmentPage**

在 `App` 新增 `selectedOutlineRowId`。`CourseSessionsPage` 的每行只保留“进入本次课”，点击后设置课次 ID；有选中课次时在“课次与材料”页签渲染 `SessionWorkspacePage`，返回时清空课次 ID。删除原 `AssessmentPage` 和 `assessmentRowId` 局部状态。

- [ ] **Step 5：实现材料下载和删除确认**

导出成功后创建临时链接下载并释放 URL。课程目标或能力指标为空时先调用 `window.confirm("当前材料缺少课程目标或能力指标代码，仍要导出吗？")`；取消时不得请求导出接口。删除使用 `window.confirm("确定删除这份备课材料吗？")`，取消时不得请求 API。

- [ ] **Step 6：增加编辑区优先的响应式样式**

桌面使用 `grid-template-columns: 260px minmax(0, 1fr)`；材料编辑器占主列。1120px 以下改为单列，760px 以下生成参数和操作按钮纵向排列。对 390px 宽度增加测试，断言课次标题、返回按钮、材料类型切换和保存按钮仍存在。

- [ ] **Step 7：运行前端全量测试和生产构建**

Run: `cd apps/web && npm test -- --run`

Expected: 全部 PASS。

Run: `cd apps/web && $env:VITE_BASE_PATH='/design/'; $env:VITE_API_BASE_URL='/design/api'; npm run build`

Expected: PASS，产物路径使用 `/design/`。

- [ ] **Step 8：提交单次课页面**

```bash
git add apps/web/src/SessionWorkspacePage.tsx apps/web/src/App.tsx apps/web/src/App.test.tsx apps/web/src/styles.css
git commit -m "feat: add session preparation workspace"
```

### Task 6：端到端验收、文档与部署

**Files:**
- Modify: `README.md`

- [ ] **Step 1：更新 README**

在 MVP 范围中补充：单次课教案编辑、作业和测试持久化、独立 Word 导出。明确学生提交仍在学校平台完成。

- [ ] **Step 2：运行全量验证**

Run: `cd apps/api && .venv/Scripts/python -m pytest -q`

Expected: 全部 PASS。

Run: `cd apps/web && npm test -- --run`

Expected: 全部 PASS。

Run: `cd apps/web && $env:VITE_BASE_PATH='/design/'; $env:VITE_API_BASE_URL='/design/api'; npm run build`

Expected: PASS。

- [ ] **Step 3：本地浏览器验收**

以管理员和普通教师分别验证：

- 进入课程和某次课。
- 修改并保存教案。
- 生成作业和测试，刷新后内容仍存在。
- 编辑、导出和删除材料。
- 1440×900、1024×768、390×844 无页面级横向溢出。
- 浏览器控制台无 error 或 warning。

- [ ] **Step 4：提交文档并推送分支**

```bash
git add README.md
git commit -m "docs: describe session preparation workflow"
git push origin codex/mvp-outline-export-pr
```

- [ ] **Step 5：部署到腾讯云并保留回滚点**

备份 `/opt/teaching-design-system` 中本次涉及的后端文件、`/var/www/teaching-design-system/design` 和 `/var/lib/teaching-design-system/teaching_design.db`。只重启 `teaching-design.service`，不修改或重启 `teacher-achievement.service`。

- [ ] **Step 6：验证公网服务**

确认：

- `http://124.221.239.254/design/` 返回 200。
- `http://124.221.239.254/design/api/health` 返回 `{"status":"ok"}`。
- OpenAPI 包含课次材料接口和 `SessionMaterialRead`。
- 线上静态 JS 与本地构建 SHA-256 一致。
- `teaching-design.service` 和 `teacher-achievement.service` 均为 active。
- 根路径成果管理系统仍返回原有响应。
