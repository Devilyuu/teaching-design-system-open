import { useEffect, useState } from "react";
import { Download, FileClock, Share2 } from "lucide-react";

import { downloadExport, getWorkbenchStatus, listExports, pushExportToWorkbench } from "./api";
import type { ExportRecord } from "./types";

// What the workbench files as a deliverable, matching the API. Session
// materials stay here until there is a reason for them to travel.
const PUSHABLE_ARTIFACTS = ["lesson", "outline"];

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function formatMoment(value: string): string {
  const moment = new Date(value);
  if (Number.isNaN(moment.getTime())) return value;
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${moment.getFullYear()}-${pad(moment.getMonth() + 1)}-${pad(moment.getDate())} ${pad(moment.getHours())}:${pad(moment.getMinutes())}`;
}

export default function ExportHistoryPanel({ taskId, reloadToken, onError }: {
  taskId: number;
  reloadToken: number;
  onError: (message: string) => void;
}) {
  const [records, setRecords] = useState<ExportRecord[] | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [pushingId, setPushingId] = useState<number | null>(null);
  const [workbench, setWorkbench] = useState(false);
  const [pushed, setPushed] = useState("");

  useEffect(() => {
    let active = true;
    listExports(taskId)
      .then((result) => { if (active) setRecords(result); })
      .catch((error: Error) => onError(error.message));
    return () => { active = false; };
  }, [taskId, reloadToken]);

  // The workbench belongs to one teacher on a deployment everyone shares, so
  // ask whether it is this one's before offering the button.
  useEffect(() => {
    let active = true;
    getWorkbenchStatus()
      .then((status) => {
        if (!active) return;
        setWorkbench(status.configured);
        if (status.message) onError(status.message);
      })
      .catch(() => { if (active) setWorkbench(false); });
    return () => { active = false; };
  }, []);

  async function pushToWorkbench(record: ExportRecord) {
    setPushingId(record.id);
    setPushed("");
    try {
      const result = await pushExportToWorkbench(taskId, record.id);
      setPushed(result.replaced ? "已更新工作台里的这份文档" : "已送入工作台，待你在那边引用为成果");
    } catch (error) {
      onError(error instanceof Error ? error.message : "推送到工作台失败");
    } finally {
      setPushingId(null);
    }
  }

  async function redownload(record: ExportRecord) {
    setBusyId(record.id);
    try {
      const { blob, filename } = await downloadExport(taskId, record.id);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      onError(error instanceof Error ? error.message : "重新下载失败");
    } finally {
      setBusyId(null);
    }
  }

  if (!records) return <div className="session-loading">正在读取导出记录...</div>;

  return (
    <section className="export-history" aria-labelledby="export-history-title">
      <div className="page-section-head">
        <div>
          <h3 id="export-history-title">导出记录</h3>
          <p>每次导出都会留档，可以查看当时使用的模板与依据，并重新下载同一份文件。</p>
        </div>
      </div>
      {pushed && <p className="inline-notice" role="status">{pushed}</p>}
      {records.length === 0 ? (
        <div className="empty-state">
          <FileClock aria-hidden="true" />
          <strong>还没有导出记录</strong>
          <p>导出课程实施大纲、整门课教案或课次材料后，会在这里留档。</p>
        </div>
      ) : (
        <ul className="export-history-list" role="list">
          {records.map((record) => (
            <li className="export-history-row" key={record.id}>
              <div className="export-history-main">
                <div className="status-line">
                  <span className="tag">{record.artifact_label}</span>
                  <strong>{record.filename}</strong>
                </div>
                <p>
                  {formatMoment(record.created_at)} · {record.exported_by} · {formatSize(record.size_bytes)}
                </p>
                <p className="export-history-source">
                  {record.source_summary}
                  {record.template_filename && ` · 模板：${record.template_filename}`}
                </p>
              </div>
              {record.available ? (
                <div className="export-history-actions">
                  <button
                    className="btn"
                    disabled={busyId === record.id}
                    onClick={() => void redownload(record)}
                  >
                    <Download className="icon" />
                    {busyId === record.id ? "下载中" : "重新下载"}
                  </button>
                  {workbench && PUSHABLE_ARTIFACTS.includes(record.artifact_type) && (
                    <button
                      className="btn"
                      disabled={pushingId === record.id}
                      onClick={() => void pushToWorkbench(record)}
                    >
                      <Share2 className="icon" />
                      {pushingId === record.id ? "推送中" : "推送到工作台"}
                    </button>
                  )}
                </div>
              ) : (
                <span className="tag amber">文件已清理</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
