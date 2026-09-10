import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import CourseMaterialsPage from "./CourseMaterialsPage";
import type { CourseReadiness, ScheduleCandidate, ScheduleColumnMatch, TeachingTask } from "./types";

const getCourseReadiness = vi.fn();
const remapScheduleCandidate = vi.fn();
const confirmScheduleCandidate = vi.fn();
const discardScheduleCandidate = vi.fn();
const uploadScheduleCandidate = vi.fn();

vi.mock("./api", () => ({
  getCourseReadiness: (...args: unknown[]) => getCourseReadiness(...args),
  remapScheduleCandidate: (...args: unknown[]) => remapScheduleCandidate(...args),
  confirmScheduleCandidate: (...args: unknown[]) => confirmScheduleCandidate(...args),
  discardScheduleCandidate: (...args: unknown[]) => discardScheduleCandidate(...args),
  confirmSources: vi.fn(),
  generateOutline: vi.fn(),
  resolveReviewNotice: vi.fn(),
  uploadCourseStandard: vi.fn(),
  uploadScheduleCandidate: (...args: unknown[]) => uploadScheduleCandidate(...args),
  uploadTalentPlan: vi.fn(),
  uploadTemplate: vi.fn()
}));

const task = {
  id: 1,
  term: "2026-2027 第一学期",
  major: "数字媒体艺术设计",
  class_name: "数字艺术25级1班",
  course_name: "人工智能与创意设计",
  teacher_name: "张老师",
  location: "智慧教室",
  total_hours: 8,
  hours_per_session: 4
} as unknown as TeachingTask;

function material(status: "missing" | "ready") {
  return { kind: "x", status, filename: status === "ready" ? "文件.docx" : "", message: "", summary: {} };
}

function awaitingSchedule() {
  return {
    kind: "schedule",
    status: "awaiting_confirmation" as const,
    filename: "1001张明课表.xls",
    message: "已解析 40 次课，待你确认后生效",
    summary: {}
  };
}

function readinessWith(candidate: unknown): CourseReadiness {
  return {
    task_id: 1,
    materials: {
      talent_plan: material("ready"),
      course_standard: material("ready"),
      schedule: material("missing"),
      outline_template: material("ready"),
      lesson_template: material("ready")
    },
    source_review: {
      goals: [],
      indicators_count: 0,
      unknown_codes: [],
      can_confirm: false,
      confirmed: false
    },
    schedule_hours: 8,
    expected_hours: 8,
    can_generate_outline: false,
    blocking_reasons: [],
    next_action: "complete_materials",
    pending_schedule: candidate,
    review_notices: []
  } as unknown as CourseReadiness;
}

const candidate = {
  id: 5,
  task_id: 1,
  filename: "registrar.xlsx",
  status: "pending",
  session_count: 2,
  total_hours: 8,
  added_count: 2,
  removed_count: 0,
  changed_count: 0,
  can_confirm: true,
  blocking_message: "",
  changes: [],
  sessions: [
    {
      session_no: 1,
      week_no: 1,
      date_text: "2026-09-07",
      weekday: "一",
      periods: "1-4",
      course_name: "人工智能与创意设计",
      class_name: "数字艺术25级1班",
      location: "实训楼A301",
      hours: 4
    },
    {
      session_no: 2,
      week_no: 2,
      date_text: "2026-09-14",
      weekday: "一",
      periods: "1-4",
      course_name: "人工智能与创意设计",
      class_name: "数字艺术25级1班",
      location: "实训楼A301",
      hours: 4
    }
  ],
  header_row: 2,
  matches: [
    { field: "week_no", column_index: 0, header_text: "教学周", confidence: "alias" },
    { field: "date_text", column_index: 1, header_text: "上课日期", confidence: "alias" },
    { field: "periods", column_index: 3, header_text: "节次", confidence: "exact" },
    { field: "course_name", column_index: 4, header_text: "课程名称", confidence: "alias" },
    { field: "class_name", column_index: 5, header_text: "教学班", confidence: "alias" },
    { field: "location", column_index: 6, header_text: "上课教室", confidence: "alias" }
  ] as ScheduleColumnMatch[],
  detected_headers: ["教学周", "上课日期", "星期几", "节次", "课程名称", "教学班", "上课教室", "任课教师"],
  unmapped_headers: ["任课教师"],
  warnings: ["课表没有星期列，已根据日期推算星期，请在预览中核对。"],
  course_names: ["人工智能与创意设计", "版式设计"],
  course_filter: "人工智能与创意设计",
  teaching_classes: [],
  teaching_class: ""
};

// The registrar's .xls names a teaching class per entry, and one course
// routinely has two; the .xlsx long format carries none.
const registrarCandidate: ScheduleCandidate = {
  ...candidate,
  teaching_classes: ["人工智能与创意设计-0001", "人工智能与创意设计-0002"],
  teaching_class: "",
  warnings: ["这门课有多个教学班：人工智能与创意设计-0001、人工智能与创意设计-0002，当前把它们合并在一起，请选择一个教学班。"]
};

beforeEach(() => {
  vi.clearAllMocks();
  getCourseReadiness.mockResolvedValue(readinessWith(candidate));
});

it("shows which column each schedule field was read from", async () => {
  render(<CourseMaterialsPage task={task} onOpenOutline={vi.fn()} onError={vi.fn()} />);

  const panel = await screen.findByRole("region", { name: "新课表待确认" });
  expect(within(panel).getByText(/识别到第 3 行为表头/)).toBeInTheDocument();
  const mapping = within(panel).getByRole("table", { name: "课表列对应关系" });
  expect(within(mapping).getByRole("row", { name: /周次 教学周/ })).toBeInTheDocument();
  expect(within(mapping).getByRole("row", { name: /地点 上课教室/ })).toBeInTheDocument();
  expect(within(panel).getByText(/任课教师/)).toBeInTheDocument();
});

it("warns about every value it had to derive", async () => {
  render(<CourseMaterialsPage task={task} onOpenOutline={vi.fn()} onError={vi.fn()} />);

  const panel = await screen.findByRole("region", { name: "新课表待确认" });
  expect(within(panel).getByRole("alert")).toHaveTextContent("已根据日期推算星期");
});

it("previews the parsed sessions before they are confirmed", async () => {
  render(<CourseMaterialsPage task={task} onOpenOutline={vi.fn()} onError={vi.fn()} />);

  const panel = await screen.findByRole("region", { name: "新课表待确认" });
  const preview = within(panel).getByRole("table", { name: "课次预览" });
  expect(within(preview).getAllByRole("row")).toHaveLength(3);
  expect(within(preview).getByRole("row", { name: /2026-09-07 一 1-4/ })).toBeInTheDocument();
});

it("re-reads the file when the teacher corrects a column", async () => {
  const user = userEvent.setup();
  remapScheduleCandidate.mockResolvedValue(candidate);
  render(<CourseMaterialsPage task={task} onOpenOutline={vi.fn()} onError={vi.fn()} />);

  const panel = await screen.findByRole("region", { name: "新课表待确认" });
  await user.click(within(panel).getByRole("button", { name: "重新指定列" }));
  await user.selectOptions(within(panel).getByLabelText("星期对应的列"), "2");
  await user.click(within(panel).getByRole("button", { name: "按新的对应关系重新识别" }));

  expect(remapScheduleCandidate).toHaveBeenCalledWith(1, 5, {
    header_row: 2,
    mapping: {
      week_no: 0,
      date_text: 1,
      weekday: 2,
      periods: 3,
      course_name: 4,
      class_name: 5,
      location: 6
    },
    course_name: "人工智能与创意设计",
    teaching_class: ""
  });
});

it("shows an uploaded timetable as awaiting confirmation, not as still missing", async () => {
  const user = userEvent.setup();
  const scrollIntoView = vi.fn();
  Element.prototype.scrollIntoView = scrollIntoView;
  const readiness = readinessWith(candidate);
  readiness.materials.schedule = awaitingSchedule();
  getCourseReadiness.mockResolvedValue(readiness);
  render(<CourseMaterialsPage task={task} onOpenOutline={vi.fn()} onError={vi.fn()} />);

  const row = (await screen.findAllByRole("listitem")).find((item) => item.textContent?.includes("教务课表"))!;
  expect(within(row).getByText("待确认")).toBeInTheDocument();
  expect(within(row).queryByText("待补充")).not.toBeInTheDocument();
  expect(within(row).getByText(/1001张明课表\.xls.*已解析 40 次课/)).toBeInTheDocument();
  // Re-uploading has to stay reachable: the pending file may be the wrong one.
  expect(within(row).getByLabelText("上传教务课表")).toBeInTheDocument();

  await user.click(within(row).getByRole("button", { name: "去确认" }));
  expect(scrollIntoView).toHaveBeenCalled();
});

it("offers no teaching class picker when the timetable names only one", async () => {
  render(<CourseMaterialsPage task={task} onOpenOutline={vi.fn()} onError={vi.fn()} />);

  const panel = await screen.findByRole("region", { name: "新课表待确认" });
  expect(within(panel).queryByLabelText("选择教学班")).not.toBeInTheDocument();
});

it("lets the teacher act on the warning that two teaching classes were merged", async () => {
  const user = userEvent.setup();
  getCourseReadiness.mockResolvedValue(readinessWith(registrarCandidate));
  remapScheduleCandidate.mockResolvedValue(registrarCandidate);
  render(<CourseMaterialsPage task={task} onOpenOutline={vi.fn()} onError={vi.fn()} />);

  const panel = await screen.findByRole("region", { name: "新课表待确认" });
  expect(within(panel).getByRole("alert")).toHaveTextContent("请选择一个教学班");
  await user.selectOptions(within(panel).getByLabelText("选择教学班"), "人工智能与创意设计-0002");

  expect(remapScheduleCandidate).toHaveBeenCalledWith(
    1,
    5,
    expect.objectContaining({ teaching_class: "人工智能与创意设计-0002" })
  );
});

it("can merge the teaching classes back together", async () => {
  const user = userEvent.setup();
  getCourseReadiness.mockResolvedValue(
    readinessWith({ ...registrarCandidate, teaching_class: "人工智能与创意设计-0002", warnings: [] })
  );
  remapScheduleCandidate.mockResolvedValue(registrarCandidate);
  render(<CourseMaterialsPage task={task} onOpenOutline={vi.fn()} onError={vi.fn()} />);

  const panel = await screen.findByRole("region", { name: "新课表待确认" });
  await user.selectOptions(within(panel).getByLabelText("选择教学班"), "全部教学班（合并）");

  expect(remapScheduleCandidate).toHaveBeenCalledWith(1, 5, expect.objectContaining({ teaching_class: "" }));
});

it("lets the teacher pick a different course from the same timetable", async () => {
  const user = userEvent.setup();
  remapScheduleCandidate.mockResolvedValue(candidate);
  render(<CourseMaterialsPage task={task} onOpenOutline={vi.fn()} onError={vi.fn()} />);

  const panel = await screen.findByRole("region", { name: "新课表待确认" });
  await user.selectOptions(within(panel).getByLabelText("按课程筛选"), "版式设计");

  expect(remapScheduleCandidate).toHaveBeenCalledWith(
    1,
    5,
    expect.objectContaining({ course_name: "版式设计" })
  );
});

it("keeps confirmation available and reports the change summary", async () => {
  const user = userEvent.setup();
  confirmScheduleCandidate.mockResolvedValue(candidate);
  render(<CourseMaterialsPage task={task} onOpenOutline={vi.fn()} onError={vi.fn()} />);

  const panel = await screen.findByRole("region", { name: "新课表待确认" });
  expect(within(panel).getByText(/新增 2/)).toBeInTheDocument();
  await user.click(within(panel).getByRole("button", { name: "确认使用新课表" }));

  expect(confirmScheduleCandidate).toHaveBeenCalledWith(1, 5);
});

it("offers the courses the timetable does list when none matches the course record", async () => {
  const user = userEvent.setup();
  Element.prototype.scrollIntoView = vi.fn();
  uploadScheduleCandidate
    .mockRejectedValueOnce(Object.assign(
      new Error("课表里没有和「人工智能与创意设计」对应的课次。课表中识别到的课程：版式设计、劳动教育。"),
      { courseNames: ["版式设计", "劳动教育"] }
    ))
    .mockResolvedValueOnce(candidate);
  const onError = vi.fn();
  render(<CourseMaterialsPage task={task} onOpenOutline={vi.fn()} onError={onError} />);

  const file = new File(["x"], "课表.xlsx", { type: "application/octet-stream" });
  await user.upload(await screen.findByLabelText("上传教务课表"), file);

  const alert = await screen.findByRole("alert", { name: "课表课程名不一致" });
  expect(alert).toHaveTextContent("课表中识别到的课程：版式设计、劳动教育");
  expect(onError).not.toHaveBeenCalled();

  await user.click(within(alert).getByRole("button", { name: "按「版式设计」导入" }));

  expect(uploadScheduleCandidate).toHaveBeenLastCalledWith(1, file, { course_name: "版式设计" });
  expect(screen.queryByRole("alert", { name: "课表课程名不一致" })).not.toBeInTheDocument();
});

it("still reports other upload failures through the page error", async () => {
  const user = userEvent.setup();
  uploadScheduleCandidate.mockRejectedValueOnce(new Error("课表缺少必需的列：节次。"));
  const onError = vi.fn();
  render(<CourseMaterialsPage task={task} onOpenOutline={vi.fn()} onError={onError} />);

  await user.upload(await screen.findByLabelText("上传教务课表"), new File(["x"], "课表.xlsx"));

  expect(onError).toHaveBeenCalledWith("课表缺少必需的列：节次。");
  expect(screen.queryByRole("alert", { name: "课表课程名不一致" })).not.toBeInTheDocument();
});

it("accepts the same file name a second time, as the registrar re-exports under one name", async () => {
  const user = userEvent.setup();
  Element.prototype.scrollIntoView = vi.fn();
  uploadScheduleCandidate.mockResolvedValue(candidate);
  render(<CourseMaterialsPage task={task} onOpenOutline={vi.fn()} onError={vi.fn()} />);

  const input = (await screen.findByLabelText("上传教务课表")) as HTMLInputElement;
  await user.upload(input, new File(["v1"], "1001张明课表.xls"));
  expect(uploadScheduleCandidate).toHaveBeenCalledTimes(1);
  // A file input only fires change when the selection differs from what it
  // still holds; clearing it is what lets the corrected export go through.
  expect(input.value).toBe("");
  expect(input.files).toHaveLength(0);

  await user.upload(input, new File(["v2"], "1001张明课表.xls"));
  expect(uploadScheduleCandidate).toHaveBeenCalledTimes(2);
});

it("tells the parent the course summary changed once the new timetable is confirmed", async () => {
  const user = userEvent.setup();
  confirmScheduleCandidate.mockResolvedValue({ ...candidate, status: "applied" });
  const onTaskChanged = vi.fn();
  render(<CourseMaterialsPage task={task} onOpenOutline={vi.fn()} onError={vi.fn()} onTaskChanged={onTaskChanged} />);

  const panel = await screen.findByRole("region", { name: "新课表待确认" });
  expect(onTaskChanged).not.toHaveBeenCalled();
  await user.click(within(panel).getByRole("button", { name: "确认使用新课表" }));

  expect(confirmScheduleCandidate).toHaveBeenCalledWith(1, 5);
  expect(onTaskChanged).toHaveBeenCalledTimes(1);
});
