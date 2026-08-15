import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import AiModelConfigPanel from "./AiModelConfigPanel";

vi.mock("./api", () => ({
  getAiModelConfig: vi.fn().mockResolvedValue({
    id: 1,
    base_url: "https://model.example/v1",
    model_name: "lesson-model",
    api_key_status: "已配置",
    enabled: true,
    connection_status: "connected",
    last_tested_at: "2026-07-02T08:00:00Z",
    updated_at: "2026-07-02T08:00:00Z"
  }),
  updateAiModelConfig: vi.fn(),
  testAiModelConfig: vi.fn(),
  enableAiModelConfig: vi.fn()
}));

describe("AiModelConfigPanel", () => {
  it("shows a connected and enabled model without revealing its key", async () => {
    render(<AiModelConfigPanel />);

    expect(await screen.findByDisplayValue("https://model.example/v1")).toBeInTheDocument();
    expect(screen.getByText("连接正常")).toBeInTheDocument();
    expect(screen.getByText("已启用")).toBeInTheDocument();
    expect(screen.queryByText("sk-private")).not.toBeInTheDocument();
  });
});
