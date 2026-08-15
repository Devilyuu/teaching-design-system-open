import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  applyPostClassReflection,
  deleteSessionMaterial,
  exportOutline,
  exportSessionMaterial,
  generateSessionMaterial,
  getSessionWorkspace,
  getAiModelConfig,
  updateAiModelConfig,
  testAiModelConfig,
  enableAiModelConfig,
  createLessonRevisionCandidate,
  acceptLessonRevisionCandidate,
  rejectLessonRevisionCandidate,
  resolveApiBaseUrl,
  upsertPostClassReflection,
  updateSessionMaterial
} from "./api";
import type { SessionMaterial } from "./types";

const material: SessionMaterial = {
  id: 31,
  task_id: 1,
  outline_row_id: 11,
  owner_user_id: 1,
  material_type: "assignment",
  title: "AIGC 实践作业",
  content: "完成案例拆解",
  reference_answer: "包含背景、方法和结论",
  grading_criteria: "完成度 40 分",
  difficulty: "medium",
  estimated_minutes: 40,
  course_goal_codes: "M1",
  ability_codes: "1-3-4",
  source_status: "outline_and_lesson",
  generation_method: "ai",
  created_at: "2026-07-02T08:00:00Z",
  updated_at: "2026-07-02T08:00:00Z"
};

describe("api base url", () => {
  it("uses the deployed base path in production when no api url is configured", () => {
    expect(resolveApiBaseUrl(undefined, false, "/design/")).toBe("/design/api");
  });
});

describe("ai model configuration api", () => {
  it("loads, updates, tests and enables the administrator configuration", async () => {
    const config = {
      id: 1,
      base_url: "https://model.example/v1",
      model_name: "lesson-model",
      api_key_status: "已配置",
      enabled: false,
      connection_status: "untested",
      last_tested_at: null,
      updated_at: null
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(config))
      .mockResolvedValueOnce(jsonResponse(config))
      .mockResolvedValueOnce(jsonResponse({ ...config, connection_status: "connected" }))
      .mockResolvedValueOnce(jsonResponse({ ...config, connection_status: "connected", enabled: true }));
    vi.stubGlobal("fetch", fetchMock);

    await getAiModelConfig();
    await updateAiModelConfig({ base_url: config.base_url, model_name: config.model_name, api_key: "" });
    await testAiModelConfig();
    await enableAiModelConfig(true);

    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      "http://localhost:8000/admin/ai-model",
      "http://localhost:8000/admin/ai-model",
      "http://localhost:8000/admin/ai-model/test",
      "http://localhost:8000/admin/ai-model/enable"
    ]);
    expect(fetchMock.mock.calls[1][1].method).toBe("PUT");
  });
});

describe("lesson revision api", () => {
  it("creates, accepts and rejects a field candidate", async () => {
    const candidate = { id: 7, proposed_content: "新教学重点", status: "pending" };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(candidate))
      .mockResolvedValueOnce(jsonResponse({ ...candidate, status: "accepted" }))
      .mockResolvedValueOnce(jsonResponse({ ...candidate, status: "rejected" }));
    vi.stubGlobal("fetch", fetchMock);

    await createLessonRevisionCandidate(1, 2, "key_points", "增加案例");
    await acceptLessonRevisionCandidate(1, 7);
    await rejectLessonRevisionCandidate(1, 7);

    expect(fetchMock.mock.calls[0][0]).toBe("http://localhost:8000/tasks/1/lessons/2/revision-candidates");
    expect(fetchMock.mock.calls[1][0]).toBe("http://localhost:8000/tasks/1/lesson-revision-candidates/7/accept");
  });
});

describe("session workspace api", () => {
  beforeEach(() => {
    localStorage.setItem("teachingDesignToken", "token");
  });

  it("loads, generates, updates and deletes session materials", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ outline: {}, lesson: null, materials: [] }))
      .mockResolvedValueOnce(jsonResponse(material))
      .mockResolvedValueOnce(jsonResponse({ ...material, title: "修改后的作业" }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await getSessionWorkspace(1, 11);
    await generateSessionMaterial(1, 11, {
      material_type: "assignment",
      difficulty: "medium",
      estimated_minutes: 40,
      question_count: 5
    });
    await updateSessionMaterial(1, { ...material, title: "修改后的作业" });
    await deleteSessionMaterial(1, 31);

    expect(fetchMock.mock.calls[0][0]).toBe("http://localhost:8000/tasks/1/sessions/11");
    expect(fetchMock.mock.calls[1][0]).toBe("http://localhost:8000/tasks/1/sessions/11/materials/generate");
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toMatchObject({ material_type: "assignment" });
    expect(fetchMock.mock.calls[2][0]).toBe("http://localhost:8000/tasks/1/materials/31");
    expect(fetchMock.mock.calls[2][1].method).toBe("PUT");
    expect(fetchMock.mock.calls[3][1].method).toBe("DELETE");
  });

  it("downloads one session material", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(new Blob(["docx"]), {
      status: 200,
      headers: { "Content-Disposition": "attachment; filename*=UTF-8''material.docx" }
    })));

    const result = await exportSessionMaterial(1, 31);

    expect(result.filename).toBe("material.docx");
    expect(result.blob.size).toBeGreaterThan(0);
  });

  it("saves and applies a post-class reflection", async () => {
    const reflection = {
      id: 12,
      progress_status: "partial",
      mastery_level: "average",
      classroom_effect: "normal",
      note: "示范环节未完成",
      suggestion_text: "建议补讲",
      suggested_minutes: 20,
      status: "pending"
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(reflection))
      .mockResolvedValueOnce(jsonResponse({ id: 8, teaching_process: "建议补讲" }));
    vi.stubGlobal("fetch", fetchMock);

    await upsertPostClassReflection(3, 9, {
      progress_status: "partial",
      mastery_level: "average",
      classroom_effect: "normal",
      note: "示范环节未完成"
    });
    await applyPostClassReflection(3, 12);

    expect(fetchMock.mock.calls[0][0]).toBe("http://localhost:8000/tasks/3/sessions/9/reflection");
    expect(fetchMock.mock.calls[0][1].method).toBe("PUT");
    expect(fetchMock.mock.calls[1][0]).toBe("http://localhost:8000/tasks/3/reflections/12/apply");
    expect(fetchMock.mock.calls[1][1].method).toBe("POST");
  });
});

describe("document download errors", () => {
  it("shows the refusal the backend wrote, not its JSON envelope", async () => {
    const detail =
      "导出中止：这份模板把正文各节标成了「【AI 生成】」，但本次任务还没有生成大纲正文。";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail }), {
          status: 400,
          headers: { "Content-Type": "application/json" }
        })
      )
    );

    await expect(exportOutline(1, null)).rejects.toThrowError(detail);
  });
});

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" }
  });
}
