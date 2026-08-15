import { ArrowLeft, CheckCircle2, Download, RotateCcw, Save, Sparkles, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  applyPostClassReflection,
  deletePostClassReflection,
  deleteSessionMaterial,
  exportSessionMaterial,
  generateSessionMaterial,
  getSessionWorkspace,
  revertPostClassReflection,
  upsertPostClassReflection,
  updateLessonPlan,
  updateSessionMaterial
} from "./api";
import type {
  LessonPlan,
  PostClassReflectionInput,
  SessionMaterial,
  SessionMaterialDifficulty,
  SessionMaterialType,
  SessionWorkspace,
  TeachingTask
} from "./types";

interface SessionWorkspacePageProps {
  task: TeachingTask;
  outlineRowId: number;
  onBack: () => void;
  onNotice: (message: string) => void;
  onError: (message: string) => void;
  onStatusChange: () => void;
}

const difficultyLabels: Record<SessionMaterialDifficulty, string> = {
  basic: "基础",
  medium: "适中",
  advanced: "提高"
};

const defaultReflection: PostClassReflectionInput = {
  progress_status: "completed",
  mastery_level: "good",
  classroom_effect: "smooth",
  note: ""
};

const progressOptions = [
  { value: "completed", label: "已完成" },
  { value: "partial", label: "部分完成" },
  { value: "not_completed", label: "未完成" }
];
const masteryOptions = [
  { value: "good", label: "良好" },
  { value: "average", label: "一般" },
  { value: "weak", label: "较弱" }
];
const effectOptions = [
  { value: "smooth", label: "顺畅" },
  { value: "normal", label: "基本正常" },
  { value: "needs_adjustment", label: "需要调整" }
];

export default function SessionWorkspacePage({
  task,
  outlineRowId,
  onBack,
  onNotice,
  onError,
  onStatusChange
}: SessionWorkspacePageProps) {
  const [workspace, setWorkspace] = useState<SessionWorkspace | null>(null);
  const [selectedMaterialId, setSelectedMaterialId] = useState<number | null>(null);
  const [materialType, setMaterialType] = useState<SessionMaterialType>("assignment");
  const [difficulty, setDifficulty] = useState<SessionMaterialDifficulty>("medium");
  const [estimatedMinutes, setEstimatedMinutes] = useState(40);
  const [questionCount, setQuestionCount] = useState(5);
  const [reflectionDraft, setReflectionDraft] = useState<PostClassReflectionInput>(defaultReflection);
  const [busy, setBusy] = useState(false);
  const [generatingMaterial, setGeneratingMaterial] = useState(false);
  const [lessonDirty, setLessonDirty] = useState(false);
  const [dirtyMaterialIds, setDirtyMaterialIds] = useState<Set<number>>(() => new Set());

  useEffect(() => {
    let active = true;
    setWorkspace(null);
    getSessionWorkspace(task.id, outlineRowId)
      .then((data) => {
        if (!active) return;
        setWorkspace(data);
        setLessonDirty(false);
        setDirtyMaterialIds(new Set());
        setSelectedMaterialId(data.materials[0]?.id ?? null);
        if (data.reflection) {
          setReflectionDraft({
            progress_status: data.reflection.progress_status,
            mastery_level: data.reflection.mastery_level,
            classroom_effect: data.reflection.classroom_effect,
            note: data.reflection.note
          });
        } else {
          setReflectionDraft(defaultReflection);
        }
      })
      .catch((reason: Error) => {
        if (active) onError(reason.message);
      });
    return () => {
      active = false;
    };
  }, [task.id, outlineRowId, onError]);

  const selectedMaterial = useMemo(
    () => workspace?.materials.find((item) => item.id === selectedMaterialId) ?? null,
    [workspace, selectedMaterialId]
  );

  function patchLesson(patch: Partial<LessonPlan>) {
    setLessonDirty(true);
    setWorkspace((current) => current?.lesson
      ? { ...current, lesson: { ...current.lesson, ...patch } }
      : current);
  }

  function patchMaterial(patch: Partial<SessionMaterial>) {
    if (!selectedMaterialId) return;
    setDirtyMaterialIds((current) => new Set(current).add(selectedMaterialId));
    setWorkspace((current) => current
      ? {
          ...current,
          materials: current.materials.map((item) => item.id === selectedMaterialId ? { ...item, ...patch } : item)
        }
      : current);
  }

  async function saveLesson() {
    if (!workspace?.lesson) return;
    setBusy(true);
    try {
      const saved = await updateLessonPlan(task.id, workspace.lesson);
      setWorkspace((current) => current ? { ...current, lesson: saved } : current);
      setLessonDirty(false);
      onNotice(`第 ${saved.session_no} 次课教案已保存`);
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "教案保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function generateMaterial() {
    setBusy(true);
    setGeneratingMaterial(true);
    try {
      const generated = await generateSessionMaterial(task.id, outlineRowId, {
        material_type: materialType,
        difficulty,
        estimated_minutes: estimatedMinutes,
        question_count: questionCount
      });
      setWorkspace((current) => current
        ? { ...current, materials: [...current.materials, generated] }
        : current);
      setSelectedMaterialId(generated.id);
      onNotice(`已生成${materialType === "assignment" ? "作业" : "测试"}草稿`);
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "材料生成失败");
    } finally {
      setGeneratingMaterial(false);
      setBusy(false);
    }
  }

  async function saveMaterial() {
    if (!selectedMaterial) return;
    setBusy(true);
    try {
      const saved = await updateSessionMaterial(task.id, selectedMaterial);
      setWorkspace((current) => current
        ? { ...current, materials: current.materials.map((item) => item.id === saved.id ? saved : item) }
        : current);
      setDirtyMaterialIds((current) => {
        const next = new Set(current);
        next.delete(saved.id);
        return next;
      });
      onNotice("备课材料已保存");
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "材料保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function downloadMaterial() {
    if (!selectedMaterial) return;
    if ((!selectedMaterial.course_goal_codes || !selectedMaterial.ability_codes)
      && !window.confirm("当前材料缺少课程目标或能力指标代码，仍要导出吗？")) return;
    setBusy(true);
    try {
      const { blob, filename } = await exportSessionMaterial(task.id, selectedMaterial.id);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      anchor.click();
      URL.revokeObjectURL(url);
      onNotice(`已导出：${filename}`);
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "材料导出失败");
    } finally {
      setBusy(false);
    }
  }

  async function removeMaterial() {
    if (!selectedMaterial || !window.confirm("确定删除这份备课材料吗？")) return;
    setBusy(true);
    try {
      await deleteSessionMaterial(task.id, selectedMaterial.id);
      setWorkspace((current) => {
        if (!current) return current;
        const materials = current.materials.filter((item) => item.id !== selectedMaterial.id);
        setDirtyMaterialIds((dirtyIds) => {
          const next = new Set(dirtyIds);
          next.delete(selectedMaterial.id);
          return next;
        });
        setSelectedMaterialId(materials[0]?.id ?? null);
        return { ...current, materials };
      });
      onNotice("备课材料已删除");
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "材料删除失败");
    } finally {
      setBusy(false);
    }
  }

  async function saveReflection() {
    setBusy(true);
    try {
      const reflection = await upsertPostClassReflection(task.id, outlineRowId, reflectionDraft);
      setWorkspace((current) => current ? { ...current, reflection } : current);
      onStatusChange();
      onNotice("课后记录已保存");
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "课后记录保存失败");
    } finally {
      setBusy(false);
    }
  }

  async function applyReflection() {
    if (!workspace?.reflection) return;
    setBusy(true);
    try {
      const lesson = await applyPostClassReflection(task.id, workspace.reflection.id);
      setWorkspace((current) => current?.reflection ? {
        ...current,
        reflection: {
          ...current.reflection,
          status: "applied",
          applied_lesson_plan_id: lesson.id,
          applied_at: new Date().toISOString()
        }
      } : current);
      onStatusChange();
      onNotice("调整建议已应用到下次课教案");
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "调整建议应用失败");
    } finally {
      setBusy(false);
    }
  }

  async function revertReflection() {
    if (!workspace?.reflection) return;
    setBusy(true);
    try {
      await revertPostClassReflection(task.id, workspace.reflection.id);
      setWorkspace((current) => current?.reflection ? {
        ...current,
        reflection: {
          ...current.reflection,
          status: "reverted",
          applied_lesson_plan_id: null,
          reverted_at: new Date().toISOString()
        }
      } : current);
      onStatusChange();
      onNotice("已撤销对下次课教案的调整");
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "撤销失败");
    } finally {
      setBusy(false);
    }
  }

  async function removeReflection() {
    if (!workspace?.reflection || !window.confirm("确定删除这条课后记录吗？")) return;
    setBusy(true);
    try {
      await deletePostClassReflection(task.id, workspace.reflection.id);
      setWorkspace((current) => current ? { ...current, reflection: null } : current);
      setReflectionDraft(defaultReflection);
      onStatusChange();
      onNotice("课后记录已删除");
    } catch (reason) {
      onError(reason instanceof Error ? reason.message : "课后记录删除失败");
    } finally {
      setBusy(false);
    }
  }

  if (!workspace) return <div className="session-loading">正在加载本次课...</div>;
  const { outline, lesson, materials } = workspace;

  return (
    <section className="session-workspace">
      <div className="session-workspace-head">
        <button className="btn icon-text" onClick={onBack}><ArrowLeft className="icon" />返回全部课次</button>
        <div>
          <span className="tag">第 {outline.session_no} 次课</span>
          <h3>{outline.topic}</h3>
          <p>{outline.date_text} · {outline.weekday} · 第 {outline.periods} 节</p>
        </div>
      </div>

      <section className="session-context" aria-labelledby="session-context-title">
        <div>
          <h3 id="session-context-title">本次课概况</h3>
          <p>{outline.teaching_content}</p>
        </div>
        <dl>
          <div><dt>课程目标</dt><dd>{outline.course_goal_codes || "未填写"}</dd></div>
          <div><dt>能力指标</dt><dd>{outline.ability_codes || "未填写"}</dd></div>
          <div><dt>生成依据</dt><dd>{lesson ? "已引用教案" : "未引用教案"}</dd></div>
        </dl>
      </section>

      <section className="session-lesson-section">
        <div className="section-title-row">
          <div><h3>本次教案</h3><span className={lessonDirty ? "save-state dirty" : "save-state"} role="status" aria-label="本次教案保存状态">{lesson ? lessonDirty ? "本次教案有未保存修改" : "本次教案已保存" : "尚未生成"}</span></div>
          {lesson && <button className="btn primary" disabled={busy || !lessonDirty} onClick={saveLesson}><Save className="icon" />{lessonDirty ? "保存本次教案修改" : "本次教案已保存"}</button>}
        </div>
        {lesson ? (
          <div className="session-lesson-editor">
            <label>教学目标<textarea value={lesson.teaching_goals} onChange={(event) => patchLesson({ teaching_goals: event.target.value })} /></label>
            <div className="two-field-row">
              <label>教学重点<textarea value={lesson.key_points} onChange={(event) => patchLesson({ key_points: event.target.value })} /></label>
              <label>教学难点<textarea value={lesson.difficult_points} onChange={(event) => patchLesson({ difficult_points: event.target.value })} /></label>
            </div>
            <label>教学过程<textarea className="large-textarea" value={lesson.teaching_process} onChange={(event) => patchLesson({ teaching_process: event.target.value })} /></label>
            <div className="two-field-row">
              <label>课后任务<textarea value={lesson.homework} onChange={(event) => patchLesson({ homework: event.target.value })} /></label>
              <label>教学反思<textarea value={lesson.reflection} onChange={(event) => patchLesson({ reflection: event.target.value })} /></label>
            </div>
          </div>
        ) : <div className="empty-inline">本次课尚无教案，材料将只依据课程实施大纲生成。</div>}
      </section>

      <section className="session-material-section">
        <div className="section-title-row"><div><h3>备课材料</h3><span>{materials.length} 份已保存</span></div></div>
        <div className="session-material-layout">
          <aside className="session-material-sidebar">
            <div className="material-generator">
              <div className="segmented" aria-label="材料类型">
                <button className={materialType === "assignment" ? "active" : ""} onClick={() => setMaterialType("assignment")}>作业</button>
                <button className={materialType === "test" ? "active" : ""} onClick={() => setMaterialType("test")}>测试</button>
              </div>
              <label>难度<select value={difficulty} onChange={(event) => setDifficulty(event.target.value as SessionMaterialDifficulty)}>
                {Object.entries(difficultyLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
              </select></label>
              <label>预计用时（分钟）<input type="number" min="1" value={estimatedMinutes} onChange={(event) => setEstimatedMinutes(Number(event.target.value))} /></label>
              {materialType === "test" && <label>题量<input type="number" min="1" value={questionCount} onChange={(event) => setQuestionCount(Number(event.target.value))} /></label>}
              <button className="btn primary" disabled={busy} onClick={generateMaterial}><Sparkles className="icon" />{generatingMaterial ? "AI 生成中" : `AI 生成${materialType === "assignment" ? "作业" : "测试"}`}</button>
            </div>
            <div className="material-list" aria-label="已保存材料">
              {materials.map((item) => (
                <button
                  key={item.id}
                  aria-label={item.title}
                  className={`${item.id === selectedMaterialId ? "active" : ""} ${dirtyMaterialIds.has(item.id) ? "dirty" : ""}`.trim()}
                  onClick={() => setSelectedMaterialId(item.id)}
                >
                  <strong>{item.title}</strong>
                  <span>{item.material_type === "assignment" ? "作业" : "测试"} · {difficultyLabels[item.difficulty]} · {item.estimated_minutes} 分钟</span>
                  <small>
                    <span>{item.generation_method === "ai" ? "AI 生成" : "规则草稿"}</span>
                    <span> · {item.source_status === "outline_and_lesson" ? "已引用教案" : "未引用教案"}</span>
                  </small>
                </button>
              ))}
            </div>
          </aside>

          <div className="material-editor">
            {selectedMaterial ? (
              <>
                <label>材料标题<input value={selectedMaterial.title} onChange={(event) => patchMaterial({ title: event.target.value })} /></label>
                <label>材料内容<textarea className="large-textarea" value={selectedMaterial.content} onChange={(event) => patchMaterial({ content: event.target.value })} /></label>
                <label>参考答案<textarea value={selectedMaterial.reference_answer} onChange={(event) => patchMaterial({ reference_answer: event.target.value })} /></label>
                <label>评分标准<textarea value={selectedMaterial.grading_criteria} onChange={(event) => patchMaterial({ grading_criteria: event.target.value })} /></label>
                <div className="material-source-codes">
                  <span>课程目标：{selectedMaterial.course_goal_codes || "未填写"}</span>
                  <span>能力指标：{selectedMaterial.ability_codes || "未填写"}</span>
                </div>
                <div className={`editor-save-state ${dirtyMaterialIds.has(selectedMaterial.id) ? "dirty" : ""}`} role="status" aria-label="材料保存状态">
                  {dirtyMaterialIds.has(selectedMaterial.id) ? "材料有未保存修改" : "材料已保存"}
                </div>
                <div className="material-actions">
                  <button className="btn danger" disabled={busy} onClick={removeMaterial}><Trash2 className="icon" />删除材料</button>
                  <button className="btn" disabled={busy || dirtyMaterialIds.has(selectedMaterial.id)} onClick={downloadMaterial}><Download className="icon" />导出 Word</button>
                  <button className="btn primary" disabled={busy || !dirtyMaterialIds.has(selectedMaterial.id)} onClick={saveMaterial}><Save className="icon" />{dirtyMaterialIds.has(selectedMaterial.id) ? "保存材料修改" : "材料已保存"}</button>
                </div>
              </>
            ) : <div className="empty-inline">选择已有材料，或生成一份新的作业或测试。</div>}
          </div>
        </div>
      </section>

      <section className="post-class-section" aria-labelledby="post-class-title">
        <div className="section-title-row">
          <div><h3 id="post-class-title">课后记录</h3><span>约 1 分钟</span></div>
          {workspace.reflection && workspace.reflection.status !== "applied" && (
            <button className="btn danger" disabled={busy} onClick={removeReflection}><Trash2 className="icon" />删除记录</button>
          )}
        </div>
        <div className="reflection-fields">
          <ReflectionOptionField
            label="授课进度"
            value={reflectionDraft.progress_status}
            options={progressOptions}
            disabled={workspace.reflection?.status === "applied"}
            onChange={(value) => setReflectionDraft((current) => ({ ...current, progress_status: value as PostClassReflectionInput["progress_status"] }))}
          />
          <ReflectionOptionField
            label="学生掌握"
            value={reflectionDraft.mastery_level}
            options={masteryOptions}
            disabled={workspace.reflection?.status === "applied"}
            onChange={(value) => setReflectionDraft((current) => ({ ...current, mastery_level: value as PostClassReflectionInput["mastery_level"] }))}
          />
          <ReflectionOptionField
            label="课堂效果"
            value={reflectionDraft.classroom_effect}
            options={effectOptions}
            disabled={workspace.reflection?.status === "applied"}
            onChange={(value) => setReflectionDraft((current) => ({ ...current, classroom_effect: value as PostClassReflectionInput["classroom_effect"] }))}
          />
        </div>
        <label>补充说明<textarea maxLength={500} disabled={workspace.reflection?.status === "applied"} value={reflectionDraft.note} onChange={(event) => setReflectionDraft((current) => ({ ...current, note: event.target.value }))} /></label>
        {workspace.reflection && (
          <div className="reflection-suggestion">
            <div><strong>下次课调整建议</strong><span>{workspace.reflection.suggested_minutes ? `建议安排 ${workspace.reflection.suggested_minutes} 分钟` : "无需调整"}</span></div>
            <p>{workspace.reflection.suggestion_text}</p>
            {!workspace.next_outline && <small>本课程暂无后续课次，记录已保存。</small>}
            {workspace.next_outline && !workspace.next_lesson_exists && <small>建议已保存，生成下一次课教案后可应用。</small>}
            {workspace.reflection.status === "applied" && <small className="success-text"><CheckCircle2 className="icon" />已应用到第 {workspace.next_outline?.session_no} 次课</small>}
          </div>
        )}
        <div className="reflection-actions">
          {workspace.reflection?.status === "applied" ? (
            <button className="btn" disabled={busy} onClick={revertReflection}><RotateCcw className="icon" />撤销应用</button>
          ) : (
            <>
              <button className="btn primary" disabled={busy} onClick={saveReflection}><Save className="icon" />保存课后记录</button>
              {workspace.reflection && workspace.reflection.suggestion_type !== "none" && workspace.next_outline && (
                <button className="btn" disabled={busy || !workspace.next_lesson_exists} onClick={applyReflection}>应用到下次课教案</button>
              )}
            </>
          )}
        </div>
      </section>
    </section>
  );
}

function ReflectionOptionField({
  label,
  value,
  options,
  disabled,
  onChange
}: {
  label: string;
  value: string;
  options: { value: string; label: string }[];
  disabled?: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <fieldset className="reflection-field">
      <legend>{label}</legend>
      <div className="reflection-option-group">
        {options.map((option) => (
          <button
            type="button"
            key={option.value}
            className={option.value === value ? "active" : ""}
            disabled={disabled}
            onClick={() => onChange(option.value)}
          >{option.label}</button>
        ))}
      </div>
    </fieldset>
  );
}
