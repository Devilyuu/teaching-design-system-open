import { RefreshCw, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { getLessonGenerationRun, retryLessonGenerationItem, startLessonGeneration } from "./api";
import type { LessonGenerationRun } from "./types";

function readStoredRun(storageKey: string): { id: number; run: LessonGenerationRun | null } | null {
  const raw = localStorage.getItem(storageKey);
  if (!raw) return null;

  try {
    const value: unknown = JSON.parse(raw);
    if (typeof value === "number" && Number.isFinite(value)) return { id: value, run: null };
    if (value && typeof value === "object" && "id" in value && typeof value.id === "number") {
      return { id: value.id, run: value as LessonGenerationRun };
    }
  } catch {
    const legacyId = Number(raw);
    if (Number.isFinite(legacyId) && legacyId > 0) return { id: legacyId, run: null };
  }

  return null;
}

function storeRun(storageKey: string, run: LessonGenerationRun) {
  localStorage.setItem(storageKey, JSON.stringify(run));
}


export default function LessonGenerationProgress({
  taskId,
  compact = false,
  onCompleted,
  onNotice,
  onError
}: {
  taskId: number;
  compact?: boolean;
  onCompleted: () => void;
  onNotice: (message: string) => void;
  onError: (message: string) => void;
}) {
  const storageKey = `lesson-generation-run:${taskId}`;
  const [run, setRun] = useState<LessonGenerationRun | null>(() => readStoredRun(storageKey)?.run ?? null);
  const [busy, setBusy] = useState(false);
  const completedRunId = useRef<number | null>(null);

  useEffect(() => {
    const stored = readStoredRun(storageKey);
    if (!stored) return;
    if (stored.run) setRun(stored.run);
    getLessonGenerationRun(taskId, stored.id)
      .then((value) => {
        setRun(value);
        storeRun(storageKey, value);
      })
      .catch(() => {
        if (!stored.run) localStorage.removeItem(storageKey);
      });
  }, [storageKey, taskId]);

  useEffect(() => {
    if (!run || !["pending", "running"].includes(run.status)) return;
    const timer = window.setTimeout(() => {
      getLessonGenerationRun(taskId, run.id).then((value) => {
        setRun(value);
        storeRun(storageKey, value);
      }).catch((reason: Error) => onError(reason.message));
    }, 2000);
    return () => window.clearTimeout(timer);
  }, [onError, run, storageKey, taskId]);

  useEffect(() => {
    if (!run || ["pending", "running"].includes(run.status) || completedRunId.current === run.id) return;
    completedRunId.current = run.id;
    onCompleted();
    onNotice(run.failed_items ? `已生成 ${run.succeeded_items} 次课，${run.failed_items} 次课需要重试` : `已生成 ${run.succeeded_items} 次课教案`);
  }, [onCompleted, onNotice, run]);

  async function start() {
    setBusy(true);
    onError("");
    try {
      const value = await startLessonGeneration(taskId);
      storeRun(storageKey, value);
      setRun(value);
      onNotice("已开始按课次生成整门课程教案");
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "教案生成启动失败");
    } finally {
      setBusy(false);
    }
  }

  async function retry(itemId: number) {
    setBusy(true);
    try {
      const value = await retryLessonGenerationItem(taskId, run!.id, itemId);
      completedRunId.current = null;
      storeRun(storageKey, value);
      setRun(value);
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "课次重试失败");
    } finally {
      setBusy(false);
    }
  }

  if (!run) {
    return <button className="btn primary" type="button" disabled={busy} onClick={start}><Sparkles className="icon" />{busy ? "正在启动" : "生成整门课教案"}</button>;
  }

  return (
    <div className={`generation-progress ${compact ? "compact" : ""}`} role="status" aria-label="教案生成进度" aria-live="polite">
      <div className="generation-summary">
        <strong>{run.succeeded_items}/{run.total_items} 次课已生成</strong>
        <span className={`tag ${run.failed_items ? "rose" : "green"}`}>{run.status === "running" ? "生成中" : run.failed_items ? `${run.failed_items} 次失败` : "已完成"}</span>
        {!compact && !["pending", "running"].includes(run.status) && <button className="btn" type="button" onClick={start}><RefreshCw className="icon" />新建生成任务</button>}
      </div>
      <progress aria-label="教案生成进度" max={run.total_items} value={run.succeeded_items} />
      {!compact && run.items.some((item) => item.status === "failed") && (
        <div className="generation-failures">
          {run.items.filter((item) => item.status === "failed").map((item, index) => (
            <div key={item.id}><span>失败课次 {index + 1} · {item.error_code}</span><button className="btn" type="button" disabled={busy} onClick={() => retry(item.id)}>重试</button></div>
          ))}
        </div>
      )}
    </div>
  );
}
