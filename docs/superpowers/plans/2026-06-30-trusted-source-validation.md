# 可信资料校验闭环实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让教师在生成课程实施大纲前，上传并核对人才培养方案与课程标准中的目标和能力指标，确认无误后才允许生成。

**Architecture:** 新增确定性人才培养方案解析器，将权威指标按任务保存；独立的资料校验服务负责把课程目标引用代码与指标库交叉匹配。API 提供上传、查看校验、确认三个动作，并用确认记录作为实施大纲生成门禁；前端把原来的“一键上传并生成”拆成“解析检查”和“确认生成”两步。

**Tech Stack:** FastAPI、SQLModel、python-docx、pytest、React 19、TypeScript、Vitest、Testing Library

---

## Task 1：人才培养方案指标解析器

**Files:**
- Create: `apps/api/app/services/talent_plan_parser.py`
- Create: `apps/api/tests/test_talent_plan_parser.py`

- [ ] **Step 1：写入表定位和指标拆分的失败测试**

测试用 `python-docx` 创建两个表：第一个是干扰表；第二个表在首行之前放一行标题，其表头包含 `培养规格代码`、`TOP10`、`其他`。数据覆盖同一单元格多个代码、十位序号 `1-1-10`、代码后无空格、知识点/能力点/素养点三种类别。

```python
def test_parse_authoritative_indicator_table_without_fixed_table_index(tmp_path):
    path = tmp_path / "talent-plan.docx"
    make_talent_plan_docx(path)

    result = parse_talent_plan(path)

    assert [item.code for item in result.indicators] == [
        "1-3-4", "1-3-10", "2-3-4", "3-2-1"
    ]
    assert result.indicators[0].category == "知识点"
    assert result.indicators[0].group_code == "1-3"
    assert result.indicators[0].description == "探究基础动画关键帧的制作方法"
    assert result.indicators[1].description == "总结渲染输出的方法"
```

- [ ] **Step 2：运行测试并确认因模块不存在而失败**

Run: `apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_talent_plan_parser.py -q`

Expected: FAIL，提示 `app.services.talent_plan_parser` 不存在。

- [ ] **Step 3：实现最小确定性解析器**

实现以下公开类型和函数：

```python
@dataclass(frozen=True)
class ParsedAbilityIndicator:
    code: str
    category: str
    group_code: str
    description: str

@dataclass(frozen=True)
class ParsedTalentPlan:
    indicators: list[ParsedAbilityIndicator]

def parse_talent_plan(path: Path | str) -> ParsedTalentPlan:
    ...
```

定位规则：遍历所有表和表内所有行，找到同时包含 `培养规格代码` 与 `TOP10` 的行；其后仅接受第二列符合 `\d+-\d+` 的数据行。使用 `(?<![\d-])(\d+-\d+-\d+)(?![\d-])` 找出每个三级代码，并将当前代码末尾到下一个代码开头之间的文本作为描述。按文档顺序返回，重复代码只保留第一次出现的记录。

- [ ] **Step 4：运行解析器测试并确认通过**

Run: `apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_talent_plan_parser.py -q`

Expected: PASS。

- [ ] **Step 5：提交解析器**

```powershell
git add apps/api/app/services/talent_plan_parser.py apps/api/tests/test_talent_plan_parser.py
git commit -m "feat: parse talent plan indicators"
```

## Task 2：资料持久化、交叉校验和生成门禁

**Files:**
- Create: `apps/api/app/services/source_validation.py`
- Modify: `apps/api/app/models.py`
- Modify: `apps/api/app/schemas.py`
- Modify: `apps/api/app/routes/tasks.py`
- Modify: `apps/api/tests/test_outline_workflow_api.py`
- Create: `apps/api/tests/test_source_validation.py`

- [ ] **Step 1：写入纯校验服务的失败测试**

服务接口固定为：

```python
def build_source_review(
    goals: Sequence[CourseGoal],
    indicators: Sequence[AbilityIndicator],
    confirmed: bool,
) -> SourceReviewData:
    ...
```

测试一个完全匹配场景和一个未知代码场景：

```python
assert review.can_confirm is True
assert review.unknown_codes == []
assert review.goals[0].indicators[0].description == "探究基础动画关键帧的制作方法"

assert invalid.can_confirm is False
assert invalid.unknown_codes == ["9-9-9"]
assert invalid.goals[0].unknown_codes == ["9-9-9"]
```

- [ ] **Step 2：运行测试并确认因服务和模型不存在而失败**

Run: `apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_source_validation.py -q`

Expected: FAIL，提示缺少 `AbilityIndicator` 或 `build_source_review`。

- [ ] **Step 3：新增数据模型和纯校验服务**

在 `models.py` 新增：

```python
class AbilityIndicator(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(index=True)
    code: str = Field(index=True)
    category: str
    group_code: str
    description: str

class SourceConfirmation(SQLModel, table=True):
    task_id: int = Field(primary_key=True)
    confirmed_by_id: int
    confirmed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

`source_validation.py` 定义不可变的 `IndicatorReviewData`、`GoalReviewData`、`SourceReviewData`，按课程目标顺序构建匹配结果；`can_confirm` 仅在目标非空、指标非空且未知代码为空时为真。

- [ ] **Step 4：运行纯服务测试并确认通过**

Run: `apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_source_validation.py -q`

Expected: PASS。

- [ ] **Step 5：写入 API 失败测试**

在工作流测试中新增人才培养方案 fixture 和以下行为断言：

```python
response = client.post(f"/tasks/{task_id}/outline/generate")
assert response.status_code == 400
assert "confirm" in response.json()["detail"].lower()

review = client.get(f"/tasks/{task_id}/sources/review").json()
assert review["indicators_count"] == 3
assert review["unknown_codes"] == []
assert review["can_confirm"] is True

response = client.post(f"/tasks/{task_id}/sources/confirm")
assert response.status_code == 200
assert response.json()["confirmed"] is True

response = client.post(f"/tasks/{task_id}/outline/generate")
assert response.status_code == 200
```

另加未知代码阻止确认、重新上传课程标准使确认失效、任务列表返回 `talent_plan_uploaded` 与 `sources_confirmed` 的测试。

- [ ] **Step 6：运行 API 测试并确认缺少端点和门禁而失败**

Run: `apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_outline_workflow_api.py -q`

Expected: FAIL，人才培养方案和资料确认端点为 404，或未确认生成错误地返回 200。

- [ ] **Step 7：实现 API、响应模型和确认失效规则**

新增响应类型：

```python
class AbilityIndicatorRead(BaseModel):
    code: str
    category: str
    group_code: str
    description: str

class CourseGoalReviewRead(BaseModel):
    code: str
    description: str
    ability_codes: list[str]
    indicators: list[AbilityIndicatorRead]
    unknown_codes: list[str]

class SourceReviewRead(BaseModel):
    task_id: int
    goals: list[CourseGoalReviewRead]
    indicators_count: int
    unknown_codes: list[str]
    can_confirm: bool
    confirmed: bool
```

实现 `POST /talent-plan`、`GET /sources/review`、`POST /sources/confirm`。人才培养方案或课程标准解析为空时先返回 400，不覆盖旧数据；成功替换后删除 `SourceConfirmation`。`outline/generate` 在读取目标和课表之前检查确认记录。`TeachingTaskRead` 和 `_task_read` 增加两个布尔字段。

- [ ] **Step 8：更新所有旧工作流测试的公共准备流程**

所有需要生成大纲的测试都先上传一个可匹配的人才培养方案并调用确认端点。不要在应用中为旧任务设置隐式确认，也不要绕过门禁。

- [ ] **Step 9：运行后端全量测试**

Run: `apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests -q`

Expected: 全部 PASS。

- [ ] **Step 10：提交后端可信资料闭环**

```powershell
git add apps/api/app/models.py apps/api/app/schemas.py apps/api/app/routes/tasks.py apps/api/app/services/source_validation.py apps/api/tests/test_source_validation.py apps/api/tests/test_outline_workflow_api.py
git commit -m "feat: require confirmed course sources"
```

## Task 3：前端资料检查与教师确认流程

**Files:**
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/api.ts`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/App.test.tsx`
- Modify: `apps/web/src/styles.css`

- [ ] **Step 1：把现有生成流程测试改为两阶段失败测试**

测试 mock 增加 `/talent-plan`、`/sources/review`、`/sources/confirm`。用户选择五类文件后，先点击“解析并检查课程依据”，断言页面显示 `M1`、`1-3-4` 和指标原文，并断言尚未请求 `/outline/generate`；再点击“确认并生成课程实施大纲”，断言依次请求确认和生成端点。

```typescript
expect(screen.getByText("探究基础动画关键帧的制作方法")).toBeInTheDocument();
expect(calledUrls).not.toContain("http://localhost:8000/tasks/2/outline/generate");
await user.click(screen.getByRole("button", { name: "确认并生成课程实施大纲" }));
expect(calledUrls).toContain("http://localhost:8000/tasks/2/sources/confirm");
expect(calledUrls).toContain("http://localhost:8000/tasks/2/outline/generate");
```

再加一个未知代码场景，断言确认按钮禁用并显示“必须修正”。

- [ ] **Step 2：运行前端测试并确认失败**

Run: `npm test -- --run`

Workdir: `apps/web`

Expected: FAIL，页面缺少人才培养方案、校验结果和两阶段按钮。

- [ ] **Step 3：新增前端类型与 API 客户端**

`types.ts` 增加与后端响应一致的 `AbilityIndicatorReview`、`CourseGoalReview`、`SourceReview`，并给任务增加 `talent_plan_uploaded?: boolean`、`sources_confirmed?: boolean`。

`api.ts` 增加：

```typescript
export function uploadTalentPlan(taskId: number, file: File): Promise<ParseSummary>;
export function getSourceReview(taskId: number): Promise<SourceReview>;
export function confirmSources(taskId: number): Promise<SourceReview>;
```

`ParseSummary` 增加 `indicators_count`。

- [ ] **Step 4：实现两阶段交互**

`MaterialKey` 增加 `talentPlan`。新增 `sourceReview` 状态；更换人才培养方案或课程标准时清空它。

`handleReviewSources` 只负责确保任务存在、上传两份依据文件并读取 review。`handleConfirmAndGenerate` 要求 `sourceReview.can_confirm`、课表和实施大纲模板存在，然后确认依据、上传课表和模板、生成大纲。教案模板保持可选。

页面将上传列表与校验结果按纵向主流程排列，校验结果使用全宽区域。每个课程目标显示描述、指标代码、类别和指标原文；未知代码使用现有错误色并标注“必须修正”。

- [ ] **Step 5：补充稳定尺寸和窄屏样式**

为 `.source-review`、`.source-goal-review`、`.indicator-review-row` 增加简洁表格式样；桌面端充分占用内容宽度，`760px` 以下改为单列。不得新增装饰插画、统计图或嵌套卡片。

- [ ] **Step 6：运行前端测试和生产构建**

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

- [ ] **Step 7：提交前端确认流程**

```powershell
git add apps/web/src/types.ts apps/web/src/api.ts apps/web/src/App.tsx apps/web/src/App.test.tsx apps/web/src/styles.css
git commit -m "feat: add source review confirmation flow"
```

## Task 4：真实样本、回归、线上部署

**Files:**
- Modify: `README.md`

- [ ] **Step 1：使用真实样本文档执行解析验收**

通过临时脚本读取 `cankao` 目录中的真实人才培养方案和课程标准，不复制或提交学校文档。断言：

```text
indicators=136
goals=4
referenced_codes=9
unknown_codes=0
```

- [ ] **Step 2：运行全量回归**

```powershell
apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests -q
cd apps/web
npm test -- --run
$env:VITE_BASE_PATH='/design/'
$env:VITE_API_BASE_URL='/design/api'
npm run build
Remove-Item Env:\VITE_BASE_PATH
Remove-Item Env:\VITE_API_BASE_URL
```

Expected: 后端、前端测试和生产构建全部通过。

- [ ] **Step 3：更新 README 的当前核心流程**

在当前范围中明确：人才培养方案与课程标准先解析、交叉校验并由教师确认，随后才能生成课程实施大纲和整门课教案；产品仍然是教师端工具，不含学生提交。

- [ ] **Step 4：提交文档**

```powershell
git add README.md
git commit -m "docs: describe trusted source workflow"
```

- [ ] **Step 5：部署到腾讯云独立路径**

沿用现有结构更新 `/opt/teaching-design-system` 和 `/var/www/teaching-design-system/design`，重启 `teaching-design.service`。不得修改 `teacher-achievement.service` 或根路径站点。

- [ ] **Step 6：部署后健康检查**

```powershell
ssh -i "$env:USERPROFILE\.ssh\teacher_achievement_tencent_ed25519" ubuntu@124.221.239.254 "systemctl is-active teaching-design.service; systemctl is-active teacher-achievement.service; curl -s -o /dev/null -w 'design=%{http_code}\n' http://127.0.0.1/design/; curl -s -o /dev/null -w 'api=%{http_code}\n' http://127.0.0.1:8002/health; curl -s -o /dev/null -w 'root=%{http_code}\n' http://127.0.0.1/"
```

Expected: 两个服务均为 `active`，`design=200`，`api=200`，根路径仍为 `200` 或 `303`。

## 完成标准

- 人才培养方案指标由确定性解析器提取，不由 AI 编造。
- 教师能逐项查看课程目标、引用代码和指标原文。
- 未知代码与未确认状态都会阻止生成。
- 重新上传依据文件会使确认失效。
- 原有实施大纲编辑、整门课教案和 Word 导出流程保持可用。
- 真实样本与自动化测试均通过，线上教学设计系统和原成果管理系统互不影响。
