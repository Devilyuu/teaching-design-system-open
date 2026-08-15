import { describe, expect, it } from "vitest";

import { resolveBasePath } from "./buildConfig";

describe("production build configuration", () => {
  it("defaults production assets to the deployed /design/ path", () => {
    expect(resolveBasePath("build", undefined)).toBe("/design/");
    expect(resolveBasePath("serve", undefined)).toBe("/");
    expect(resolveBasePath("build", "/preview/")).toBe("/preview/");
  });
});
