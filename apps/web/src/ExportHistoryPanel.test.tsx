import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";

import ExportHistoryPanel from "./ExportHistoryPanel";
import type { ExportRecord } from "./types";

const listExports = vi.fn();
const downloadExport = vi.fn();
const getWorkbenchStatus = vi.fn();
const pushExportToWorkbench = vi.fn();

vi.mock("./api", () => ({
  listExports: (...args: unknown[]) => listExports(...args),
  downloadExport: (...args: unknown[]) => downloadExport(...args),
  getWorkbenchStatus: (...args: unknown[]) => getWorkbenchStatus(...args),
  pushExportToWorkbench: (...args: unknown[]) => pushExportToWorkbench(...args)
}));

const outlineRecord: ExportRecord = {
  id: 21,
  artifact_type: "outline",
  artifact_label: "课程实施大纲",
  filename: "人工智能与创意设计_课程实施大纲.docx",
  size_bytes: 45056,
  template_filename: "课程实施大纲模板.docx",
  source_summary: "8 行课程实施大纲，课程依据已确认",
  session_no: null,
  exported_by: "张明",
  created_at: "2026-08-07T02:30:00Z",
  available: true
};

const staleRecord: ExportRecord = {
  ...outlineRecord,
  id: 20,
  artifact_type: "lesson",
  artifact_label: "整门课教案",
  filename: "人工智能与创意设计_教案.docx",
  template_filename: "教案模板.docx",
  source_summary: "8 份教案",
  available: false
};

const lessonRecord: ExportRecord = {
  ...staleRecord,
  id: 22,
  available: true
};

beforeEach(() => {
  vi.clearAllMocks();
  listExports.mockResolvedValue([outlineRecord, staleRecord]);
  getWorkbenchStatus.mockResolvedValue({ configured: false, message: "" });
});

it("shows which template and evidence produced each document", async () => {
  render(<ExportHistoryPanel taskId={1} reloadToken={0} onError={vi.fn()} />);

  const rows = await screen.findAllByRole("listitem");
  expect(rows).toHaveLength(2);
  expect(within(rows[0]).getByText("人工智能与创意设计_课程实施大纲.docx")).toBeInTheDocument();
  expect(within(rows[0]).getByText(/课程实施大纲模板\.docx/)).toBeInTheDocument();
  expect(within(rows[0]).getByText(/8 行课程实施大纲，课程依据已确认/)).toBeInTheDocument();
  expect(within(rows[0]).getByText(/张明/)).toBeInTheDocument();
  expect(within(rows[0]).getByText(/44 KB/)).toBeInTheDocument();
});

it("re-downloads a retained document without regenerating it", async () => {
  const user = userEvent.setup();
  downloadExport.mockResolvedValue({ blob: new Blob(["x"]), filename: "大纲.docx" });
  vi.stubGlobal("URL", { createObjectURL: vi.fn(() => "blob:export"), revokeObjectURL: vi.fn() });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  render(<ExportHistoryPanel taskId={1} reloadToken={0} onError={vi.fn()} />);

  const rows = await screen.findAllByRole("listitem");
  await user.click(within(rows[0]).getByRole("button", { name: "重新下载" }));

  expect(downloadExport).toHaveBeenCalledWith(1, 21);
});

it("marks a record whose file is gone instead of offering a broken download", async () => {
  render(<ExportHistoryPanel taskId={1} reloadToken={0} onError={vi.fn()} />);

  const rows = await screen.findAllByRole("listitem");
  expect(within(rows[1]).getByText("文件已清理")).toBeInTheDocument();
  expect(within(rows[1]).queryByRole("button", { name: "重新下载" })).not.toBeInTheDocument();
});

it("explains the empty state before anything has been exported", async () => {
  listExports.mockResolvedValue([]);
  render(<ExportHistoryPanel taskId={1} reloadToken={0} onError={vi.fn()} />);

  expect(await screen.findByText("还没有导出记录")).toBeInTheDocument();
});

it("offers no workbench push where this deployment has none", async () => {
  listExports.mockResolvedValue([outlineRecord, lessonRecord]);
  render(<ExportHistoryPanel taskId={1} reloadToken={0} onError={vi.fn()} />);

  const rows = await screen.findAllByRole("listitem");
  expect(within(rows[1]).queryByRole("button", { name: "推送到工作台" })).not.toBeInTheDocument();
});

it("pushes both deliverables, and says the workbench record was replaced", async () => {
  const user = userEvent.setup();
  listExports.mockResolvedValue([outlineRecord, lessonRecord]);
  getWorkbenchStatus.mockResolvedValue({ configured: true, message: "" });
  pushExportToWorkbench.mockResolvedValue({ id: "abc", status: "RECEIVED", created: false, replaced: true });
  render(<ExportHistoryPanel taskId={1} reloadToken={0} onError={vi.fn()} />);

  const rows = await screen.findAllByRole("listitem");
  // 大纲 and 教案 both travel; each files under its own workbench record.
  await user.click(within(rows[0]).getByRole("button", { name: "推送到工作台" }));
  expect(pushExportToWorkbench).toHaveBeenCalledWith(1, 21);

  await user.click(within(rows[1]).getByRole("button", { name: "推送到工作台" }));
  expect(pushExportToWorkbench).toHaveBeenCalledWith(1, 22);
  expect(await screen.findByRole("status")).toHaveTextContent("已更新工作台里的这份文档");
});

it("surfaces a half-set workbench configuration instead of quietly hiding the button", async () => {
  const onError = vi.fn();
  getWorkbenchStatus.mockResolvedValue({ configured: false, message: "工作台回流配置不完整" });
  render(<ExportHistoryPanel taskId={1} reloadToken={0} onError={onError} />);

  await screen.findAllByRole("listitem");
  expect(onError).toHaveBeenCalledWith("工作台回流配置不完整");
});

it("reloads the history when a new export happens", async () => {
  const { rerender } = render(<ExportHistoryPanel taskId={1} reloadToken={0} onError={vi.fn()} />);
  await screen.findAllByRole("listitem");

  rerender(<ExportHistoryPanel taskId={1} reloadToken={1} onError={vi.fn()} />);

  expect(listExports).toHaveBeenCalledTimes(2);
});
