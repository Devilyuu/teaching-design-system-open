# 智能备课文档生成系统

面向高职院校教师的备课文档生成系统。把**课程标准、人才培养方案、教务课表和学校 Word
模板**组织成可追溯的生成依据，产出格式保真的课程实施大纲、教案、作业和试卷。

导出的是能直接交上去的 `.docx`——套用你们学校自己的模板，保留原有表格和样式。

---

## 先说清楚三件事

**一、这不是开箱即用的软件。**
代码里有若干处按某一所学校的教务格式写死了：能力指标代码长什么样、教案模板的表头叫什么、
教务课表怎么导出。换一所学校，多半会卡在解析环节。
**动手前请先读 [docs/ADAPTING.md](docs/ADAPTING.md)**，它列清了所有需要调整的地方，
并附了一段可以直接丢给 Claude 或 Codex 的提示词。

**二、仓库里没有任何真实教学材料。**
课程标准、人才培养方案、课表都是各校自己的东西，一律不入库。`templates/` 下那份模板是
**脱敏示例**，只用来说明代码依赖的结构约定，不是任何学校的正式模板。

**三、它的价值在「不许编造」，不在「生成得快」。**
如果只想要一份教案，直接问 AI 更快。这套系统多出来的部分是几道拦截：AI 引用的课程目标
代码和能力指标代码必须在你上传的材料里真实存在，教材书目和考核比例只许照抄课程标准不许
生成，导出前回头比对模板、还有空格就中止。**改功能时别顺手把这几道闸门拆了。**

---

## 它能做什么

- **学期课程工作台**：下一次课、待备课项、课程整体进度放在一起
- **材料解析**：人才培养方案、课程标准、教务课表（xlsx/xls）
- **依据确认**：教师逐条确认课程目标与能力指标的对应关系——确认完才允许生成
- **课程实施大纲生成**：按课次拆解整门课程
- **整门课教案生成**：可逐课次编辑，生成过程可中断、可单项重试
- **课次备课工作区**：调整教案、生成作业和试卷
- **课后一分钟反思**：教师确认后的调整自动接进下一次课的教案
- **格式保真导出**：优先用占位符；没有占位符就认出学校模板里的表格逐格填，样式和结构不动

系统只管教师这一侧的备课，学生提交仍留在学校现有教学平台。

---

## 快速开始

需要 Python 3.10+ 和 Node.js 18+。

```bash
cp .env.example .env
```

留空即可先跑起来——首次启动会创建管理员账号，密码随机生成并在启动日志里打印一次，
登录后请立即修改。对外提供服务前，请按 `.env.example` 里的说明把安全相关的几项填上。

**后端**

```powershell
cd apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

**前端**

```powershell
cd apps/web
npm install
npm run dev
```

前端读 `VITE_API_BASE_URL`，默认 `http://localhost:8000`。

**跑测试**

```bash
cd apps/api && pytest
```

```bash
cd apps/web && npm test -- --run
```

后端 301 项、前端 88 项。改完代码跑一遍，这是你有没有改坏的判据。

---

## 给全系教师开账号

以管理员登录 → 标准库与账号管理 → 教师账号。两种方式：

- **批量导入**：从教务花名册复制「工号」「姓名」两列直接粘贴，一行一位，一次建完全系。
- **新增教师**：单个添加，可顺手绑定授课专业。

新账号的初始密码就是本人工号，首次登录系统会强制改成自己的密码，管理员不需要
逐个通知密码。已有账号的工号会被跳过，名单可以反复粘贴。老师忘记密码时，
在账号列表里把密码重置为工号即可；离职或调动的账号可以停用，课程资料保留。

每位教师只能看到自己建的课程，管理员能看到全部。

---

## 接入 AI 模型

系统走 **OpenAI 兼容接口**，不绑定厂商：DeepSeek、通义、Kimi、自建 vLLM 都行。

以管理员登录 → AI 模型配置 → 填 base_url、模型名、API Key → 测试连接。
Key 用 Fernet 加密后入库，界面上只回显掩码，日志和报错都做了脱敏。

加密密钥来自 `MODEL_CONFIG_ENCRYPTION_KEY`：

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**这把密钥一旦用于保存过模型配置就必须持续备份**，换掉之后已存的 Key 解不开，
需要重新填写。

---

## 部署

单人使用 SQLite 就够。多人共用推荐 docker compose（PostgreSQL）：

```bash
docker compose up -d --build
```

启动前必须在 compose 文件旁边的 `.env` 里设好 `POSTGRES_PASSWORD`、
`APP_SECRET_KEY` 和 `MODEL_CONFIG_ENCRYPTION_KEY`——**缺任何一项 compose 会直接拒绝启动**，
而不是退回到一个人人都知道的默认值。

默认对外端口 `8081`，方便和服务器上已有的系统共存。绑域名走 Nginx 反代时，
把 `.env` 里的 `WEB_HOST` 改成 `127.0.0.1`，别把端口直接暴露到公网。

用哪种数据库是配置不是构建：`DATABASE_URL` 同时接受 `sqlite:///...` 和
`postgresql://...`，后者需要 PostgreSQL 驱动（`pip install -e "./apps/api[postgres]"`），
裸的 `postgresql://` 会自动路由过去。

腾讯云轻量服务器的完整步骤见 [docs/deployment/tencent-lighthouse.md](docs/deployment/tencent-lighthouse.md)。

---

## 技术栈与代码地图

| | |
|---|---|
| 后端 | FastAPI + SQLModel，约 9000 行，`apps/api/` |
| 前端 | React + TypeScript + Vite，约 5800 行，`apps/web/` |
| 文档处理 | python-docx / openpyxl / xlrd |
| 数据库 | SQLite 或 PostgreSQL |

业务逻辑几乎都在 `apps/api/app/services/`，路由只做编排：

- `*_parser.py` — 解析学校材料
- `ai_*.py` — 组装证据、调模型、校验返回
- `*_template_filler.py` — 按学校 Word 模板逐格填充
- `*_exporter.py` — 导出 docx

其他文档：

- [CLAUDE.md](CLAUDE.md) — 给 AI 助手看的架构说明和硬约束
- [docs/ADAPTING.md](docs/ADAPTING.md) — 适配到你自己学校
- [templates/README.md](templates/README.md) — 模板的 `C00000` 红字契约
- [PRODUCT.md](PRODUCT.md) / [DESIGN.md](DESIGN.md) — 产品定位与设计系统
- `docs/superpowers/` — 各功能的需求与设计文档

---

## 关于隐私

系统在你自己的机器或服务器上跑，教学材料不出本地。唯一的外发是调用你自己配置的模型
接口——生成时会把课程标准、能力指标等相关内容作为上下文发给该模型服务商。

**上传涉及学生个人信息的材料前，请先确认你所配置的模型服务商的数据政策。**

---

## License

MIT，见 [LICENSE](LICENSE)。随便改、随便用。

如果你把它适配到了自己学校，欢迎回来提个 issue 说说卡在哪了——
[docs/ADAPTING.md](docs/ADAPTING.md) 的常见卡点表就是这么攒出来的。
