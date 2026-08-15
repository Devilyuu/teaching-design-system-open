---
name: "智能备课文档生成系统"
description: "面向高职教师的清晰、可信、低干扰备课工作台"
colors:
  institutional-blue: "#2452C7"
  institutional-blue-deep: "#1F43B3"
  canvas-mist: "#EEF3FB"
  work-surface: "#FFFFFF"
  surface-subtle: "#F8FAFD"
  selection-blue: "#EDF3FF"
  ink: "#1E2430"
  ink-secondary: "#56647A"
  border: "#D5DEED"
  border-subtle: "#E9EDF5"
  attention-orange: "#FF6B2B"
  attention-soft: "#FFF1E9"
  success: "#168052"
  success-soft: "#EBF7F1"
  danger: "#C84B62"
  danger-soft: "#FFF0F2"
typography:
  headline:
    fontFamily: "Microsoft YaHei, PingFang SC, Segoe UI, sans-serif"
    fontSize: "24px"
    fontWeight: 700
    lineHeight: 1.35
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Microsoft YaHei, PingFang SC, Segoe UI, sans-serif"
    fontSize: "16px"
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: "Microsoft YaHei, PingFang SC, Segoe UI, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Microsoft YaHei, PingFang SC, Segoe UI, sans-serif"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1.4
rounded:
  control: "4px"
  surface: "6px"
  tag: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  xxl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.institutional-blue}"
    textColor: "{colors.work-surface}"
    rounded: "{rounded.control}"
    padding: "8px 14px"
    height: "36px"
  button-secondary:
    backgroundColor: "{colors.work-surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "8px 14px"
    height: "36px"
  input:
    backgroundColor: "{colors.work-surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "9px 10px"
    height: "40px"
  navigation-active:
    backgroundColor: "{colors.work-surface}"
    textColor: "{colors.institutional-blue-deep}"
    rounded: "{rounded.surface}"
    padding: "9px 10px"
  status-tag:
    backgroundColor: "{colors.selection-blue}"
    textColor: "{colors.institutional-blue-deep}"
    rounded: "{rounded.tag}"
    padding: "3px 8px"
---

# Design System: 智能备课文档生成系统

## Overview

**Creative North Star: “蓝图工作台”**

界面像一张被整理好的教学蓝图：结构先于装饰，依据与状态始终可追溯，教师可以迅速判断当前进度和下一步动作。雾蓝导航与画布建立稳定的工作环境，白色只保留给可阅读、可编辑、可确认的正式内容，因此页面不会陷入“全部都是白卡片”的单调。

设计服务于连续数小时的桌面备课，不追求营销式惊艳。交互遵循成熟办公软件的熟悉感：固定侧栏、清晰页面标题、稳定的表单控件、逐层展开的复杂信息、可恢复的生成流程。移动端用于浏览、确认和轻量操作，重编辑在桌面完成。

**Key Characteristics:**

- 雾蓝负责区域分层，白色负责工作内容。
- 每页一个当前主任务，次要操作退到工具栏或局部区域。
- 信息密度适中，依靠间距、分隔线和标题层级组织，不依靠卡片堆叠。
- AI 是可解释、可中断、可重试的流程能力，不是视觉主角。
- 课程、课次、文档和历史记录使用同一套状态语言。

## Colors

这是一个冷静的教育办公蓝色系统：蓝色表达结构与信任，橙色表达需要教师注意的事项，语义色只服务于真实状态。

### Primary

- **院校蓝**：用于唯一主操作、当前导航、焦点和关键链接；同一可视区域不得出现多个同权重蓝色按钮。
- **深院校蓝**：用于蓝色表面上的文字、选中态文字和主色悬停状态。

### Secondary

- **批注橙**：仅用于待处理、阻塞前提醒和需复核状态。禁止用于品牌装饰、渐变或大面积背景。

### Neutral

- **雾蓝画布**：页面背景和侧栏分区，承担约 18%–24% 的可视面积。
- **工作白**：编辑器、表格、表单和文档预览的内容表面。
- **墨色**：标题、正文和数据的主要阅读色。
- **次级墨色**：说明、时间和补充信息；必须保持 WCAG AA 对比度。
- **结构线**：表格、列表和表单的边界。分隔线承担层级，不依赖普遍阴影。

**The Chromatic Zoning Rule.** 蓝色通过导航、画布和选中区形成区域层级；禁止把所有表面都做成白色，再靠阴影区分。

**The One Primary Action Rule.** 每个页面或独立工作区只允许一个视觉最强的院校蓝按钮。

**The Orange Is Work Rule.** 橙色出现时必须意味着“教师需要关注或处理”，否则禁止使用。

## Typography

**Display Font:** Microsoft YaHei（回退至 PingFang SC、Segoe UI、sans-serif）  
**Body Font:** Microsoft YaHei（同一字体栈）

**Character:** 单一中文无衬线字体维持熟悉、可靠的办公感。层级通过字号、字重和留白建立，不使用展示字体、全大写小标题或夸张字距。

### Hierarchy

- **Headline**（700，24px，1.35）：页面标题和课程标题，一屏最多一个。
- **Title**（600，16px，1.4）：分区标题、面板标题和重要字段组。
- **Body**（400，14px，1.6）：正文、说明和表单内容；连续说明控制在 70 个中文字符左右的阅读宽度。
- **Label**（500，12px，1.4）：字段标签、元数据和状态辅助信息，不使用全大写或扩张字距。

**The Quiet Hierarchy Rule.** 相邻层级只通过一个字号或字重台阶区分；禁止用同时放大、加粗、变色来制造噪声。

## Elevation

系统以色调分层和结构线为主，默认表面保持平坦。阴影只用于真正浮于页面之上的菜单、对话框、固定工具栏，以及需要与背景分离的登录面板；普通卡片、表格和表单不得同时使用边框与宽模糊阴影。

### Shadow Vocabulary

- **浮层**（`0 4px 8px rgba(31, 67, 179, 0.12)`）：仅用于菜单、对话框和浮动确认层。
- **登录面板**（`0 8px 24px rgba(31, 67, 179, 0.10)`）：登录页唯一的大面积抬升表面，不再叠加粗边框。

**The Flat-by-Default Rule.** 静态内容面默认无阴影；如果一个页面看起来像很多漂浮白卡片，说明层级方法已经错误。

## Components

### Buttons

- **Shape:** 紧凑直角圆角（4px），高度 36px；触屏环境保持至少 44px 点击区域。
- **Primary:** 院校蓝底、白字，只承载当前流程的下一步或提交动作。
- **Hover / Focus:** 150–200ms 颜色过渡；焦点使用清晰的 2px 外环，不移动组件位置。
- **Secondary:** 白底结构线，用于查看、返回、替换和次级保存。
- **Danger:** 默认使用白底危险色文字；只有不可逆确认步骤才使用实色危险按钮。

### Chips

- **Style:** 仅用于状态和紧凑筛选，圆形胶囊边缘；状态必须同时包含文字或图标，不得只靠颜色。
- **State:** 成功、提醒、危险和信息使用固定语义色；禁止把普通类别全部做成彩色标签。

### Cards / Containers

- **Corner Style:** 轻微圆角（6px）。
- **Background:** 工作白或表面浅色，禁止透明玻璃效果。
- **Shadow Strategy:** 默认无阴影，引用 Elevation 规则。
- **Border:** 1px 结构线；可编辑内容与只读摘要使用不同表面色，而不是再嵌套一层卡片。
- **Internal Padding:** 紧凑 16px，重要工作区 24px，列表行以 12–16px 垂直节奏为主。

### Inputs / Fields

- **Style:** 工作白背景、1px 结构线、4px 圆角、40px 基础高度。标签永远可见，placeholder 不承担字段名称。
- **Focus:** 院校蓝边框与 2px 外环；键盘和鼠标状态一致。
- **Error / Disabled:** 错误紧邻字段说明原因与修复方法；禁用态降低强调但仍保持文字可读。
- **Long Forms:** 按“课程信息、资料与模板、生成设置”分组，使用渐进展开，禁止一次展示超长表单墙。

### Navigation

雾蓝侧栏负责一级区域，活动项使用白色工作面和深院校蓝文字，不使用彩色竖条。课程内二级导航使用水平标签页，并保持课程名称与当前课次上下文可见。窄屏折叠为顶部导航和可横向滚动的标签页，页面本身不得横向溢出。

### Generation Status

生成状态必须包含当前阶段、已完成数量、剩余工作、预计行为和失败恢复路径。长任务使用骨架、进度条或分项状态，不在空白页面中央只放一个旋转图标。失败项可单独重试，已生成内容不因一次失败而消失。

### Document Preview

预览区模拟正式文档的阅读边界，但不使用纸张纹理。桌面端优先提供可读页宽、缩放、页码和导出状态；窄屏切换为内容摘要和“在桌面编辑”说明，避免缩小整张文档造成不可读。

## Do's and Don'ts

### Do:

- **Do** 使用雾蓝导航和画布建立分区，让白色只承载可操作内容。
- **Do** 在每个页面顶部同时说明“当前状态、下一步、为什么”。
- **Do** 为按钮、输入、标签、加载、空状态和错误建立完整且统一的状态词汇。
- **Do** 让资料替换、AI 生成和导出过程明确显示影响范围、保留内容和恢复方法。
- **Do** 在 375px、768px、1024px 和 1440px 验证布局，窄屏不产生页面级横向滚动。

### Don't:

- **Don't** 做“营销型 AI 产品”：禁止紫蓝渐变、发光效果、漂浮卡片和夸张动效。
- **Don't** 做传统政务后台的沉重深色框架，也不要用密集菜单和表格堆满首屏。
- **Don't** 把每段内容包进卡片，禁止卡片套卡片、统一图标方块和无意义指标墙。
- **Don't** 隐藏生成依据、失败原因或下一步操作，禁止用笼统的“处理中”或“操作失败”结束反馈。
- **Don't** 在卡片和提示上使用大于 1px 的彩色侧边条；改用完整边界、背景色和明确图标。
- **Don't** 同时给普通表面添加 1px 边框与 16px 以上模糊阴影。
- **Don't** 使用渐变文字、玻璃拟态、装饰网格、条纹背景或手绘 SVG。

