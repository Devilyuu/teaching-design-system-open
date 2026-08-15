import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const css = readFileSync("src/styles.css", "utf8");

describe("global UI foundation", () => {
  it("uses the approved navigation surface and solid brand mark", () => {
    expect(css).toContain("--nav-surface: #dfe9f6");
    expect(css).toMatch(/\.brand-mark\s*\{[\s\S]*?background:\s*var\(--blue\)/);
  });

  it("defines visible keyboard focus and accessible secondary text", () => {
    expect(css).toContain("--muted: #56647a");
    expect(css).toContain(":focus-visible");
    expect(css).toMatch(/\.sr-only\s*\{[\s\S]*?position:\s*absolute/);
  });

  it("stacks the dashboard before the mobile breakpoint", () => {
    const compactDesktopRules = css.match(/@media \(max-width: 1120px\) \{([\s\S]*?)\n\}/)?.[1] ?? "";
    expect(compactDesktopRules).toMatch(/\.dashboard-focus\s*\{\s*grid-template-columns:\s*1fr/);
  });

  it("keeps mobile navigation compact and horizontally scrollable", () => {
    const mobileRules = css.match(/@media \(max-width: 760px\) \{([\s\S]*?)\n\}/)?.[1] ?? "";
    expect(mobileRules).toMatch(/\.app\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)/);
    expect(mobileRules).toMatch(/\.nav\s*\{[\s\S]*?display:\s*flex/);
    expect(mobileRules).toMatch(/\.nav\s*\{[\s\S]*?overflow-x:\s*auto/);
    expect(mobileRules).toMatch(/\.topbar-actions\s+\.user-chip\s*\{\s*display:\s*none/);
  });

  it("uses a full status surface instead of a side stripe for readiness", () => {
    const readinessRule = css.match(/\.readiness-band\s*\{([^}]*)\}/)?.[1] ?? "";
    expect(readinessRule).toContain("border: 1px solid");
    expect(readinessRule).not.toContain("border-left");
    expect(css).toContain(".material-list-head");
  });

  it("keeps course workspace tabs visible during long document workflows", () => {
    const tabsRule = css.match(/\.workspace-tabs\s*\{([^}]*)\}/)?.[1] ?? "";
    expect(tabsRule).toContain("position: sticky");
    expect(tabsRule).toContain("top: 0");
  });

  it("keeps outline context and actions visible while scrolling the wide editor", () => {
    expect(css).toMatch(/\.outline-main-panel th:first-child[^{]*\{[^}]*position:\s*sticky/);
    expect(css).toMatch(/\.outline-main-panel th:last-child[^{]*\{[^}]*position:\s*sticky/);
    expect(css).toContain(".outline-row-dirty");
  });

  it("keeps outline columns aligned without a sticky action overlay on narrow screens", () => {
    const outlineTableRule = css.match(/\.outline-main-panel table\s*\{([^}]*)\}/)?.[1] ?? "";
    expect(outlineTableRule).toContain("table-layout: fixed");
    expect(css).toContain(".outline-col-content");
    expect(css).toMatch(/@media \(max-width: 760px\)[\s\S]*?\.outline-main-panel th:last-child\s*\{[^}]*right:\s*auto/);
    expect(css).toMatch(/@media \(max-width: 760px\)[\s\S]*?\.outline-main-panel td:last-child\s*\{[^}]*position:\s*static/);
  });

  it("lines every outline panel up on both edges", () => {
    // The editor table is wider than anything that could sit beside it, so the
    // two-column grid left 生成依据 in a 220px column with dead space to its
    // right and 课次详情 pushed against the other edge.
    expect(css).toMatch(/\.outline-layout\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/);
    expect(css).toMatch(/\.outline-layout > \.outline-main-panel,\s*\.outline-layout > \.outline-detail-panel\s*\{[^}]*grid-column:\s*1/);
    // Full width would otherwise turn each four-item list into a tall stack.
    expect(css).toMatch(/\.outline-layout \.goal-list[^{]*\{[^}]*grid-template-columns:\s*repeat\(4/);
    // The lesson page still has a column narrow enough for a panel beside it.
    expect(css).toMatch(/\.lesson-layout > \.lesson-detail-panel\s*\{[^}]*grid-column:\s*2/);
  });

  it("avoids thick side-stripe accents across work surfaces", () => {
    expect(css).not.toMatch(/border-left:\s*[2-9]px/);
  });

  it("keeps admin library entries as flat rows instead of nested cards", () => {
    const adminLibraryItems = css.match(/\.admin-library-grid \.library-item\s*\{([^}]*)\}/)?.[1] ?? "";
    expect(adminLibraryItems).toContain("border: 0");
    expect(adminLibraryItems).toContain("border-bottom: 1px solid");
    expect(adminLibraryItems).toContain("background: transparent");
  });
});
