# Account System MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a small internal account system so administrators can maintain editable majors and teacher accounts, while teachers log in by employee number and only work with their own teaching tasks.

**Architecture:** Add first-party authentication to the FastAPI API using PBKDF2 password hashes and signed bearer tokens implemented with the Python standard library. Add `Major`, `User`, and `UserMajorLink` tables, attach `owner_id` and `major_id` to `TeachingTask`, and keep old text fields for document rendering compatibility. The React app stores the token in local storage, shows a login screen when unauthenticated, and conditionally shows account/major management to administrators.

**Tech Stack:** FastAPI, SQLModel, SQLite, Python standard library crypto helpers, React, TypeScript, Vitest.

---

### Task 1: Backend Auth Foundation

**Files:**
- Create: `apps/api/app/auth.py`
- Modify: `apps/api/app/models.py`
- Modify: `apps/api/app/schemas.py`
- Modify: `apps/api/app/db.py`
- Create: `apps/api/app/routes/auth.py`
- Test: `apps/api/tests/test_auth_api.py`

- [ ] **Step 1: Write failing API tests**

Create tests that seed an admin user, log in by employee number and password, verify `/auth/me`, and reject wrong passwords.

- [ ] **Step 2: Run tests to verify RED**

Run: `python -m pytest tests/test_auth_api.py -q`

Expected: imports or routes fail because auth models/routes do not exist.

- [ ] **Step 3: Implement minimal auth**

Implement `hash_password`, `verify_password`, `create_access_token`, `decode_access_token`, `get_current_user`, and `require_admin`.

- [ ] **Step 4: Add models and schemas**

Add `Major`, `User`, `UserMajorLink`; add auth request/response schemas.

- [ ] **Step 5: Add database bootstrap**

Create tables, add lightweight SQLite column migration for `TeachingTask.owner_id` and `TeachingTask.major_id`, seed default admin from environment variables, and assign existing tasks to that admin.

- [ ] **Step 6: Run tests to verify GREEN**

Run: `python -m pytest tests/test_auth_api.py -q`

Expected: all tests pass.

### Task 2: Backend Admin and Task Ownership

**Files:**
- Create: `apps/api/app/routes/admin.py`
- Modify: `apps/api/app/routes/tasks.py`
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/app/schemas.py`
- Test: `apps/api/tests/test_admin_api.py`
- Test: existing API tests

- [ ] **Step 1: Write failing tests**

Cover admin-created majors, admin-created teacher accounts, teacher-visible majors, teacher task list isolation, and admin task list visibility.

- [ ] **Step 2: Run tests to verify RED**

Run: `python -m pytest tests/test_admin_api.py -q`

Expected: missing admin routes and task auth behavior.

- [ ] **Step 3: Implement admin routes**

Add `/admin/majors`, `/admin/users`, `/majors`, and password reset/update behavior needed for the MVP.

- [ ] **Step 4: Protect task routes**

Require a logged-in user for task APIs. Teachers can only access their own tasks. Admins can access all tasks. New tasks are assigned to the current user.

- [ ] **Step 5: Run focused and full backend tests**

Run: `python -m pytest tests/test_admin_api.py tests/test_auth_api.py -q`, then full `python -m pytest -q`.

Expected: all pass.

### Task 3: Frontend Login and Admin Screens

**Files:**
- Modify: `apps/web/src/api.ts`
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/styles.css`
- Test: `apps/web/src/App.test.tsx`

- [ ] **Step 1: Write failing frontend tests**

Cover login by employee number, dashboard shown after login, and admin management view only for admin users.

- [ ] **Step 2: Run tests to verify RED**

Run: `npm test -- --run src/App.test.tsx -t "login"`

Expected: login UI and API calls are missing.

- [ ] **Step 3: Add API token support**

Store bearer token in local storage, attach it to JSON, form upload, and export requests, and clear it on logout or 401.

- [ ] **Step 4: Add login shell**

Show login screen before app data loads. After login, load `/auth/me`, tasks, and teacher-visible majors.

- [ ] **Step 5: Add compact admin management**

On the existing admin page, add tabs or sections for editable majors and teacher accounts.

- [ ] **Step 6: Run frontend tests and build**

Run: `npm test -- --run` and `npm run build` with `/design/` environment variables.

Expected: all pass.

### Task 4: Deploy and Smoke Test

**Files:**
- Server deployment only

- [ ] **Step 1: Package source**

Create tarball excluding `.git`, `apps/web/node_modules`, `apps/api/uploads`, caches, and database files.

- [ ] **Step 2: Deploy to `/opt/teaching-design-system`**

Keep the existing `.venv`; reinstall editable API package, copy frontend dist to `/var/www/teaching-design-system/design`, restart `teaching-design.service`.

- [ ] **Step 3: Smoke test**

Check `teaching-design.service`, `teacher-achievement.service`, `/design/`, `/design/api/health`, `/design/api/auth/login`, and root achievement system.

- [ ] **Step 4: Commit and push**

Commit the account-system changes and push `codex/mvp-outline-export-pr`.

