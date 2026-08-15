# UI Foundation, Login, and Application Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the React login and authenticated application shell with the approved “蓝图工作台” system while fixing the medium-width dashboard break, keyboard focus, status semantics, and demo-data leakage.

**Architecture:** Preserve the current single-page React state model and API calls. Add only semantic attributes and presentation rules in `App.tsx` and `styles.css`; keep the change reversible and independent from later course-workspace restructuring. Tests lock down user-visible login defaults, active-navigation semantics, live status behavior, and the CSS rules that prevent the known responsive regression.

**Tech Stack:** React 19, TypeScript 5.8, Vite 6, Vitest 3, Testing Library, plain CSS design tokens.

---

### Task 1: Login and Global Status Semantics

**Files:**
- Modify: `apps/web/src/App.test.tsx`
- Modify: `apps/web/src/App.tsx`

- [ ] **Step 1: Write failing login and status tests**

Add tests asserting that the employee number starts blank, the login-state check exposes `role="status"`, and login errors expose `role="alert"`.

```tsx
it("starts the login form without development credentials", async () => {
  localStorage.removeItem("teachingDesignToken");
  render(<App />);
  expect(await screen.findByLabelText("工号")).toHaveValue("");
});

it("announces authentication progress", () => {
  localStorage.removeItem("teachingDesignToken");
  vi.stubGlobal("fetch", vi.fn(() => new Promise(() => undefined)));
  render(<App />);
  expect(screen.getByRole("status")).toHaveTextContent("正在检查登录状态");
});
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `npm test -- App.test.tsx -t "starts the login form|announces authentication progress"`

Expected: the employee number assertion fails because it is `admin`, and the role query fails because the loading surface has no status role.

- [ ] **Step 3: Implement minimal semantic changes**

In `App.tsx`, initialize `employeeNo` to an empty string, add `autoComplete="username"` and `autoComplete="current-password"`, mark authentication/loading text with `role="status"`, and mark visible errors with `role="alert"`. Add `aria-live="polite"` to non-error notices.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `npm test -- App.test.tsx -t "starts the login form|announces authentication progress"`

Expected: both tests pass.

### Task 2: Navigation Semantics and Current Location

**Files:**
- Modify: `apps/web/src/App.test.tsx`
- Modify: `apps/web/src/App.tsx`

- [ ] **Step 1: Write a failing active-navigation test**

```tsx
it("marks the current primary navigation destination", async () => {
  render(<App />);
  expect(await screen.findByRole("button", { name: "教师工作台" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByRole("button", { name: "我的课程" })).not.toHaveAttribute("aria-current");
});
```

- [ ] **Step 2: Run the test and verify RED**

Run: `npm test -- App.test.tsx -t "marks the current primary navigation destination"`

Expected: failure because the active button has only a CSS class.

- [ ] **Step 3: Implement `aria-current`**

Apply `aria-current={view === id ? "page" : undefined}` to teacher and administrator navigation entries without changing their click behavior.

- [ ] **Step 4: Run the focused test and verify GREEN**

Run: `npm test -- App.test.tsx -t "marks the current primary navigation destination"`

Expected: pass.

### Task 3: Blueprint Workbench Tokens and Responsive Shell

**Files:**
- Create: `apps/web/src/styles.test.ts`
- Modify: `apps/web/src/styles.css`

- [ ] **Step 1: Write failing design-system regression tests**

Create a Vitest test that reads `styles.css` and asserts the approved global contracts:

```ts
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const css = readFileSync(new URL("./styles.css", import.meta.url), "utf8");

describe("global UI foundation", () => {
  it("uses the approved navigation surface and solid brand mark", () => {
    expect(css).toContain("--nav-surface: #dfe9f6");
    expect(css).toMatch(/\.brand-mark\s*\{[\s\S]*background:\s*var\(--blue\)/);
  });

  it("defines visible keyboard focus and accessible secondary text", () => {
    expect(css).toContain("--muted: #56647a");
    expect(css).toContain(":focus-visible");
  });

  it("stacks the dashboard before the mobile breakpoint", () => {
    expect(css).toMatch(/@media \(max-width: 1120px\)[\s\S]*\.dashboard-focus\s*\{\s*grid-template-columns:\s*1fr/);
  });
});
```

- [ ] **Step 2: Run the CSS tests and verify RED**

Run: `npm test -- styles.test.ts`

Expected: all three tests fail against the current tokens and breakpoint rules.

- [ ] **Step 3: Implement the global visual foundation**

Update `styles.css` to:

- introduce `--nav-surface`, `--focus-ring`, semantic state colors, and the approved 4/8/12/16/24/32 spacing vocabulary;
- raise `--muted` to `#56647a`;
- use a solid institutional-blue brand mark;
- make the sidebar mist blue and active navigation white without a colored side stripe;
- remove wide shadows from the application frame, panels, and course cards;
- add consistent `:focus-visible`, disabled, hover, and active states;
- make buttons at least 36px on desktop and 44px at touch breakpoints;
- stack `.dashboard-focus` and `.course-grid` at 1120px so the pending-course column cannot collapse into vertical Chinese text;
- keep the existing mobile DOM and business behavior intact.

- [ ] **Step 4: Run CSS tests and verify GREEN**

Run: `npm test -- styles.test.ts`

Expected: 3 tests pass.

### Task 4: Full Verification and Visual QA

**Files:**
- Verify: `apps/web/src/App.tsx`
- Verify: `apps/web/src/styles.css`
- Verify: `apps/web/src/App.test.tsx`
- Verify: `apps/web/src/styles.test.ts`

- [ ] **Step 1: Run all frontend tests**

Run: `npm test`

Expected: all Vitest tests pass with no unhandled errors.

- [ ] **Step 2: Run the production build**

Run: `npm run build`

Expected: TypeScript and Vite complete successfully.

- [ ] **Step 3: Run the Impeccable detector**

Run: `node ~/.agents/skills/impeccable/scripts/detect.mjs --json apps/web/src`

Expected: no `side-tab` warning remains in the changed shell styles; remaining findings are documented for later page batches.

- [ ] **Step 4: Verify real browser rendering**

At 1440px, 1024px, 882px, 768px, and 375px verify login, dashboard, sidebar, current navigation, focus visibility, long Chinese course names, and absence of page-level horizontal overflow. Confirm console has no errors.

### Self-review

- Scope covers only foundation, login, status semantics, app shell, and the proven medium-width regression.
- Course workflow components, APIs, and business state transitions remain untouched.
- No placeholders, new backend dependencies, or fabricated history data are introduced.
