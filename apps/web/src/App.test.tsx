import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const tasks = [
  {
    id: 1,
    term: "2026-2027 第一学期",
    major: "数字媒体艺术设计",
    class_name: "数媒艺术 2501",
    course_name: "人工智能与创意设计",
    teacher_name: "张老师",
    location: "智慧教室",
    total_hours: 32,
    hours_per_session: 4,
    status: "outline_ready",
    course_standard_uploaded: true,
    talent_plan_uploaded: true,
    sources_confirmed: true,
    schedule_uploaded: true,
    outline_template_uploaded: true,
    lesson_template_uploaded: true,
    outline_rows_count: 1,
    lesson_plans_count: 1,
    session_count: 8,
    completed_sessions_count: 2,
    next_session_no: 3,
    next_session_date: new Date().toISOString().slice(0, 10),
    next_session_weekday: "周一",
    next_session_periods: "1-4"
  }
];

const outlineRows = [
  {
    id: 11,
    session_no: 1,
    date_text: "2026-09-07",
    week_no: 1,
    weekday: "周一",
    periods: "1-4",
    topic: "AIGC 与创意设计导入",
    teaching_content: "理解 AIGC 基础与创意设计流程",
    ideological_point: "技术向善",
    teaching_methods: "案例分析、项目导入",
    pre_task: "阅读课程说明",
    in_class_task: "完成案例拆解",
    post_task: "提交调研记录",
    course_goal_codes: "M1",
    ability_codes: "1-3-4",
    note: "",
    updated_at: "2026-07-03T08:00:00Z"
  }
];

const outlineRevisionCandidate = {
  id: 71,
  task_id: 1,
  outline_row_id: 11,
  field_name: "teaching_content",
  original_content: outlineRows[0].teaching_content,
  proposed_content: "通过真实设计案例理解 AIGC 工作流，并完成提示词迭代练习。",
  teacher_instruction: "",
  status: "pending",
  created_at: "2026-07-03T08:10:00Z"
};

const lessonPlans = [
  {
    id: 21,
    task_id: 1,
    outline_row_id: 11,
    session_no: 1,
    title: "第 1 次课：理解 AIGC 基础与创意设计流程",
    duration_minutes: 160,
    teaching_goals: "对应课程目标 M1，支撑能力指标 1-3-4。",
    key_points: "理解 AIGC 基础与创意设计流程",
    difficult_points: "将 AI 工具使用落实到具体设计任务中。",
    teaching_process: "课前：阅读课程说明\n导入：展示案例\n实训：完成案例拆解\n课后：提交调研记录",
    homework: "提交调研记录",
    reflection: "课后补充教学反思",
    course_goal_codes: "M1",
    ability_codes: "1-3-4"
  }
];

const sessionMaterials = [
  {
    id: 31,
    task_id: 1,
    outline_row_id: 11,
    owner_user_id: 1,
    material_type: "assignment",
    title: "AIGC 实践作业",
    content: "完成一份案例拆解。",
    reference_answer: "成果应包含背景、方法和结论。",
    grading_criteria: "任务完成度 40 分。",
    difficulty: "medium",
    estimated_minutes: 40,
    course_goal_codes: "M1",
    ability_codes: "1-3-4",
    source_status: "outline_and_lesson",
    generation_method: "ai",
    created_at: "2026-07-02T08:00:00Z",
    updated_at: "2026-07-02T08:00:00Z"
  }
];

const sourceReview = {
  task_id: 2,
  goals: [
    {
      code: "M1",
      description: "理解 AIGC 基础与创意设计流程",
      ability_codes: ["1-3-4"],
      indicators: [
        {
          code: "1-3-4",
          category: "知识点",
          group_code: "1-3",
          description: "探究基础动画关键帧的制作方法"
        }
      ],
      unknown_codes: []
    }
  ],
  indicators_count: 136,
  unknown_codes: [],
  can_confirm: true,
  confirmed: false
};

const readiness = {
  task_id: 1,
  materials: {
    talent_plan: { kind: "talent_plan", status: "ready", filename: "人才培养方案.docx", message: "资料已就绪", summary: {} },
    course_standard: { kind: "course_standard", status: "ready", filename: "课程标准.docx", message: "资料已就绪", summary: {} },
    schedule: { kind: "schedule", status: "ready", filename: "课表.xlsx", message: "资料已就绪", summary: {} },
    outline_template: { kind: "outline_template", status: "ready", filename: "实施大纲模板.docx", message: "资料已就绪", summary: {} },
    lesson_template: { kind: "lesson_template", status: "ready", filename: "教案模板.docx", message: "资料已就绪", summary: {} }
  },
  source_review: { ...sourceReview, task_id: 1, confirmed: true },
  schedule_hours: 32,
  expected_hours: 32,
  can_generate_outline: false,
  blocking_reasons: [],
  next_action: "open_outline",
  pending_schedule: null,
  review_notices: []
};

const exportRecords = [
  {
    id: 31,
    artifact_type: "outline",
    artifact_label: "课程实施大纲",
    filename: "人工智能与创意设计_课程实施大纲.docx",
    size_bytes: 45056,
    template_filename: "课程实施大纲模板.docx",
    source_summary: "1 行课程实施大纲，课程依据已确认",
    session_no: null,
    exported_by: "张老师",
    created_at: "2026-08-07T02:30:00Z",
    available: true
  }
];

function mockFetch(options: { unknownCodes?: boolean; noSessionLesson?: boolean } = {}) {
  let lessonsGenerated = false;
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.endsWith("/auth/me") && (!init || init.method === undefined)) {
      return jsonResponse({
        id: 1,
        employee_no: "admin",
        name: "系统管理员",
        role: "admin",
        is_active: true,
        major_ids: []
      });
    }

    if (url.endsWith("/auth/login") && init?.method === "POST") {
      return jsonResponse({ access_token: "token", token_type: "bearer" });
    }

    if (url.endsWith("/auth/change-password") && init?.method === "POST") {
      return jsonResponse({ status: "ok" });
    }

    if (url.endsWith("/majors") && (!init || init.method === undefined)) {
      return jsonResponse([{ id: 1, name: "数字媒体艺术设计", short_name: "数媒", is_active: true }]);
    }

    if (url.endsWith("/admin/majors") && (!init || init.method === undefined)) {
      return jsonResponse([{ id: 1, name: "数字媒体艺术设计", short_name: "数媒", is_active: true }]);
    }

    if (url.endsWith("/admin/users") && (!init || init.method === undefined)) {
      return jsonResponse([
        { id: 1, employee_no: "admin", name: "系统管理员", role: "admin", is_active: true, major_ids: [] },
        { id: 2, employee_no: "T001", name: "张老师", role: "teacher", is_active: true, major_ids: [1] }
      ]);
    }

    if (url.endsWith("/admin/users/2/password") && init?.method === "POST") {
      return jsonResponse({ status: "ok" });
    }

    if (url.endsWith("/tasks") && (!init || init.method === undefined)) {
      return jsonResponse(tasks);
    }

    if (url.endsWith("/tasks") && init?.method === "POST") {
      return jsonResponse({ ...tasks[0], id: 2, course_name: "新课程" });
    }

    if (url.endsWith("/tasks/1/readiness") && (!init || init.method === undefined)) {
      return jsonResponse(readiness);
    }

    if (url.endsWith("/tasks/2/readiness") && (!init || init.method === undefined)) {
      return jsonResponse({
        ...readiness,
        task_id: 2,
        materials: Object.fromEntries(
          Object.entries(readiness.materials).map(([key, material]) => [
            key,
            { ...material, status: "missing", filename: null, message: "尚未上传" }
          ])
        ),
        source_review: null,
        schedule_hours: 0,
        can_generate_outline: false,
        blocking_reasons: [{ code: "missing_materials", message: "请先补齐课程资料" }],
        next_action: "complete_materials"
      });
    }

    if (url.endsWith("/course-standard") && init?.method === "POST") {
      return jsonResponse({ task_id: 2, goals_count: 2, sessions_count: 0 });
    }

    if (url.endsWith("/talent-plan") && init?.method === "POST") {
      return jsonResponse({ task_id: 2, goals_count: 0, indicators_count: 136, sessions_count: 0 });
    }

    if (url.endsWith("/sources/review") && (!init || init.method === undefined)) {
      return jsonResponse(
        options.unknownCodes
          ? {
              ...sourceReview,
              goals: [
                {
                  ...sourceReview.goals[0],
                  ability_codes: ["9-9-9"],
                  indicators: [],
                  unknown_codes: ["9-9-9"]
                }
              ],
              unknown_codes: ["9-9-9"],
              can_confirm: false
            }
          : sourceReview
      );
    }

    if (url.endsWith("/sources/confirm") && init?.method === "POST") {
      return jsonResponse({ ...sourceReview, confirmed: true });
    }

    if (url.endsWith("/schedule") && init?.method === "POST") {
      return jsonResponse({ task_id: 2, goals_count: 0, sessions_count: 1 });
    }

    if (url.endsWith("/templates/outline") && init?.method === "POST") {
      return jsonResponse({ kind: "outline", filename: "课程实施大纲模板.docx", size: 8 });
    }

    if (url.endsWith("/templates/lesson") && init?.method === "POST") {
      return jsonResponse({ kind: "lesson", filename: "教案模板.docx", size: 8 });
    }

    if (url.endsWith("/outline/generate") && init?.method === "POST") {
      return jsonResponse(outlineRows);
    }

    if (url.endsWith("/outline/sections/regenerate") && init?.method === "POST") {
      return jsonResponse({ course_summary: "重写后的课程简介。" });
    }

    if (url.endsWith("/outline/export") && init?.method === "POST") {
      return new Response(new Blob(["docx"]), {
        status: 200,
        headers: {
          "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
          "Content-Disposition": "attachment; filename*=UTF-8''outline.docx"
        }
      });
    }

    if (url.endsWith("/tasks/1/exports") && (!init || init.method === undefined)) {
      return jsonResponse(exportRecords);
    }

    if (url.endsWith("/tasks/1/lessons") && (!init || init.method === undefined)) {
      return jsonResponse(lessonsGenerated ? lessonPlans : []);
    }

    if (url.endsWith("/tasks/1/lesson-generation-runs") && init?.method === "POST") {
      lessonsGenerated = true;
      return jsonResponse({
        id: 51,
        task_id: 1,
        status: "completed",
        total_items: 1,
        succeeded_items: 1,
        failed_items: 0,
        created_at: "2026-07-02T08:00:00Z",
        finished_at: "2026-07-02T08:01:00Z",
        items: [{ id: 61, outline_row_id: 11, lesson_plan_id: 21, status: "succeeded", attempts: 1, duration_ms: 200, error_code: "" }]
      });
    }

    if (url.endsWith("/tasks/1/lesson-generation-runs/51") && (!init || init.method === undefined)) {
      return jsonResponse({
        id: 51,
        task_id: 1,
        status: "completed",
        total_items: 1,
        succeeded_items: 1,
        failed_items: 0,
        created_at: "2026-07-02T08:00:00Z",
        finished_at: "2026-07-02T08:01:00Z",
        items: [{ id: 61, outline_row_id: 11, lesson_plan_id: 21, status: "succeeded", attempts: 1, duration_ms: 200, error_code: "" }]
      });
    }

    if (url.endsWith("/tasks/1/lessons/21") && init?.method === "PUT") {
      return jsonResponse({ ...lessonPlans[0], ...JSON.parse(String(init.body)) });
    }

    if (url.endsWith("/tasks/1/lessons/export") && init?.method === "POST") {
      return new Response(new Blob(["lesson-docx"]), {
        status: 200,
        headers: {
          "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
          "Content-Disposition": "attachment; filename*=UTF-8''lessons.docx"
        }
      });
    }

    if (url.endsWith("/tasks/1/outline") || url.endsWith("/tasks/2/outline")) {
      return jsonResponse(outlineRows);
    }

    if (url.endsWith("/tasks/1/outline/11") && init?.method === "PUT") {
      return jsonResponse({ ...outlineRows[0], topic: "更新后的主题" });
    }

    if (url.endsWith("/tasks/1/outline/11/revision-candidates") && init?.method === "POST") {
      return jsonResponse(outlineRevisionCandidate);
    }

    if (url.endsWith("/tasks/1/outline-revision-candidates/71/accept") && init?.method === "POST") {
      return jsonResponse({ ...outlineRevisionCandidate, status: "accepted" });
    }

    if (url.endsWith("/tasks/1/outline-revision-candidates/71/reject") && init?.method === "POST") {
      return jsonResponse({ ...outlineRevisionCandidate, status: "rejected" });
    }

    if (url.endsWith("/tasks/1/sessions/11") && (!init || init.method === undefined)) {
      return jsonResponse({
        outline: outlineRows[0],
        lesson: options.noSessionLesson ? null : lessonPlans[0],
        materials: sessionMaterials,
        reflection: null,
        next_outline: { ...outlineRows[0], id: 12, session_no: 2, date_text: "2026-09-14" },
        next_lesson_exists: !options.noSessionLesson
      });
    }

    if (url.endsWith("/tasks/1/sessions/11/reflection") && init?.method === "PUT") {
      return jsonResponse({
        id: 41,
        task_id: 1,
        outline_row_id: 11,
        owner_user_id: 1,
        ...JSON.parse(String(init.body)),
        suggestion_type: "progress+mastery",
        suggestion_text: "补充说明：示范环节未完成。建议补讲本次课未完成内容；安排复习、示范或基础练习。",
        suggested_minutes: 20,
        status: "pending",
        target_outline_row_id: 12,
        applied_lesson_plan_id: null,
        created_at: "2026-07-02T08:00:00Z",
        updated_at: "2026-07-02T08:00:00Z",
        applied_at: null,
        reverted_at: null
      });
    }

    if (url.endsWith("/tasks/1/reflections/41/apply") && init?.method === "POST") {
      return jsonResponse({ ...lessonPlans[0], id: 22, outline_row_id: 12, session_no: 2 });
    }

    if (url.endsWith("/tasks/1/sessions/11/materials/generate") && init?.method === "POST") {
      const payload = JSON.parse(String(init.body));
      return jsonResponse({
        ...sessionMaterials[0],
        id: 32,
        material_type: payload.material_type,
        title: payload.material_type === "test" ? "AIGC 课堂测试" : "AIGC 实践作业",
        difficulty: payload.difficulty,
        estimated_minutes: payload.estimated_minutes,
        content: payload.material_type === "test" ? "第 1 题：说明 AIGC 的关键要点。" : sessionMaterials[0].content
      });
    }

    if (url.endsWith("/tasks/1/materials/31") && init?.method === "PUT") {
      return jsonResponse({ ...sessionMaterials[0], ...JSON.parse(String(init.body)) });
    }

    if (url.endsWith("/tasks/1/materials/31") && init?.method === "DELETE") {
      return new Response(null, { status: 204 });
    }

    if (url.endsWith("/tasks/1/materials/31/export") && init?.method === "POST") {
      return new Response(new Blob(["material-docx"]), {
        status: 200,
        headers: { "Content-Disposition": "attachment; filename*=UTF-8''material.docx" }
      });
    }

    return jsonResponse({ detail: "Not found" }, 404);
  });
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" }
  });
}

describe("App", () => {
  beforeEach(() => {
    localStorage.setItem("teachingDesignToken", "token");
    localStorage.removeItem("lesson-generation-run:1");
    vi.stubGlobal("fetch", mockFetch());
  });

  it("starts the login form without development credentials", async () => {
    localStorage.removeItem("teachingDesignToken");
    render(<App />);

    expect(await screen.findByLabelText("工号")).toHaveValue("");
  });

  it("announces authentication progress", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => undefined)));

    render(<App />);

    expect(screen.getByRole("status")).toHaveTextContent("正在检查登录状态");
  });

  it("logs in with an employee number before loading the dashboard", async () => {
    localStorage.removeItem("teachingDesignToken");
    const user = userEvent.setup();
    render(<App />);

    await user.type(screen.getByLabelText("工号"), "admin");
    await user.type(screen.getByLabelText("密码"), "Admin@2026!");
    await user.click(screen.getByRole("button", { name: "登录" }));

    expect((await screen.findAllByText("人工智能与创意设计")).length).toBeGreaterThan(0);
  });

  it("changes the current user's password", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "修改密码" }));
    await user.type(screen.getByLabelText("当前密码"), "Admin@2026!");
    await user.type(screen.getByLabelText("新密码"), "Changed@2026!");
    await user.type(screen.getByLabelText("确认新密码"), "Changed@2026!");
    await user.click(screen.getByRole("button", { name: "保存新密码" }));

    expect(await screen.findByText("密码已修改")).toBeInTheDocument();
  });

  it("explains password requirements before allowing a password change", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "修改密码" }));
    const saveButton = screen.getByRole("button", { name: "保存新密码" });
    expect(saveButton).toBeDisabled();

    await user.type(screen.getByLabelText("当前密码"), "Admin@2026!");
    await user.type(screen.getByLabelText("新密码"), "Changed@2026!");
    await user.type(screen.getByLabelText("确认新密码"), "Changed@2025!");

    expect(screen.getByText("两次输入不一致")).toBeInTheDocument();
    expect(saveButton).toBeDisabled();

    await user.clear(screen.getByLabelText("确认新密码"));
    await user.type(screen.getByLabelText("确认新密码"), "Changed@2026!");
    expect(screen.getByText("两次输入一致")).toBeInTheDocument();
    expect(saveButton).toBeEnabled();
  });

  it("lets an admin reset a teacher password", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "标准库与账号管理" }));
    await user.type(await screen.findByLabelText("重置 张老师 密码"), "Reset@2026!");
    await user.click(screen.getByRole("button", { name: "重置 张老师 密码" }));

    expect(await screen.findByText("密码已重置")).toBeInTheDocument();
  });

  it("organizes admin tools into focused sections", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "标准库与账号管理" }));
    expect(await screen.findByRole("tablist", { name: "管理内容" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "账号与专业" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByLabelText("重置 张老师 密码")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "人才培养方案库" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "标准与模板" }));
    expect(screen.getByRole("heading", { name: "人才培养方案库" })).toBeInTheDocument();
    expect(screen.queryByLabelText("重置 张老师 密码")).not.toBeInTheDocument();
    expect(screen.getByText("15 个占位符")).not.toHaveClass("green");

    await user.click(screen.getByRole("tab", { name: "AI 生成配置" }));
    expect(screen.getByRole("heading", { name: "AI 模型配置" })).toBeInTheDocument();
  });

  it("keeps admin creation forms collapsed until requested", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "标准库与账号管理" }));
    await screen.findByRole("heading", { name: "专业管理" });
    expect(screen.queryByLabelText("专业名称")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("工号")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "新增专业" }));
    expect(screen.getByLabelText("专业名称")).toBeInTheDocument();
    expect(screen.queryByLabelText("工号")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "新增教师" }));
    expect(screen.getByLabelText("工号")).toBeInTheDocument();
    expect(screen.queryByLabelText("专业名称")).not.toBeInTheDocument();
  });

  it("lists teaching tasks on the dashboard", async () => {
    render(<App />);

    expect(await screen.findByRole("heading", { name: "待处理事项" })).toBeInTheDocument();
    expect(screen.getByText("继续本次课备课")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "新建学期课程" })).toBeInTheDocument();
  });

  it("matches the approved prototype navigation and dashboard workflow", async () => {
    render(<App />);

    expect(await screen.findByRole("heading", { name: "今天的课程" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "我的课程" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "教案生成" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "标准库与账号管理" })).toBeInTheDocument();
  });

  it("uses semester courses as the primary teacher navigation", async () => {
    render(<App />);

    expect(await screen.findByRole("button", { name: "教师工作台" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "我的课程" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "新建学期课程" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "教案生成" })).not.toBeInTheDocument();
  });

  it("marks the current primary navigation destination", async () => {
    render(<App />);

    expect(await screen.findByRole("button", { name: "教师工作台" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("button", { name: "我的课程" })).not.toHaveAttribute("aria-current");
  });

  it("lists the current teacher's semester courses", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "我的课程" }));

    expect(screen.getByRole("heading", { name: "我的课程" })).toBeInTheDocument();
    expect(screen.getByText("人工智能与创意设计")).toBeInTheDocument();
    expect(screen.getByText(/已完成 2\/8 次课/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "进入课程" })).toBeInTheDocument();
  });

  it("filters semester courses and explains when no course matches", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "我的课程" }));
    const search = screen.getByRole("searchbox", { name: "搜索课程" });
    await user.type(search, "不存在的课程");

    expect(screen.queryByText("人工智能与创意设计")).not.toBeInTheDocument();
    expect(screen.getByText("没有找到匹配的课程")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "清除搜索" })).toBeInTheDocument();
  });

  it("keeps course entry actions visually secondary", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "我的课程" }));

    expect(screen.getByRole("button", { name: "进入课程" })).not.toHaveClass("primary");
    expect(screen.getAllByRole("button", { name: "新建学期课程" })
      .some((button) => button.classList.contains("primary"))).toBe(true);
  });

  it("shows today's course and pending preparation on the teacher dashboard", async () => {
    render(<App />);

    expect(await screen.findByRole("heading", { name: "今天的课程" })).toBeInTheDocument();
    expect(screen.getByText(/第 3 次课/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "进入本次课" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "待处理事项" })).toBeInTheDocument();
  });

  it("opens a course workspace with five stable tabs", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "我的课程" }));
    await user.click(screen.getByRole("button", { name: "进入课程" }));

    expect(screen.getByRole("tab", { name: "课程概览" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "课程资料" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "课程实施大纲" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "整门课教案" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "课次与材料" })).toBeInTheDocument();
  });

  it("keeps My Courses selected while working inside a course", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "我的课程" }));
    await user.click(screen.getByRole("button", { name: "进入课程" }));

    expect(screen.getByRole("button", { name: "我的课程" })).toHaveAttribute("aria-current", "page");
  });

  it("opens a dedicated course materials workspace", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "我的课程" }));
    await user.click(screen.getByRole("button", { name: "进入课程" }));
    await user.click(screen.getByRole("tab", { name: "课程资料" }));
    expect(await screen.findByRole("heading", { name: "课程资料与生成准备" })).toBeInTheDocument();
    expect(screen.getByText("课程标准.docx")).toBeInTheDocument();
  });

  it("presents course readiness as a clear status and material checklist", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "我的课程" }));
    await user.click(screen.getByRole("button", { name: "进入课程" }));
    await user.click(screen.getByRole("tab", { name: "课程资料" }));

    expect(await screen.findByRole("status", { name: "课程资料已就绪" })).toBeInTheDocument();
    const materialRegion = screen.getByRole("region", { name: "课程资料清单" });
    expect(within(materialRegion).getAllByRole("listitem")).toHaveLength(5);
    expect(within(materialRegion).getAllByText("替换后将重新核对生成条件")).toHaveLength(5);
    expect(screen.getByRole("button", { name: "查看已有课程实施大纲" })).not.toHaveClass("primary");
  });

  it("keeps the course workspace controls available at narrow widths", async () => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 390 });
    window.dispatchEvent(new Event("resize"));
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "我的课程" }));
    await user.click(screen.getByRole("button", { name: "进入课程" }));

    expect(screen.getByRole("tablist", { name: "课程工作台" })).toBeInTheDocument();
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual([
      "课程概览",
      "课程资料",
      "课程实施大纲",
      "整门课教案",
      "课次与材料",
      "导出记录"
    ]);
  });

  it("traces an exported document back to its template and evidence", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "我的课程" }));
    await user.click(screen.getByRole("button", { name: "进入课程" }));
    await user.click(screen.getByRole("tab", { name: "导出记录" }));

    const row = await screen.findByRole("listitem");
    expect(within(row).getByText("人工智能与创意设计_课程实施大纲.docx")).toBeInTheDocument();
    expect(within(row).getByText(/课程实施大纲模板\.docx/)).toBeInTheDocument();
    expect(within(row).getByRole("button", { name: "重新下载" })).toBeInTheDocument();
  });

  it("shows resumable task progress on the dashboard", async () => {
    render(<App />);

    await screen.findByRole("heading", { name: "待处理事项" });

    expect(screen.getByText("大纲 1 行")).toBeInTheDocument();
    expect(screen.getByText("教案 1 份")).toBeInTheDocument();
    expect(screen.getByText("模板已保存")).toBeInTheDocument();
  });

  it("creates a teaching task from the new task form", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "新建学期课程" }));
    await user.clear(screen.getByLabelText("课程名称"));
    await user.type(screen.getByLabelText("课程名称"), "新课程");
    await user.click(screen.getByRole("button", { name: /保存并继续准备资料/ }));

    await waitFor(() => {
      expect(screen.getByText("任务已创建，请继续补充课程资料")).toBeInTheDocument();
    });
    expect(screen.getByRole("tab", { name: "课程资料" })).toHaveAttribute("aria-selected", "true");
    expect(await screen.findByRole("heading", { name: "课程资料与生成准备" })).toBeInTheDocument();
  });

  it("keeps material uploads and generation controls out of the new course form", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "新建学期课程" }));

    expect(screen.getByLabelText("课程名称")).toBeInTheDocument();
    expect(screen.queryByLabelText("上传课程标准")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("上传教务课表")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "解析并检查课程依据" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "AI 生成课程实施大纲" })).not.toBeInTheDocument();
  });

  it("groups new course details and previews the teaching schedule", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "新建学期课程" }));

    expect(screen.getByRole("group", { name: "课程归属" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "授课安排" })).toBeInTheDocument();
    expect(screen.getByText(/预计形成 8 次课/)).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: "创建后流程" })).toBeInTheDocument();
  });

  it("edits and saves an outline table row", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "我的课程" }));
    await user.click(screen.getByRole("button", { name: "进入课程" }));
    await user.click(screen.getByRole("tab", { name: "课程实施大纲" }));
    const table = await screen.findByRole("table", { name: "课程实施大纲编辑表" });
    expect(screen.queryByRole("button", { name: "重新生成" })).not.toBeInTheDocument();
    const row = within(table).getByRole("row", { name: /AIGC 与创意设计导入/ });

    await user.clear(within(row).getByLabelText("主题"));
    await user.type(within(row).getByLabelText("主题"), "更新后的主题");
    expect(screen.getByText("1 项未保存")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "导出课程实施大纲" })).toBeDisabled();
    expect(within(row).getByRole("button", { name: "AI 优化第 1 次课" })).toBeDisabled();
    await user.click(within(row).getByRole("button", { name: "保存修改" }));

    await waitFor(() => {
      expect(screen.getByText("第 1 次课已保存")).toBeInTheDocument();
    });
    expect(screen.getByText("全部修改已保存")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "导出课程实施大纲" })).toBeEnabled();
  });

  it("asks for a fresh outline body without touching the schedule", async () => {
    // The body is written on the first export and then kept, so there has to be
    // a way to ask for different prose.
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "我的课程" }));
    await user.click(screen.getByRole("button", { name: "进入课程" }));
    await user.click(screen.getByRole("tab", { name: "课程实施大纲" }));
    await screen.findByRole("table", { name: "课程实施大纲编辑表" });

    await user.click(screen.getByRole("button", { name: "重写大纲正文" }));

    await waitFor(() => {
      expect(screen.getByText("大纲正文已重新生成，下次导出即为新内容")).toBeInTheDocument();
    });
    const calls = (globalThis.fetch as unknown as { mock: { calls: [string, RequestInit?][] } }).mock.calls;
    expect(calls.some(([url, init]) =>
      url.endsWith("/tasks/1/outline/sections/regenerate") && init?.method === "POST"
    )).toBe(true);
  });

  it("defines stable columns for the outline editor table", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "我的课程" }));
    await user.click(screen.getByRole("button", { name: "进入课程" }));
    await user.click(screen.getByRole("tab", { name: "课程实施大纲" }));

    const table = await screen.findByRole("table", { name: "课程实施大纲编辑表" });
    expect(Array.from(table.querySelectorAll("col")).map((column) => column.className)).toEqual([
      "outline-col-session",
      "outline-col-date",
      "outline-col-week",
      "outline-col-periods",
      "outline-col-topic",
      "outline-col-content",
      "outline-col-goals",
      "outline-col-abilities",
      "outline-col-actions"
    ]);
  });

  it("uses verified codes and accepts a row-level AI revision", async () => {
    const user = userEvent.setup();
    const fetchMock = mockFetch();
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "我的课程" }));
    await user.click(screen.getByRole("button", { name: "进入课程" }));
    await user.click(screen.getByRole("tab", { name: "课程实施大纲" }));
    await screen.findByRole("table", { name: "课程实施大纲编辑表" });

    expect(await screen.findByRole("checkbox", { name: /M1/ })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /1-3-4/ })).toBeChecked();

    await user.click(screen.getByRole("button", { name: "AI 优化第 1 次课" }));
    expect(await screen.findByText("通过真实设计案例理解 AIGC 工作流，并完成提示词迭代练习。")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "采用建议" }));

    await waitFor(() => {
      expect(screen.queryByText("通过真实设计案例理解 AIGC 工作流，并完成提示词迭代练习。")).not.toBeInTheDocument();
    });
    const calledUrls = fetchMock.mock.calls.map(([input]) => String(input));
    expect(calledUrls).toContain("http://localhost:8000/tasks/1/outline/11/revision-candidates");
    expect(calledUrls).toContain("http://localhost:8000/tasks/1/outline-revision-candidates/71/accept");
  });

  it("discards a row-level AI revision without changing the outline", async () => {
    const user = userEvent.setup();
    const fetchMock = mockFetch();
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "我的课程" }));
    await user.click(screen.getByRole("button", { name: "进入课程" }));
    await user.click(screen.getByRole("tab", { name: "课程实施大纲" }));
    await screen.findByRole("table", { name: "课程实施大纲编辑表" });
    await user.click(screen.getByRole("button", { name: "AI 优化第 1 次课" }));
    await user.click(await screen.findByRole("button", { name: "放弃建议" }));

    expect(await screen.findByText("已放弃本次 AI 建议，原内容保持不变")).toBeInTheDocument();
    const calledUrls = fetchMock.mock.calls.map(([input]) => String(input));
    expect(calledUrls).toContain("http://localhost:8000/tasks/1/outline-revision-candidates/71/reject");
  });

  it("generates lesson plans from the confirmed outline", async () => {
    const user = userEvent.setup();
    const fetchMock = mockFetch();
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "我的课程" }));
    await user.click(screen.getByRole("button", { name: "进入课程" }));
    await user.click(screen.getByRole("tab", { name: "整门课教案" }));
    await user.click(await screen.findByRole("button", { name: "生成整门课教案" }));

    expect(JSON.parse(localStorage.getItem("lesson-generation-run:1") || "null")).toMatchObject({ id: 51 });
    expect(await screen.findByText("第 1 次课：理解 AIGC 基础与创意设计流程")).toBeInTheDocument();
    expect(screen.getByDisplayValue(/课前：阅读课程说明/)).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "教案生成进度" })).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "教案生成进度" })).toHaveAttribute("value", "1");

    const calledUrls = fetchMock.mock.calls.map(([input]) => String(input));
    expect(calledUrls).toContain("http://localhost:8000/tasks/1/lesson-generation-runs");
  });

  it("protects unsaved whole-course lesson edits before export", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "我的课程" }));
    await user.click(screen.getByRole("button", { name: "进入课程" }));
    await user.click(screen.getByRole("tab", { name: "整门课教案" }));
    await user.click(await screen.findByRole("button", { name: "生成整门课教案" }));
    const goal = await screen.findByLabelText("教学目标");
    await user.type(goal, "补充目标");

    expect(screen.getByText("1 份教案未保存")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "导出整门课教案" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "保存教案修改" }));

    expect(await screen.findByText("全部教案已保存")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "导出整门课教案" })).toBeEnabled();
  });

  it("exports lesson plans with the stored template when no local file is selected", async () => {
    const user = userEvent.setup();
    const fetchMock = mockFetch();
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn(() => "blob:lesson-docx"),
      revokeObjectURL: vi.fn()
    });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "我的课程" }));
    await user.click(screen.getByRole("button", { name: "进入课程" }));
    await user.click(screen.getByRole("tab", { name: "整门课教案" }));
    await user.click(await screen.findByRole("button", { name: "生成整门课教案" }));
    await screen.findByText("第 1 次课：理解 AIGC 基础与创意设计流程");
    await user.click(screen.getByRole("button", { name: "导出整门课教案" }));

    const calledUrls = fetchMock.mock.calls.map(([input]) => String(input));
    expect(calledUrls).toContain("http://localhost:8000/tasks/1/lessons/export");
    expect(screen.queryByText("请先在新建任务页面选择教案模板")).not.toBeInTheDocument();
  });

  it("opens one session and saves its lesson plan", async () => {
    const user = userEvent.setup();
    const fetchMock = mockFetch();
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "我的课程" }));
    await user.click(screen.getByRole("button", { name: "进入课程" }));
    await user.click(screen.getByRole("tab", { name: "课次与材料" }));
    await user.click(await screen.findByRole("button", { name: "进入本次课" }));

    expect(await screen.findByRole("heading", { name: "本次课概况" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "本次教案" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "备课材料" })).toBeInTheDocument();
    const keyPoints = screen.getByLabelText("教学重点");
    await user.clear(keyPoints);
    await user.type(keyPoints, "更新后的教学重点");
    expect(screen.getByText("本次教案有未保存修改")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "保存本次教案修改" }));

    await waitFor(() => {
      expect(fetchMock.mock.calls.map(([input]) => String(input))).toContain(
        "http://localhost:8000/tasks/1/lessons/21"
      );
    });
    expect(screen.getByRole("status", { name: "本次教案保存状态" })).toHaveTextContent("本次教案已保存");
  });

  it("generates, edits and exports a session material", async () => {
    const user = userEvent.setup();
    const fetchMock = mockFetch();
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("URL", {
      createObjectURL: vi.fn(() => "blob:material-docx"),
      revokeObjectURL: vi.fn()
    });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "我的课程" }));
    await user.click(screen.getByRole("button", { name: "进入课程" }));
    await user.click(screen.getByRole("tab", { name: "课次与材料" }));
    await user.click(await screen.findByRole("button", { name: "进入本次课" }));
    await user.click(await screen.findByRole("button", { name: "测试" }));
    await user.clear(screen.getByLabelText("预计用时（分钟）"));
    await user.type(screen.getByLabelText("预计用时（分钟）"), "20");
    await user.clear(screen.getByLabelText("题量"));
    await user.type(screen.getByLabelText("题量"), "3");
    expect(screen.getByText("AI 生成")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "AI 生成测试" }));

    expect(await screen.findByDisplayValue("AIGC 课堂测试")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "AIGC 实践作业" }));
    const title = screen.getByLabelText("材料标题");
    await user.clear(title);
    await user.type(title, "修改后的实践作业");
    expect(screen.getByText("材料有未保存修改")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "导出 Word" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "保存材料修改" }));
    expect(screen.getByRole("status", { name: "材料保存状态" })).toHaveTextContent("材料已保存");
    expect(screen.getByRole("button", { name: "导出 Word" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "导出 Word" }));

    await waitFor(() => {
      const calledUrls = fetchMock.mock.calls.map(([input]) => String(input));
      expect(calledUrls).toContain("http://localhost:8000/tasks/1/sessions/11/materials/generate");
      expect(calledUrls).toContain("http://localhost:8000/tasks/1/materials/31");
      expect(calledUrls).toContain("http://localhost:8000/tasks/1/materials/31/export");
    });
  });

  it("allows material generation without a lesson and deletes saved material", async () => {
    const user = userEvent.setup();
    const fetchMock = mockFetch({ noSessionLesson: true });
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "我的课程" }));
    await user.click(screen.getByRole("button", { name: "进入课程" }));
    await user.click(screen.getByRole("tab", { name: "课次与材料" }));
    await user.click(await screen.findByRole("button", { name: "进入本次课" }));

    expect(await screen.findByText("未引用教案")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "AIGC 实践作业" }));
    await user.click(screen.getByRole("button", { name: "删除材料" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "AIGC 实践作业" })).not.toBeInTheDocument());
    expect(fetchMock.mock.calls.map(([input]) => String(input))).toContain(
      "http://localhost:8000/tasks/1/materials/31"
    );
  });

  it("records a completed session and applies its suggestion to the next lesson", async () => {
    const user = userEvent.setup();
    const fetchMock = mockFetch();
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "我的课程" }));
    await user.click(screen.getByRole("button", { name: "进入课程" }));
    await user.click(screen.getByRole("tab", { name: "课次与材料" }));
    await user.click(await screen.findByRole("button", { name: "进入本次课" }));

    expect(screen.queryByRole("button", { name: "应用到下次课教案" })).not.toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "部分完成" }));
    await user.click(screen.getByRole("button", { name: "一般" }));
    await user.click(screen.getByRole("button", { name: "基本正常" }));
    await user.type(screen.getByLabelText("补充说明"), "示范环节未完成");
    await user.click(screen.getByRole("button", { name: "保存课后记录" }));

    expect(await screen.findByText(/建议补讲本次课未完成内容/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "应用到下次课教案" }));
    expect(await screen.findByText("已应用到第 2 次课")).toBeInTheDocument();
    expect(fetchMock.mock.calls.map(([input]) => String(input))).toContain(
      "http://localhost:8000/tasks/1/reflections/41/apply"
    );
  });
});
