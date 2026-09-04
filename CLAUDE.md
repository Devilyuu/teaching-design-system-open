# CLAUDE.md

面向在本仓库里工作的 AI 助手。人类读者请先看 [README.md](README.md)，
要把系统适配到自己学校请看 [docs/ADAPTING.md](docs/ADAPTING.md)。

## 这是什么

面向高职教师的备课文档生成系统。把**课程标准、人才培养方案、教务课表、学校 Word 模板**
组织成可追溯的生成依据，产出格式保真的课程实施大纲、教案、作业和试卷。

它不是「教学设计版 ChatGPT」。**它比直接问 AI 要一份教案强的地方，全在下面那几条硬约束
上**——改动时优先保住它们。

## 四条硬约束

违反其中任何一条的改动都是错的，即使测试通过、即使用户要求「先跑通再说」。

1. **代码不许编造。** 生成内容引用的课程目标代码（`M1`）和能力指标代码（`1-3-4`）
   只能来自已解析的课程标准和人才培养方案。校验在
   `services/ai_lesson_validator.py` 和 `services/source_validation.py`。
   **对不上就中止，不做降级、不做「尽力而为」。**

2. **事实性内容照抄，不经模型。** 大纲第五节（教材、教辅、参考书目、平台网址）和
   第六节（考核方式与比例）只允许从课程标准原样搬运，见
   `services/course_standard_resources.py` 和 `course_standard_assessment.py`。
   模型编的书名和网址毫无破绽却查无此物；考核比例是教务要对的账。
   课程标准里没有的，写「课程标准中未提供，请教师补充」，不许模型生成一条。

3. **导出前回头比对。** `lesson_template_filler.find_unfilled_generated_cells()`
   比对模板与成品，**还有 `C00000` 红字格没填就中止导出**。不交半成品。

4. **不认识的模板不硬导。** 模板既没有 `{{教案正文}}` 占位符、又认不出教案表格结构时，
   返回明确的校验错误，**不要退化成往文档里追加一段纯文本**。

还有一条前置闸门：**课程标准引用的每个能力指标都必须在人才培养方案里找到、且经教师确认
对应关系之后**，才允许生成课程实施大纲。

## 架构

```
apps/api/    FastAPI + SQLModel，约 9000 行
apps/web/    React + TypeScript + Vite，约 5800 行
templates/   脱敏示例模板（真实模板由教师按课程上传）
docs/        需求、设计、部署、适配文档
```

后端分层清楚，逻辑几乎都在 `app/services/`，路由只做编排：

| 目录 | 职责 |
|---|---|
| `app/routes/` | HTTP 编排；业务逻辑不写在这里 |
| `app/services/*_parser.py` | 解析学校材料（课程标准、人才培养方案、课表） |
| `app/services/ai_*.py` | 组装证据、调模型、校验返回 |
| `app/services/*_template_filler.py` | 按学校 Word 模板逐格填充，保留原样式 |
| `app/services/*_exporter.py` | 导出 docx |
| `app/models.py` | 全部数据表，单文件 |

**数据库是配置而非构建。** `DATABASE_URL` 同时支持 `sqlite:///`（单人安装）和
`postgresql://`（多人共用，走 `postgres` 附加依赖）。别引入只在其中一种上能跑的写法。

**模型接入是 OpenAI 兼容的 HTTP 调用**（`services/openai_compatible.py`），
不绑定任何厂商。base_url、model_name、api_key 由管理员在界面上配，api_key 用 Fernet
加密后入库（`services/secret_store.py`）。**任何日志和报错都不许带上 api_key**——
`openai_compatible.failure_reason()` 已经做了脱敏，新增错误路径要沿用它。

## 教师的工作流

代码组织跟着这条线走，读代码时按这个顺序看最省力：

```
建课程 → 传人才培养方案 + 课程标准 → 确认课程目标与能力指标对应关系
      → 导入教务课表 → 生成课程实施大纲 → 生成整门课教案
      → 逐课次调整、生成作业/试卷 → 导出 docx → 课后一分钟反思接入下一课
```

## 开发

```bash
cd apps/api && pytest              # 293 项，改后端必跑
cd apps/web && npm test -- --run   # 80 项
```

Windows 上前端构建用 PowerShell，不要用 Git Bash。

`apps/api/scripts/real_generation_check.py` 是唯一会真调模型的检查：自动化测试全是 mock，
说明不了生成内容能不能用。它需要 `--materials` 指向一份真实材料目录，
仓库不附带任何学校材料。

## 写代码的口味

跟着现有代码走，这几点在本仓库里是一致的：

- **注释解释「为什么」，不解释「做了什么」。** 现有注释大多在说某个决定背后的权衡
  （为什么不给默认密码、为什么这一节不过模型），照这个来。
- 报错要能指导下一步动作。`操作失败` 这种没有信息量的文案不要写。
- 面向教师的文案用中文，代码标识符和注释用英文——注释里出现的教务术语除外。
- 不为「以后可能有用」提前抽象。

## 这个仓库是公开的

- **不要提交任何真实学校材料**：课程标准、人才培养方案、课表、教案、学生信息。
  `.gitignore` 已经挡了 `cankao/`、`*.docx`、`*.pdf`、`uploads/`、`*.db`
  （例外：`templates/*.docx` 是脱敏示例，需要入库）。
- **不要在源码里写任何默认密钥或默认口令。** `APP_SECRET_KEY` 未设置时按进程随机生成，
  初始管理员密码未设置时随机生成并只打印一次——这是刻意的，别为了方便改回固定值。
- 测试数据用中性化名（张明 / 张老师），不要写真实教师、班级、校区名。
- 提交 docx 前先清 `docProps/core.xml` 的作者信息和 WPS 的账号追踪属性。
