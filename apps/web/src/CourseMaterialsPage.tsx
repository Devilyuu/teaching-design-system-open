import { useEffect, useState } from "react";
import { CheckCircle2, FileText, Upload } from "lucide-react";

import {
  confirmScheduleCandidate,
  confirmSources,
  discardScheduleCandidate,
  getCourseReadiness,
  generateOutline,
  remapScheduleCandidate,
  resolveReviewNotice,
  uploadCourseStandard,
  uploadScheduleCandidate,
  uploadTalentPlan,
  uploadTemplate
} from "./api";
import type { CourseReadiness, ScheduleCandidate, ScheduleField, TeachingTask } from "./types";

const materialDefinitions = [
  ["talent_plan", "人才培养方案", ".docx"],
  ["course_standard", "课程标准", ".docx"],
  // The registrar exports the old OLE2 .xls; teachers should not have to
  // re-save it as .xlsx before the picker will let them choose it.
  ["schedule", "教务课表", ".xlsx,.xls"],
  ["outline_template", "课程实施大纲模板", ".docx"],
  ["lesson_template", "教案模板", ".docx"]
] as const;

const scheduleFieldLabels: Array<[ScheduleField, string]> = [
  ["week_no", "周次"],
  ["date_text", "日期"],
  ["weekday", "星期"],
  ["periods", "节次"],
  ["course_name", "课程"],
  ["class_name", "班级"],
  ["location", "地点"]
];

const confidenceLabels = { exact: "自动识别", alias: "按别名识别", manual: "手动指定" } as const;

const SCHEDULE_PANEL_ID = "schedule-candidate-panel";

/** The confirm panel sits below the material list, where an upload does not look like it landed. */
function revealSchedulePanel() {
  const panel = document.getElementById(SCHEDULE_PANEL_ID);
  if (typeof panel?.scrollIntoView === "function") {
    panel.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function SchedulePreviewPanel({ taskId, candidate, onReload, onError }: {
  taskId: number;
  candidate: ScheduleCandidate;
  onReload: () => Promise<void>;
  onError: (message: string) => void;
}) {
  const [editingColumns, setEditingColumns] = useState(false);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState<Partial<Record<ScheduleField, number>>>({});

  const mapping = Object.fromEntries(
    candidate.matches.map((match) => [match.field, match.column_index])
  ) as Partial<Record<ScheduleField, number>>;
  const current = { ...mapping, ...draft };

  async function remap(overrides: {
    mapping?: Partial<Record<ScheduleField, number>>;
    course_name?: string;
    teaching_class?: string;
  }) {
    setBusy(true);
    try {
      await remapScheduleCandidate(taskId, candidate.id, {
        header_row: candidate.header_row,
        mapping: overrides.mapping ?? current,
        course_name: overrides.course_name ?? candidate.course_filter,
        teaching_class: overrides.teaching_class ?? candidate.teaching_class
      });
      setEditingColumns(false);
      setDraft({});
      await onReload();
    } catch (error) {
      onError(error instanceof Error ? error.message : "重新识别课表失败");
    } finally {
      setBusy(false);
    }
  }

  async function run(action: () => Promise<unknown>, failure: string) {
    setBusy(true);
    try {
      await action();
      await onReload();
    } catch (error) {
      onError(error instanceof Error ? error.message : failure);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="schedule-candidate-panel" id={SCHEDULE_PANEL_ID} aria-label="新课表待确认">
      <div className="schedule-candidate-head">
        <div>
          <strong>新课表待确认</strong>
          <p>
            {candidate.filename} · 识别到第 {candidate.header_row + 1} 行为表头 · 共 {candidate.session_count} 次课 /{" "}
            {candidate.total_hours} 学时
          </p>
        </div>
        <p className="schedule-change-summary">
          新增 {candidate.added_count}，删除 {candidate.removed_count}，变更 {candidate.changed_count} 次课
        </p>
      </div>

      {candidate.warnings.map((warning) => (
        <p className="inline-alert" role="alert" key={warning}>{warning}</p>
      ))}

      {candidate.course_names.length > 1 && (
        <label className="schedule-course-filter">
          <span>按课程筛选</span>
          <select
            aria-label="按课程筛选"
            value={candidate.course_filter}
            disabled={busy}
            onChange={(event) => void remap({ course_name: event.target.value })}
          >
            {candidate.course_names.map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
        </label>
      )}

      {candidate.teaching_classes.length > 1 && (
        <label className="schedule-course-filter">
          <span>选择教学班</span>
          <select
            aria-label="选择教学班"
            value={candidate.teaching_class}
            disabled={busy}
            onChange={(event) => void remap({ teaching_class: event.target.value })}
          >
            <option value="">全部教学班（合并）</option>
            {candidate.teaching_classes.map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
        </label>
      )}

      <table className="schedule-mapping-table" aria-label="课表列对应关系">
        <thead>
          <tr><th scope="col">系统字段</th><th scope="col">读取的列</th><th scope="col">识别方式</th></tr>
        </thead>
        <tbody>
          {scheduleFieldLabels.map(([field, label]) => {
            const match = candidate.matches.find((item) => item.field === field);
            return (
              <tr key={field}>
                <th scope="row">{label}</th>
                <td>{match ? match.header_text : "未识别，已按规则推算"}</td>
                <td>
                  {editingColumns ? (
                    <select
                      aria-label={`${label}对应的列`}
                      value={current[field] ?? ""}
                      onChange={(event) => setDraft((previous) => ({
                        ...previous,
                        [field]: Number(event.target.value)
                      }))}
                    >
                      <option value="">不使用</option>
                      {candidate.detected_headers.map((header, index) => (
                        <option key={`${header}-${index}`} value={index}>{header}</option>
                      ))}
                    </select>
                  ) : (
                    match ? confidenceLabels[match.confidence] : "—"
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {candidate.unmapped_headers.length > 0 && (
        <p className="schedule-unmapped">未使用的列：{candidate.unmapped_headers.join("、")}</p>
      )}

      <table className="schedule-preview-table" aria-label="课次预览">
        <thead>
          <tr>
            <th scope="col">课次</th><th scope="col">周次</th><th scope="col">日期</th><th scope="col">星期</th>
            <th scope="col">节次</th><th scope="col">班级</th><th scope="col">地点</th>
          </tr>
        </thead>
        <tbody>
          {candidate.sessions.map((item) => (
            <tr key={item.session_no}>
              <td>{item.session_no}</td><td>{item.week_no}</td><td>{item.date_text}</td><td>{item.weekday}</td>
              <td>{item.periods}</td><td>{item.class_name}</td><td>{item.location}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {candidate.blocking_message && <p className="inline-alert" role="alert">{candidate.blocking_message}</p>}

      <div className="status-line">
        <button
          className="btn primary"
          disabled={!candidate.can_confirm || busy}
          onClick={() => void run(() => confirmScheduleCandidate(taskId, candidate.id), "确认课表失败")}
        >
          确认使用新课表
        </button>
        {editingColumns ? (
          <>
            <button className="btn" disabled={busy} onClick={() => void remap({})}>按新的对应关系重新识别</button>
            <button className="btn" disabled={busy} onClick={() => { setEditingColumns(false); setDraft({}); }}>取消</button>
          </>
        ) : (
          <button className="btn" disabled={busy} onClick={() => setEditingColumns(true)}>重新指定列</button>
        )}
        <button
          className="btn"
          disabled={busy}
          onClick={() => void run(() => discardScheduleCandidate(taskId, candidate.id), "放弃课表失败")}
        >
          放弃
        </button>
      </div>
    </section>
  );
}

export default function CourseMaterialsPage({ task, onOpenOutline, onError }: {
  task: TeachingTask;
  onOpenOutline: () => void;
  onError: (message: string) => void;
}) {
  const [readiness, setReadiness] = useState<CourseReadiness | null>(null);
  const [busy, setBusy] = useState("");

  async function reload() {
    setReadiness(await getCourseReadiness(task.id));
  }

  useEffect(() => { void reload().catch((error: Error) => onError(error.message)); }, [task.id]);

  async function upload(kind: string, file: File) {
    setBusy(kind);
    try {
      if (kind === "talent_plan") await uploadTalentPlan(task.id, file);
      if (kind === "course_standard") await uploadCourseStandard(task.id, file);
      if (kind === "schedule") await uploadScheduleCandidate(task.id, file);
      if (kind === "outline_template") await uploadTemplate(task.id, "outline", file);
      if (kind === "lesson_template") await uploadTemplate(task.id, "lesson", file);
      await reload();
      // A timetable is not accepted until it is confirmed, and the panel that
      // asks is off-screen; leaving the teacher on the list reads as failure.
      if (kind === "schedule") revealSchedulePanel();
    } catch (error) {
      onError(error instanceof Error ? error.message : "资料上传失败");
    } finally {
      setBusy("");
    }
  }

  async function runPrimaryAction() {
    setBusy("primary");
    try {
      if (readiness?.next_action === "confirm_sources") await confirmSources(task.id);
      if (readiness?.next_action === "generate_outline") {
        await generateOutline(task.id);
        onOpenOutline();
      }
      await reload();
    } catch (error) {
      onError(error instanceof Error ? error.message : "操作失败");
    } finally {
      setBusy("");
    }
  }

  if (!readiness) return <div className="session-loading">正在读取课程资料...</div>;

  const readyMaterialCount = materialDefinitions.filter(([kind]) => readiness.materials[kind].status === "ready").length;
  const readinessTitle = readiness.blocking_reasons.length
    ? `还需完成 ${readiness.blocking_reasons.length} 项`
    : "课程资料已就绪";

  return (
    <section className="course-materials-page">
      <div className="page-section-head">
        <div><h3>课程资料与生成准备</h3><p>补齐或替换资料后，系统会重新核对生成条件。</p></div>
        {readiness.next_action === "open_outline" && <button className="btn" onClick={onOpenOutline}>查看已有课程实施大纲</button>}
        {readiness.next_action === "confirm_sources" && <button className="btn primary" disabled={!readiness.source_review.can_confirm || busy === "primary"} onClick={() => void runPrimaryAction()}>确认课程依据</button>}
        {readiness.next_action === "generate_outline" && <button className="btn primary" disabled={busy === "primary"} onClick={() => void runPrimaryAction()}>AI 生成课程实施大纲</button>}
      </div>
      <div
        className={`readiness-band ${readiness.blocking_reasons.length ? "attention" : "ready"}`}
        role="status"
        aria-label={readinessTitle}
      >
        <span className="readiness-icon"><CheckCircle2 aria-hidden="true" /></span>
        <div>
          <strong>{readinessTitle}</strong>
          <p>{readiness.blocking_reasons.length ? "完成以下事项后，可继续确认课程依据并生成文档。" : "课程依据已确认，可以继续查看或生成课程文档。"}</p>
          {readiness.blocking_reasons.length > 0 && (
            <ul className="readiness-list">
              {readiness.blocking_reasons.map((item) => <li key={item.code}>{item.message}</li>)}
            </ul>
          )}
        </div>
      </div>
      <section className="material-section" aria-labelledby="course-material-list-title">
        <div className="material-list-head">
          <div><h4 id="course-material-list-title">课程资料清单</h4><p>系统按这些资料核对课程目标、排课与文档格式。</p></div>
          <span>{readyMaterialCount}/{materialDefinitions.length} 项已就绪</span>
        </div>
        <div className="material-work-list" role="list">
          {materialDefinitions.map(([kind, label, accept]) => {
            const state = readiness.materials[kind];
            const awaiting = state.status === "awaiting_confirmation";
            return <div className="material-work-row" role="listitem" key={kind}>
              <FileText aria-hidden="true" />
              <div>
                <strong>{label}</strong>
                <p>{awaiting ? `${state.filename}｜${state.message}` : state.filename || state.message}</p>
                {state.status === "ready" && <small>替换后将重新核对生成条件</small>}
              </div>
              <span className={`tag ${state.status === "ready" ? "green" : "amber"}`}>
                {state.status === "ready" ? "已就绪" : awaiting ? "待确认" : "待补充"}
              </span>
              <div className="material-row-actions">
                {/* Re-uploading stays available: a pending timetable may be the wrong file. */}
                {awaiting && <button className="btn primary" onClick={revealSchedulePanel}>去确认</button>}
                <label className={`btn material-upload ${busy === kind ? "disabled" : ""}`}><Upload className="icon" />{busy === kind ? "上传中" : state.status === "ready" || awaiting ? "替换" : "上传"}
                  <input aria-label={`上传${label}`} type="file" accept={accept} disabled={busy === kind} onChange={(event) => { const file = event.target.files?.[0]; if (file) void upload(kind, file); }} />
                </label>
              </div>
            </div>;
          })}
        </div>
      </section>
      {readiness.pending_schedule && (
        <SchedulePreviewPanel
          taskId={task.id}
          candidate={readiness.pending_schedule}
          onReload={reload}
          onError={onError}
        />
      )}
      {readiness.review_notices.map((notice) => <div className="review-notice" key={notice.id}><span>{notice.reason}</span><button className="btn" onClick={async () => { await resolveReviewNotice(task.id, notice.id); await reload(); }}>已完成复核</button></div>)}
    </section>
  );
}
