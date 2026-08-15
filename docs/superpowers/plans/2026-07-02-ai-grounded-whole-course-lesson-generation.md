# AI-Grounded Whole-Course Lesson Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace generic lesson-plan generation with administrator-configured, source-grounded AI generation that strictly validates ability codes, preserves partial batch results, and supports teacher-approved field regeneration.

**Architecture:** Add focused model-configuration, evidence, adapter, validator, orchestration, and candidate services behind new SQLModel records and authenticated API routes. The React client starts a persisted batch run and polls progress while keeping current lesson editing and Word export intact. Model-provider details remain behind an OpenAI-compatible adapter.

**Tech Stack:** FastAPI, SQLModel, Pydantic, httpx, cryptography/Fernet, SQLite, React, TypeScript, Vite, Vitest, Testing Library

---

## File Structure

- Create `apps/api/app/services/secret_store.py`: encrypt and decrypt model API keys.
- Create `apps/api/app/services/ai_model_config.py`: validate, save, mask, and test provider configuration.
- Create `apps/api/app/services/lesson_evidence.py`: build strict per-session evidence and code allowlists.
- Create `apps/api/app/services/openai_compatible.py`: call the configured chat-completions endpoint and parse JSON.
- Create `apps/api/app/services/ai_lesson_validator.py`: deterministic schema, code, and duration validation.
- Create `apps/api/app/services/ai_lesson_generation.py`: persisted whole-course orchestration and retries.
- Create `apps/api/app/services/lesson_revision.py`: field candidate generation and acceptance rules.
- Create `apps/api/app/routes/ai_config.py`: administrator-only model configuration endpoints.
- Create `apps/api/app/routes/lesson_ai.py`: batch-run and field-candidate endpoints.
- Create `apps/api/tests/test_ai_model_config.py`: encryption, masking, permissions, and connection tests.
- Create `apps/api/tests/test_lesson_evidence.py`: strict source and code tests.
- Create `apps/api/tests/test_ai_lesson_validator.py`: structured output and duration tests.
- Create `apps/api/tests/test_ai_lesson_generation_api.py`: batch, retry, partial success, and candidate API tests.
- Create `apps/web/src/AiModelConfigPanel.tsx`: administrator configuration surface.
- Create `apps/web/src/LessonGenerationProgress.tsx`: run status and failed-item retry UI.
- Create `apps/web/src/LessonRevisionControl.tsx`: local regeneration request and comparison UI.
- Modify `apps/api/app/models.py`: add configuration, run, item, and candidate tables.
- Modify `apps/api/app/db.py`: add idempotent legacy-column migration for expanded lesson fields.
- Modify `apps/api/app/schemas.py`: add public request and response contracts.
- Modify `apps/api/app/main.py`: register the two focused routers.
- Modify `apps/api/app/routes/tasks.py`: remove use of generic generation from the product path while preserving lesson list, edit, and export.
- Modify `apps/api/pyproject.toml`: promote `httpx` to runtime and add `cryptography`.
- Modify `apps/web/src/api.ts`: add configuration, run, retry, and candidate calls.
- Modify `apps/web/src/types.ts`: add matching TypeScript contracts.
- Modify `apps/web/src/App.tsx`: integrate the three new focused components.
- Modify `apps/web/src/App.test.tsx` and `apps/web/src/api.test.ts`: cover the new teacher flow.

### Task 1: Persist And Protect Model Configuration

**Files:**
- Modify: `apps/api/pyproject.toml`
- Modify: `apps/api/app/models.py`
- Modify: `apps/api/app/schemas.py`
- Modify: `apps/api/tests/conftest.py`
- Create: `apps/api/app/services/secret_store.py`
- Create: `apps/api/tests/test_ai_model_config.py`

- [ ] **Step 1: Write failing encryption and masking tests**

```python
def test_model_api_key_is_encrypted_and_masked(session):
    encrypted = encrypt_secret("sk-private")
    assert encrypted != "sk-private"
    assert decrypt_secret(encrypted) == "sk-private"
    assert mask_secret("sk-private") == "已配置"
```

- [ ] **Step 2: Run the focused test and verify missing symbols fail**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_ai_model_config.py -q`
Expected: FAIL because `AiModelConfig` and `encrypt_secret` do not exist.

- [ ] **Step 3: Add runtime dependencies and the configuration table**

```toml
"httpx>=0.27.0",
"cryptography>=43.0.0",
```

```python
class AiModelConfig(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    base_url: str
    model_name: str
    encrypted_api_key: str
    enabled: bool = False
    connection_status: str = "untested"
    last_tested_at: datetime | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 4: Implement Fernet encryption with a required server secret**

```python
def _fernet() -> Fernet:
    key = os.getenv("MODEL_CONFIG_ENCRYPTION_KEY", "")
    if not key:
        raise ModelSecretError("MODEL_CONFIG_ENCRYPTION_KEY is not configured")
    return Fernet(key.encode("ascii"))

def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")

def decrypt_secret(value: str) -> str:
    return _fernet().decrypt(value.encode("ascii")).decode("utf-8")

def mask_secret(value: str) -> str:
    return "已配置" if value else "未配置"
```

- [ ] **Step 5: Set an isolated encryption key in test setup and verify tests pass**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_ai_model_config.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/pyproject.toml apps/api/app/models.py apps/api/app/schemas.py apps/api/app/services/secret_store.py apps/api/tests/conftest.py apps/api/tests/test_ai_model_config.py
git commit -m "feat: protect ai model configuration"
```

### Task 2: Add Administrator Model Configuration API

**Files:**
- Create: `apps/api/app/services/ai_model_config.py`
- Create: `apps/api/app/routes/ai_config.py`
- Modify: `apps/api/app/main.py`
- Test: `apps/api/tests/test_ai_model_config.py`

- [ ] **Step 1: Add failing API tests for admin-only read, update, and test connection**

```python
response = client.put("/admin/ai-model", headers=admin_headers, json={
    "base_url": "https://model.example/v1",
    "model_name": "lesson-model",
    "api_key": "sk-private",
})
assert response.status_code == 200
assert response.json()["api_key_status"] == "已配置"
assert "encrypted_api_key" not in response.json()
assert client.get("/admin/ai-model", headers=teacher_headers).status_code == 403
```

- [ ] **Step 2: Run the API tests and verify the routes return 404**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_ai_model_config.py -q`
Expected: FAIL with 404 responses.

- [ ] **Step 3: Implement validation and masked responses**

```python
def validate_base_url(value: str) -> str:
    parsed = urlparse(value.rstrip("/"))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("模型接口地址必须是有效的 HTTP 或 HTTPS 地址")
    return value.rstrip("/")
```

`PUT /admin/ai-model` preserves the existing encrypted key when `api_key` is blank, marks the configuration `untested`, and disables it. `POST /admin/ai-model/test` sends one minimal JSON response request; only a successful parsed response changes status to `connected`. `POST /admin/ai-model/enable` rejects untested configurations.

- [ ] **Step 4: Register the router and verify all configuration tests pass**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_ai_model_config.py tests/test_admin_api.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/ai_model_config.py apps/api/app/routes/ai_config.py apps/api/app/main.py apps/api/tests/test_ai_model_config.py
git commit -m "feat: add ai model administration api"
```

### Task 3: Build Strict Lesson Evidence

**Files:**
- Create: `apps/api/app/services/lesson_evidence.py`
- Create: `apps/api/tests/test_lesson_evidence.py`

- [ ] **Step 1: Write failing tests for accepted and rejected codes**

```python
evidence = build_lesson_evidence(task, row, goals, indicators, previous_row=None, next_row=None)
assert evidence.allowed_ability_codes == {"1-3-4": "能够完成创意设计"}

row.ability_codes = "1-3-4 9-9-9"
with pytest.raises(LessonEvidenceError, match="9-9-9"):
    build_lesson_evidence(task, row, goals, indicators, None, None)
```

- [ ] **Step 2: Run the focused tests and verify the module is missing**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_lesson_evidence.py -q`
Expected: FAIL on import.

- [ ] **Step 3: Implement canonical comparison without semantic guessing**

```python
def canonical_code(value: str) -> str:
    return value.strip().replace("－", "-").replace("—", "-")

allowed = {canonical_code(indicator.code): indicator.description for indicator in indicators}
referenced = {canonical_code(code) for goal in goals for code in goal.ability_codes.split()}
row_codes = {canonical_code(code) for code in row.ability_codes.split()}
unknown = (referenced | row_codes) - set(allowed)
if unknown:
    raise LessonEvidenceError(f"能力代码未通过人才培养方案校验：{', '.join(sorted(unknown))}")
```

The evidence object contains task identity, one outline row, adjacent titles, goal definitions, allowed ability definitions, and exact duration minutes. It requires `SourceConfirmation` at the API boundary.

- [ ] **Step 4: Run evidence and existing source-validation tests**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_lesson_evidence.py tests/test_source_validation.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/services/lesson_evidence.py apps/api/tests/test_lesson_evidence.py
git commit -m "feat: build strict lesson evidence"
```

### Task 4: Add OpenAI-Compatible Adapter And Deterministic Validator

**Files:**
- Create: `apps/api/app/services/openai_compatible.py`
- Create: `apps/api/app/services/ai_lesson_validator.py`
- Create: `apps/api/tests/test_ai_lesson_validator.py`

- [ ] **Step 1: Write failing tests for parsing, invented codes, and duration mismatch**

```python
payload = valid_model_payload(total_minutes=160, ability_codes=["1-3-4"])
lesson = validate_lesson_payload(payload, evidence)
assert lesson.duration_minutes == 160

payload["ability_codes"] = ["9-9-9"]
with pytest.raises(LessonValidationError, match="9-9-9"):
    validate_lesson_payload(payload, evidence)
```

- [ ] **Step 2: Run tests and verify missing modules fail**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_ai_lesson_validator.py -q`
Expected: FAIL on import.

- [ ] **Step 3: Implement the adapter with dependency-injected httpx transport**

```python
class OpenAICompatibleClient:
    def __init__(self, config: AiModelConfig, transport: httpx.BaseTransport | None = None):
        self.config = config
        self.transport = transport

    def generate_json(self, system_prompt: str, user_payload: dict) -> dict:
        with httpx.Client(transport=self.transport, timeout=60) as client:
            response = client.post(
                f"{self.config.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {decrypt_secret(self.config.encrypted_api_key)}"},
                json={
                    "model": self.config.model_name,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
                    ],
                },
            )
        response.raise_for_status()
        return json.loads(response.json()["choices"][0]["message"]["content"])
```

- [ ] **Step 4: Implement strict Pydantic output validation and plain-text conversion**

Use `AiLessonPayload` with typed process segments. Validate all goal and ability codes against evidence, require non-empty fields, and require `sum(segment.minutes) == evidence.duration_minutes`. Convert accepted segments to the current `LessonPlan.teaching_process` plain-text format so Word export remains unchanged.

- [ ] **Step 5: Run validator tests**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_ai_lesson_validator.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/services/openai_compatible.py apps/api/app/services/ai_lesson_validator.py apps/api/tests/test_ai_lesson_validator.py
git commit -m "feat: validate structured ai lessons"
```

### Task 5: Persist Whole-Course Generation Runs

**Files:**
- Modify: `apps/api/app/models.py`
- Modify: `apps/api/app/db.py`
- Modify: `apps/api/app/schemas.py`
- Modify: `apps/api/app/services/docx_exporter.py`
- Modify: `apps/api/app/services/lesson_template_filler.py`
- Create: `apps/api/app/services/ai_lesson_generation.py`
- Create: `apps/api/tests/test_ai_lesson_generation_api.py`

- [ ] **Step 1: Write failing service tests for partial success and retry-once**

The fake adapter returns valid output for session 1 and invalid output twice for session 2. Assert one saved `LessonPlan`, item statuses `succeeded` and `failed`, and attempt count `2` on the failed item.

- [ ] **Step 2: Run focused tests and verify missing run models fail**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_ai_lesson_generation_api.py -q`
Expected: FAIL because generation run records do not exist.

- [ ] **Step 3: Add run and item tables**

```python
class LessonGenerationRun(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(index=True)
    initiated_by_id: int = Field(index=True)
    status: str = "pending"
    total_items: int = 0
    succeeded_items: int = 0
    failed_items: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None

class LessonGenerationItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(index=True)
    outline_row_id: int = Field(index=True)
    lesson_plan_id: int | None = Field(default=None, index=True)
    status: str = "pending"
    attempts: int = 0
    duration_ms: int = 0
    error_code: str = ""
```

Extend `LessonPlan` with `teaching_preparation`, `summary`, `generation_source`, and `review_status`. Add idempotent SQLite `ALTER TABLE` checks in `db.py` so existing deployments receive these columns. Include preparation and summary in fallback and recognized-template export positions without altering table styles. `LessonPlanUpdate` marks an AI draft `reviewed` after the teacher saves it.

- [ ] **Step 4: Implement orchestration with two model workers and serialized database writes**

Create all items first. Use `ThreadPoolExecutor(max_workers=2)` only for provider calls. Each worker returns a validated lesson or sanitized error; the coordinator updates SQLite sequentially. Retry timeout, provider, parse, and validation failures once. Upsert by `outline_row_id` only when validation succeeds.

- [ ] **Step 5: Run focused tests**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_ai_lesson_generation_api.py -q`
Expected: PASS for service-level run behavior.

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/models.py apps/api/app/db.py apps/api/app/schemas.py apps/api/app/services/docx_exporter.py apps/api/app/services/lesson_template_filler.py apps/api/app/services/ai_lesson_generation.py apps/api/tests/test_ai_lesson_generation_api.py
git commit -m "feat: persist lesson generation runs"
```

### Task 6: Expose Batch Generation And Retry APIs

**Files:**
- Create: `apps/api/app/routes/lesson_ai.py`
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/app/routes/tasks.py`
- Test: `apps/api/tests/test_ai_lesson_generation_api.py`

- [ ] **Step 1: Add failing endpoint tests**

Test that starting requires confirmed sources and an enabled connected model, returns a persisted run, hides another teacher's run, returns per-item progress, and retries only a failed item.

- [ ] **Step 2: Run tests and verify 404 responses**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_ai_lesson_generation_api.py -q`
Expected: FAIL with missing routes.

- [ ] **Step 3: Implement authenticated endpoints**

```text
POST /tasks/{task_id}/lesson-generation-runs
GET  /tasks/{task_id}/lesson-generation-runs/{run_id}
POST /tasks/{task_id}/lesson-generation-runs/{run_id}/items/{item_id}/retry
```

Start work with FastAPI `BackgroundTasks`; use a fresh database session inside the worker. Return `409` for unresolved sources, missing/disabled model configuration, no outline rows, or another active run. The old generic generation route returns a clear `410` response directing the client to the run endpoint.

- [ ] **Step 4: Verify API and existing ownership tests**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_ai_lesson_generation_api.py tests/test_outline_workflow_api.py tests/test_admin_api.py -q`
Expected: PASS after updating the old workflow expectation to the new run contract.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/routes/lesson_ai.py apps/api/app/main.py apps/api/app/routes/tasks.py apps/api/tests/test_ai_lesson_generation_api.py apps/api/tests/test_outline_workflow_api.py
git commit -m "feat: expose grounded lesson generation api"
```

### Task 7: Add Field-Level Revision Candidates

**Files:**
- Modify: `apps/api/app/models.py`
- Modify: `apps/api/app/schemas.py`
- Create: `apps/api/app/services/lesson_revision.py`
- Modify: `apps/api/app/routes/lesson_ai.py`
- Test: `apps/api/tests/test_ai_lesson_generation_api.py`

- [ ] **Step 1: Add failing tests for create, accept, reject, and failed generation**

Assert a pending candidate does not modify the lesson, acceptance changes only the requested field, rejection changes nothing, stale original snapshots return `409`, and provider failure leaves the lesson unchanged.

- [ ] **Step 2: Run tests and verify candidate routes are missing**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_ai_lesson_generation_api.py -q`
Expected: FAIL with 404.

- [ ] **Step 3: Add the candidate table and allowlisted fields**

```python
REVISION_FIELDS = {
    "teaching_goals", "key_points", "difficult_points",
    "teaching_preparation", "teaching_process", "summary", "homework",
}

class LessonRevisionCandidate(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    lesson_plan_id: int = Field(index=True)
    field_name: str
    original_content: str
    proposed_content: str
    teacher_instruction: str = ""
    status: str = "pending"
    created_by_id: int = Field(index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 4: Implement candidate endpoints**

```text
POST /tasks/{task_id}/lessons/{lesson_id}/revision-candidates
POST /tasks/{task_id}/lesson-revision-candidates/{candidate_id}/accept
POST /tasks/{task_id}/lesson-revision-candidates/{candidate_id}/reject
```

The generation prompt receives the authoritative evidence, current field, and optional instruction. Accept compares the current field to `original_content` before replacing one attribute.

- [ ] **Step 5: Run candidate and lesson-edit regression tests**

Run: `cd apps/api && .venv/Scripts/python -m pytest tests/test_ai_lesson_generation_api.py tests/test_outline_workflow_api.py tests/test_session_workspace_api.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/models.py apps/api/app/schemas.py apps/api/app/services/lesson_revision.py apps/api/app/routes/lesson_ai.py apps/api/tests/test_ai_lesson_generation_api.py
git commit -m "feat: review ai lesson revisions"
```

### Task 8: Build Administrator Model Configuration UI

**Files:**
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/api.ts`
- Create: `apps/web/src/AiModelConfigPanel.tsx`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/api.test.ts`
- Modify: `apps/web/src/App.test.tsx`

- [ ] **Step 1: Add failing API and component tests**

Test masked loading, preserving a blank key, connection testing, enabling only after connection, and hiding the panel from teachers.

- [ ] **Step 2: Run tests and verify missing exports/components fail**

Run: `cd apps/web && npm test -- --run src/api.test.ts src/App.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Add typed API calls**

```typescript
export function getAiModelConfig(): Promise<AiModelConfig> {
  return request<AiModelConfig>("/admin/ai-model");
}
export function updateAiModelConfig(payload: AiModelConfigUpdate): Promise<AiModelConfig> {
  return request<AiModelConfig>("/admin/ai-model", { method: "PUT", body: JSON.stringify(payload) });
}
export function testAiModelConfig(): Promise<AiModelConfig> {
  return request<AiModelConfig>("/admin/ai-model/test", { method: "POST" });
}
```

- [ ] **Step 4: Implement a compact admin panel**

Use URL, model, password, save, test, and enable controls. Display only masked key status and connection status. Keep it as a full-width admin section, not a nested card.

- [ ] **Step 5: Run focused frontend tests**

Run: `cd apps/web && npm test -- --run src/api.test.ts src/App.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/types.ts apps/web/src/api.ts apps/web/src/AiModelConfigPanel.tsx apps/web/src/App.tsx apps/web/src/api.test.ts apps/web/src/App.test.tsx
git commit -m "feat: configure ai model in admin"
```

### Task 9: Replace Generic Generation With Persisted Progress UI

**Files:**
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/api.ts`
- Create: `apps/web/src/LessonGenerationProgress.tsx`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/api.test.ts`
- Modify: `apps/web/src/App.test.tsx`

- [ ] **Step 1: Add failing tests for starting, polling, partial failure, and retry**

Use fake timers to progress `pending -> running -> completed_with_errors`. Assert successful lessons remain visible and retry targets only the failed item.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `cd apps/web && npm test -- --run src/api.test.ts src/App.test.tsx`
Expected: FAIL because run APIs and progress UI are absent.

- [ ] **Step 3: Add run contracts and calls**

```typescript
export type LessonGenerationRun = {
  id: number;
  task_id: number;
  status: "pending" | "running" | "completed" | "completed_with_errors" | "failed";
  total_items: number;
  succeeded_items: number;
  failed_items: number;
  items: LessonGenerationItem[];
};
```

Add `startLessonGeneration`, `getLessonGenerationRun`, and `retryLessonGenerationItem`.

- [ ] **Step 4: Implement progress polling and restore-on-reload**

Poll every two seconds only while pending/running, clear the timer on unmount, reload lesson plans after each terminal update, and persist the active run id in task-scoped local storage. Display one compact row per session with retry only on failed rows.

- [ ] **Step 5: Run frontend tests**

Run: `cd apps/web && npm test -- --run src/api.test.ts src/App.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/types.ts apps/web/src/api.ts apps/web/src/LessonGenerationProgress.tsx apps/web/src/App.tsx apps/web/src/api.test.ts apps/web/src/App.test.tsx
git commit -m "feat: show lesson generation progress"
```

### Task 10: Add Local Regeneration Comparison UI

**Files:**
- Modify: `apps/web/src/types.ts`
- Modify: `apps/web/src/api.ts`
- Create: `apps/web/src/LessonRevisionControl.tsx`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/api.test.ts`
- Modify: `apps/web/src/App.test.tsx`

- [ ] **Step 1: Add failing tests for candidate preview, accept, and reject**

Assert generation does not change the textarea, acceptance updates only the selected field, rejection closes the comparison, and API failure preserves current content.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `cd apps/web && npm test -- --run src/api.test.ts src/App.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Add candidate API calls and component**

The component receives task id, lesson, field name, current content, and `onAccepted`. It offers one optional instruction, generates a candidate, renders original and proposed text in a responsive two-column comparison, and has explicit accept/reject buttons.

- [ ] **Step 4: Integrate controls beside the five supported lesson fields**

Keep goal and ability-code controls locked to confirmed values. Do not add regeneration to reflection or code fields.

- [ ] **Step 5: Run frontend tests and production build**

Run: `cd apps/web && npm test -- --run && $env:VITE_BASE_PATH='/design/'; $env:VITE_API_BASE_URL='/design/api'; npm run build`
Expected: 0 failed tests and successful Vite build.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/types.ts apps/web/src/api.ts apps/web/src/LessonRevisionControl.tsx apps/web/src/App.tsx apps/web/src/api.test.ts apps/web/src/App.test.tsx
git commit -m "feat: compare ai lesson revisions"
```

### Task 11: Full Verification And Deployment Configuration

**Files:**
- Modify: `.env.example`
- Modify: `docs/deployment/tencent-lighthouse.md`

- [ ] **Step 1: Document required server settings without secrets**

Add `MODEL_CONFIG_ENCRYPTION_KEY` generation instructions and the existing `/design/api` build variables. State that the key must live in a root-readable systemd environment file and must never be committed.

- [ ] **Step 2: Run the complete backend suite**

Run: `cd apps/api && .venv/Scripts/python -m pytest -q`
Expected: all tests pass.

- [ ] **Step 3: Run the complete frontend suite and production build**

Run: `cd apps/web && npm test -- --run`
Expected: all tests pass.

Run: `cd apps/web && $env:VITE_BASE_PATH='/design/'; $env:VITE_API_BASE_URL='/design/api'; npm run build`
Expected: build succeeds and generated JavaScript contains `/design/api`, not `http://localhost:8000`.

- [ ] **Step 4: Verify browser workflows at desktop and mobile widths**

Verify admin model configuration, whole-course progress, failed-item retry, lesson editing, candidate comparison, and Word export. Confirm no horizontal overflow at 1440x900, 1024x768, and 390x844.

- [ ] **Step 5: Commit documentation**

```bash
git add .env.example docs/deployment/tencent-lighthouse.md
git commit -m "docs: configure grounded lesson generation"
```

- [ ] **Step 6: Deploy with backup and production smoke checks**

Back up `/opt/teaching-design-system`, `/var/lib/teaching-design-system`, the teaching systemd unit, and the teaching Nginx paths. Add the encryption key only to the teaching service environment, install dependencies, restart `teaching-design.service`, and atomically replace `/var/www/teaching-design-system/design`. Verify both `teaching-design.service` and `teacher-achievement.service` are active, `/design/` and `/design/api/health` return 200, model configuration is admin-only, and the root achievement system still responds.
