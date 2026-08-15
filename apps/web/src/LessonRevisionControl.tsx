import { Sparkles, X } from "lucide-react";
import { useState } from "react";

import { acceptLessonRevisionCandidate, createLessonRevisionCandidate, rejectLessonRevisionCandidate } from "./api";
import type { LessonRevisionCandidate, LessonRevisionField } from "./types";


export default function LessonRevisionControl({ taskId, lessonId, fieldName, onAccepted, onError }: {
  taskId: number;
  lessonId: number;
  fieldName: LessonRevisionField;
  onAccepted: (content: string) => void;
  onError: (message: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [instruction, setInstruction] = useState("");
  const [candidate, setCandidate] = useState<LessonRevisionCandidate | null>(null);
  const [busy, setBusy] = useState(false);

  async function generate() {
    setBusy(true);
    try {
      setCandidate(await createLessonRevisionCandidate(taskId, lessonId, fieldName, instruction));
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "智能重写失败");
    } finally {
      setBusy(false);
    }
  }

  async function accept() {
    if (!candidate) return;
    setBusy(true);
    try {
      const accepted = await acceptLessonRevisionCandidate(taskId, candidate.id);
      onAccepted(accepted.proposed_content);
      setCandidate(null);
      setOpen(false);
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "候选内容应用失败");
    } finally {
      setBusy(false);
    }
  }

  async function reject() {
    if (candidate) await rejectLessonRevisionCandidate(taskId, candidate.id).catch(() => undefined);
    setCandidate(null);
    setOpen(false);
  }

  if (!open) return <button className="text-action" type="button" onClick={() => setOpen(true)}><Sparkles className="icon" />智能重写</button>;

  return (
    <div className="revision-control">
      {!candidate ? <>
        <input aria-label="智能重写要求" value={instruction} placeholder="可选：例如增加艺术设计实践环节" onChange={(event) => setInstruction(event.target.value)} />
        <button className="btn" type="button" disabled={busy} onClick={generate}>{busy ? "生成中" : "生成候选"}</button>
        <button className="icon-btn" title="取消" type="button" onClick={() => setOpen(false)}><X className="icon" /></button>
      </> : <div className="revision-comparison">
        <strong>智能建议</strong><p>{candidate.proposed_content}</p>
        <div className="form-actions"><button className="btn primary" type="button" disabled={busy} onClick={accept}>采用</button><button className="btn" type="button" onClick={reject}>放弃</button></div>
      </div>}
    </div>
  );
}
