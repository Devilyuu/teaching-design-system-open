# 混合式教案模板填充实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变学校 Word 教案模板结构的前提下，将整门课教案逐课次填入模板原有表格，并在模板不可识别时拒绝生成。

**Architecture:** 保留占位符替换作为第一优先级；新增独立的课次区块识别与填充服务，按信息表和过程表的表头定位区块。路由层补充实施大纲上下文并将模板识别错误转换为 400 响应。

**Tech Stack:** Python、python-docx、FastAPI、pytest、LibreOffice 渲染

---

### Task 1：识别真实教案课次区块

**Files:**
- Create: `apps/api/app/services/lesson_template_filler.py`
- Create: `apps/api/tests/test_lesson_template_filler.py`

- [ ] 先写失败测试：合成两个课次信息表和两个过程表，断言识别两个区块；缺少关键表头时返回空列表。
- [ ] 运行 `apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/test_lesson_template_filler.py -q`，确认因模块不存在失败。
- [ ] 实现 `LessonTemplateBlock` 和 `find_lesson_template_blocks(document)`，只使用表头语义定位，不依赖固定表序号。
- [ ] 运行目标测试并确认通过。

### Task 2：原位填充信息表和过程表

**Files:**
- Modify: `apps/api/app/services/lesson_template_filler.py`
- Modify: `apps/api/tests/test_lesson_template_filler.py`

- [ ] 先写失败测试：填充两份教案后断言标题、学时、班级、时间、地点、教学目标、课程目标、能力代码和课后任务进入各自区块。
- [ ] 测试记录填充前后的表格数、行列数和合并单元格 XML，断言结构不变。
- [ ] 实现 `fill_structured_lesson_template(document, lessons, contexts, common_values)`；按标签拆分教学过程，无法拆分时只填第一条课中行。
- [ ] 增加区块不足和模板不可识别的 `LessonTemplateError` 测试与实现。
- [ ] 运行目标测试并确认通过。

### Task 3：接入现有教案导出

**Files:**
- Modify: `apps/api/app/services/docx_exporter.py`
- Modify: `apps/api/app/routes/tasks.py`
- Modify: `apps/api/tests/test_docx_exporter.py`
- Modify: `apps/api/tests/test_outline_workflow_api.py`

- [ ] 先写失败测试：无 `{{教案正文}}` 的结构化模板必须原位填充，不得新增“教案正文”尾部段落。
- [ ] 写 API 失败测试：不可识别模板返回 400；结构化模板导出成功。
- [ ] 修改 `fill_lesson_docx`：占位符存在时替换，否则调用结构填充器；删除末尾追加纯文本回退。
- [ ] 路由读取每份教案对应的 `OutlineRow`，构建周次、星期、节次和地点上下文；捕获 `LessonTemplateError` 返回 400。
- [ ] 运行后端全量测试。

### Task 4：真实模板与部署验收

**Files:**
- Modify: `README.md`

- [ ] 使用真实 `人工智能与创意设计_完整版教案.docx` 识别 8 个课次区块并生成测试输出。
- [ ] 对比导出前后表格数量、行列、合并关系、节属性、页眉页脚和媒体文件数量。
- [ ] 使用 Documents skill 的 `render_docx.py` 渲染全部页面并逐页检查。
- [ ] 运行后端和前端全量测试、前端生产构建。
- [ ] 更新 README，提交并推送分支。
- [ ] 备份线上数据库和应用文件，增量部署后验证两个 systemd 服务及 `/design/`、API、根路径。

