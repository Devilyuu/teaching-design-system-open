# 小红书 Vibe Coding 作品发布包 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 产出一套可直接发布的小红书素材，包括 8 张 1200×1600 PNG 图卡、自然真诚的发布文案和逐图脱敏检查记录。

**Architecture:** 在新的 `social/xiaohongshu-2026-08-15-v2/` 目录中保留独立素材包，不覆盖第一版。图卡由一个单页 HTML 按 `?card=1..8` 渲染，Playwright 脚本负责尺寸、溢出检查和 PNG 导出；Markdown 文件承载可直接复制的正文与发布顺序。

**Tech Stack:** HTML/CSS/JavaScript、Node.js、Playwright、PNG、Markdown。

---

## 文件结构

- `social/xiaohongshu-2026-08-15-v2/cards.html`：8 页内容数据、统一视觉变量和逐页布局。
- `social/xiaohongshu-2026-08-15-v2/render-cards.mjs`：无服务器渲染、溢出检查和 PNG 导出。
- `social/xiaohongshu-2026-08-15-v2/小红书发布文案.md`：标题、正文、标签、评论引导、置顶评论和配图顺序。
- `social/xiaohongshu-2026-08-15-v2/素材脱敏检查.md`：7 张原始截图与 8 张成品图卡的检查结果。
- `social/xiaohongshu-2026-08-15-v2/*-raw.png`：从第一版复制的脱敏原始截图。
- `social/xiaohongshu-2026-08-15-v2/card-*.png`：最终 8 张图卡。

### Task 1: 建立独立素材包并复核截图来源

**Files:**
- Create: `social/xiaohongshu-2026-08-15-v2/素材脱敏检查.md`
- Copy: `social/xiaohongshu-2026-08-15/*-raw.png`

- [ ] **Step 1: 创建新版目录并复制 7 张原始截图**

Run:

```powershell
New-Item -ItemType Directory -Force -Path "social/xiaohongshu-2026-08-15-v2"
Copy-Item -LiteralPath "social/xiaohongshu-2026-08-15/01-dashboard-raw.png" -Destination "social/xiaohongshu-2026-08-15-v2/01-dashboard-raw.png"
Copy-Item -LiteralPath "social/xiaohongshu-2026-08-15/02-course-overview-raw.png" -Destination "social/xiaohongshu-2026-08-15-v2/02-course-overview-raw.png"
Copy-Item -LiteralPath "social/xiaohongshu-2026-08-15/03-materials-raw.png" -Destination "social/xiaohongshu-2026-08-15-v2/03-materials-raw.png"
Copy-Item -LiteralPath "social/xiaohongshu-2026-08-15/04-outline-raw.png" -Destination "social/xiaohongshu-2026-08-15-v2/04-outline-raw.png"
Copy-Item -LiteralPath "social/xiaohongshu-2026-08-15/05-lessons-raw.png" -Destination "social/xiaohongshu-2026-08-15-v2/05-lessons-raw.png"
Copy-Item -LiteralPath "social/xiaohongshu-2026-08-15/06-session-raw.png" -Destination "social/xiaohongshu-2026-08-15-v2/06-session-raw.png"
Copy-Item -LiteralPath "social/xiaohongshu-2026-08-15/07-reflection-raw.png" -Destination "social/xiaohongshu-2026-08-15-v2/07-reflection-raw.png"
```

Expected: 新目录中出现 7 张与第一版字节一致的 PNG，第一版文件未修改。

- [ ] **Step 2: 逐张检查原始截图**

使用图像查看工具以原始分辨率检查姓名、学校、课程、账号、API Key、内网地址、服务器地址和本机绝对路径。发现可识别信息时，停止使用该图并在 HTML 中改用安全截图；不得通过模糊到不可读的方式掩盖问题。

- [ ] **Step 3: 写入脱敏检查记录**

记录每个文件的检查状态、可见演示信息和处理决定。文档必须明确写出“未发现真实身份、学校、账号、密钥或服务器信息”或具体替换措施，不能只写“已脱敏”。

### Task 2: 重写可直接发布的正文

**Files:**
- Create: `social/xiaohongshu-2026-08-15-v2/小红书发布文案.md`
- Reference: `README.md`
- Reference: `PRODUCT.md`

- [ ] **Step 1: 写 5 个标题**

标题围绕以下五个角度各写一个：高校教师身份、备课痛点、Vibe Coding、AI 不乱编、GitHub 开源。主标题使用“备课最费时间的事，我做成系统了”，其余标题不得使用“神器”“秒杀”“彻底解放”等夸张词。

- [ ] **Step 2: 写第一人称正文**

正文按以下顺序落稿：

1. `👩‍🏫` 自我介绍：高校教师，也是 Vibe Coding 爱好者。
2. `💭` 真实动机：资料查找、依据核对、课次拆分和 Word 套模板比“写教案”更耗时。
3. `🔍` 核心原则：课程目标、能力指标、教材和考核比例必须来自教师提供的材料，依据不足就提示补充。
4. `🧩` 主要功能：资料管理、整门课规划、逐课教案、单次课作业测试、课后反思和模板导出。
5. `⚠️` 已知限制：不同学校的课标、课表和 Word 模板需要针对性适配。
6. `🌱` 开源邀请：公开仓库使用脱敏示例，邀请教师试用、提 Issue 和反馈真实卡点。

每段 1 至 3 句；每个图标只出现一次；正文保持教师之间交流的语气，不写成项目 README。

- [ ] **Step 3: 补齐发布辅助文本**

添加 8 至 10 个相关标签、一条以“你们学校备课时最卡的是哪一步？”为核心的评论引导，以及一条说明 GitHub 地址和适配限制的置顶评论。

- [ ] **Step 4: 对照项目资料核实功能**

Run:

```powershell
rg -n "学期课程工作台|材料解析|依据确认|课程实施大纲生成|整门课教案生成|课次备课工作区|课后一分钟反思|格式保真导出" README.md
```

Expected: 8 项功能均在 README 的“它能做什么”部分出现；正文不新增未经证实的能力。

### Task 3: 制作 B 方案的 8 页图卡

**Files:**
- Create: `social/xiaohongshu-2026-08-15-v2/cards.html`

- [ ] **Step 1: 建立统一视觉变量**

在 `cards.html` 中固定 `1200px × 1600px` 画布，使用 `#F3F0E8` 米白背景、`#242824` 主文字、`#59645F` 次文字、`#2F6B59` 墨绿强调和 `#FFFFFF` 内容卡片。圆角保持 8 至 14 像素，阴影轻微，标题不小于 58 像素，正文不小于 25 像素。

- [ ] **Step 2: 建立可复用页面组件**

HTML 模板必须包含身份栏、页码、图标、主标题、副标题、一个主要信息结构、截图容器和统一页脚。页面数据通过长度为 8 的 `cards` 数组提供，URL 参数 `card` 选择对应页面；无效参数回退到第 1 页。

- [ ] **Step 3: 实现 8 页内容和节奏变化**

按设计说明实现封面、痛点清单、依据流程、课程规划、教案生成、单次课工作区、课后反思和开源邀请。封面以标题和局部截图为主；痛点页使用四项清单；功能页分别使用截图标注、流程线或双栏卡片；结尾页减少信息密度并突出共建邀请。

- [ ] **Step 4: 控制图标与截图使用**

每页最多一个主图标，使用 `👩‍🏫 📚 🧩 ✍️ 🔍 💬` 中与内容对应的符号。每页最多一张真实截图，截图区域标注“演示数据已脱敏”；不添加随机贴纸、彩虹渐变、蓝紫霓虹或无意义装饰。

### Task 4: 自动渲染并检查尺寸与溢出

**Files:**
- Create: `social/xiaohongshu-2026-08-15-v2/render-cards.mjs`
- Create: `social/xiaohongshu-2026-08-15-v2/card-01-cover.png`
- Create: `social/xiaohongshu-2026-08-15-v2/card-02-pain.png`
- Create: `social/xiaohongshu-2026-08-15-v2/card-03-evidence.png`
- Create: `social/xiaohongshu-2026-08-15-v2/card-04-outline.png`
- Create: `social/xiaohongshu-2026-08-15-v2/card-05-lessons.png`
- Create: `social/xiaohongshu-2026-08-15-v2/card-06-session.png`
- Create: `social/xiaohongshu-2026-08-15-v2/card-07-reflection.png`
- Create: `social/xiaohongshu-2026-08-15-v2/card-08-open-source.png`

- [ ] **Step 1: 编写无服务器 Playwright 渲染器**

使用 `pathToFileURL(path.join(outputDir, "cards.html"))` 打开页面，每页建立 `1200×1600` viewport。截图前等待 `document.fonts.ready` 和所有图片 `complete`；检查 `.card` 的 `scrollWidth <= 1200`、`scrollHeight <= 1600`，不满足时抛错并停止导出。

- [ ] **Step 2: 渲染 8 张 PNG**

Run:

```powershell
node "social/xiaohongshu-2026-08-15-v2/render-cards.mjs"
```

Expected: 控制台依次输出 8 个 `rendered card-*.png`，进程退出码为 0。

- [ ] **Step 3: 验证文件数量和尺寸**

Run:

```powershell
$files = Get-ChildItem -LiteralPath "social/xiaohongshu-2026-08-15-v2" -Filter "card-*.png"
if ($files.Count -ne 8) { throw "expected 8 cards, got $($files.Count)" }
Add-Type -AssemblyName System.Drawing
foreach ($file in $files) {
  $image = [System.Drawing.Image]::FromFile($file.FullName)
  try { if ($image.Width -ne 1200 -or $image.Height -ne 1600) { throw "$($file.Name) has invalid dimensions" } }
  finally { $image.Dispose() }
}
```

Expected: 命令无错误退出，8 张图片均为 1200×1600。

### Task 5: 视觉、隐私与交付验收

**Files:**
- Modify: `social/xiaohongshu-2026-08-15-v2/素材脱敏检查.md`
- Verify: `social/xiaohongshu-2026-08-15-v2/card-*.png`
- Verify: `social/xiaohongshu-2026-08-15-v2/小红书发布文案.md`

- [ ] **Step 1: 逐张查看最终图片**

以原始分辨率检查 8 张图卡，确认标题可读、正文没有裁切、截图内容清晰、页面构图有变化、页码连续，并排除 PPT 感和廉价模板感。

- [ ] **Step 2: 完成最终脱敏记录**

对 8 张成品再次检查姓名、学校、课程、账号、密钥、路径和服务器信息，在 `素材脱敏检查.md` 中逐项记录。若任何一项可疑，回到 Task 3 替换素材并重新执行 Task 4。

- [ ] **Step 3: 检查发布包完整性**

Run:

```powershell
Get-ChildItem -LiteralPath "social/xiaohongshu-2026-08-15-v2" | Sort-Object Name | Select-Object Name,Length
git status --short
```

Expected: 新目录包含 7 张原始截图、8 张图卡、HTML、渲染器、发布文案和脱敏记录；第一版目录保持不变。

- [ ] **Step 4: 提交新版发布包**

Run:

```powershell
git add -- "social/xiaohongshu-2026-08-15-v2"
git commit -m "docs: add Xiaohongshu Vibe Coding showcase"
```

Expected: 仅新版发布包进入该提交，不包含 `.superpowers/` 或其他无关文件。
