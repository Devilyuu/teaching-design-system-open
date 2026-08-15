# AI-Grounded Whole-Course Lesson Generation Design

## Purpose

Improve lesson-plan quality without turning the system into an unconstrained text generator. A teacher still clicks once to generate the whole course, while the system internally generates and validates one scheduled session at a time. The resulting lesson plans remain editable and export through the existing Word-template workflow.

The first release optimizes the central lesson-plan artifact. Assignment and test quality, cross-semester reuse, external retrieval, and knowledge graphs remain outside this scope.

## Product Rules

1. Talent-plan ability codes and course-standard references are authoritative data, not model suggestions.
2. An ability code may be used only when it appears in both the confirmed talent plan and the confirmed course standard.
3. Code comparison permits only harmless parser normalization such as trimming whitespace and normalizing full-width punctuation. The stored and displayed code remains the source form.
4. If the same code has conflicting definitions, or a referenced code is missing or ambiguous, generation is blocked until the teacher resolves the source review.
5. The model may enrich teaching activities, examples, questions, and wording. These additions are marked as intelligent suggestions until the teacher saves them.
6. The model may not invent, rewrite, infer, or silently replace course-goal or ability codes.
7. The model does not browse the internet in this release. Hard teaching evidence comes only from teacher-uploaded and confirmed materials.

## User Flow

1. The teacher uploads and confirms the talent plan and course standard, then finalizes the course implementation outline.
2. The teacher clicks `Generate whole-course lesson plans` once.
3. The system runs a source and code preflight. Any unresolved source conflict stops the run with an actionable message.
4. The system creates one generation item for each outline row and processes at most two items concurrently.
5. Successful lesson plans are saved immediately as drafts. A failed item does not discard successful items.
6. The teacher reviews progress and opens any session from the lesson list.
7. The teacher edits content directly or requests regeneration of one supported field with an optional instruction.
8. A local regeneration produces a comparison candidate. The existing lesson changes only after the teacher accepts it.
9. After review, the teacher exports the entire course through the existing lesson-plan Word template.

## Architecture

### 1. Authoritative Evidence Builder

The evidence builder reads only confirmed parsed sources and the finalized outline. It produces:

- confirmed course goals;
- the allowed ability-code set and source definitions;
- the current outline row, scheduled date, session hours, and teaching content;
- adjacent-session titles for continuity;
- existing teacher edits when regenerating a field.

It rejects the request before any model call when the allowed code set is incomplete or contradictory.

### 2. Model Adapter

One OpenAI-compatible adapter owns request formatting, authentication, timeout handling, and structured-response parsing. Business services depend on this adapter interface rather than a named model provider.

The adapter requests a fixed lesson schema containing:

- lesson title and teaching objectives;
- key and difficult points;
- teaching preparation;
- timed teaching-process segments;
- teacher activities and student activities;
- questions, checks for learning, summary, and after-class task;
- course-goal and ability-code references selected only from the supplied allowlist.

For the common art-and-design schedule, process minutes must total four 40-minute periods. Other courses use the configured hours per session.

### 3. Generation Orchestrator

The orchestrator creates a whole-course run, then generates one session per item with a concurrency limit of two. Each item has `pending`, `running`, `succeeded`, or `failed` status and records attempt count, duration, and a sanitized error type.

Malformed output, timeout, or validation failure is retried once. The second failure remains visible for manual retry. Re-running a failed item does not regenerate successful teacher-reviewed lessons.

### 4. Deterministic Validator

Model output is not persisted until deterministic checks pass:

- every ability code belongs to the confirmed allowlist;
- every course-goal code belongs to the confirmed goal set;
- required fields are present;
- process minutes match the session duration;
- structured arrays and text fields respect schema and size limits;
- the model did not return an unrequested code in prose-only code fields.

Validation errors are machine-readable so the orchestrator can retry and the interface can explain the failure.

### 5. Candidate Review Service

Local regeneration supports the main editable fields: objectives, key and difficult points, preparation, teaching process, summary, and after-class task. It stores the original snapshot and proposed content as a pending candidate. Accepting replaces only that field; rejecting leaves the lesson unchanged.

## Data Model

### `AiModelConfig`

A singleton administrator-owned configuration with provider base URL, model name, encrypted API key, enabled state, connection-test status, and last-tested time. The API key is encrypted using a server environment secret and is never returned to the browser.

### `LessonGenerationRun`

Stores task, initiator, overall status, item counts, start time, and finish time.

### `LessonGenerationItem`

Stores run, outline row, lesson plan, status, attempts, duration, and sanitized error code. It supports progress polling and retrying one failed session.

### `LessonRevisionCandidate`

Stores lesson plan, field name, original snapshot, proposed content, optional teacher instruction, and `pending`, `accepted`, or `rejected` status.

Existing `LessonPlan` records remain the canonical editable and exportable content. No parallel filing/execution/revision version system is introduced.

## API Surface

Administrator endpoints:

- read masked model configuration;
- update model configuration;
- test model connectivity;
- enable or disable AI generation.

Teacher endpoints:

- start a whole-course generation run;
- read run and per-session progress;
- retry one failed generation item;
- create a field-level regeneration candidate;
- accept or reject a candidate.

All endpoints reuse existing employee-number authentication and task ownership rules. Only administrators can read or change model configuration.

## Interface Design

The lesson workspace keeps the existing whole-course action and expands the editing surface:

- a compact progress header shows generated, pending-review, and failed counts;
- a left session list shows date, lesson title, and status;
- the main editor gives most of the page width to lesson fields;
- confirmed course goals and ability codes are locked selectors sourced from the evidence allowlist;
- AI-enriched activities, examples, and questions carry an `Intelligent suggestion` label until saved;
- each major field offers local regeneration with one optional teacher instruction;
- a side-by-side or stacked comparison appears before replacement;
- Word export continues to produce one complete course document without changing template formatting.

## Failure Handling

- Missing configuration: block generation and direct the user to an administrator.
- Failed connection test: configuration cannot be enabled.
- Source mismatch: block before model usage and link to source review.
- Timeout, rate limit, malformed JSON, or schema failure: retry once, then mark only that session failed.
- Candidate generation failure: preserve the current field exactly.
- Page reload during generation: restore run progress from persisted run items.
- Model outage: existing lesson plans, manual editing, and Word export remain available.

Logs contain task/session identifiers, status, duration, attempt count, and sanitized error type. They do not contain API keys or complete uploaded documents.

## Security

- API keys are encrypted at rest and never sent to teachers or written to logs.
- Only the minimum evidence package needed for one session is sent to the configured model endpoint.
- The interface warns administrators that the endpoint receives selected school teaching content.
- Model configuration changes and connection tests require administrator authorization.
- Generated HTML is not trusted; lesson content is stored and rendered as plain structured text.

## Testing And Acceptance

Automated tests cover:

- exact ability-code allowlisting and source-conflict blocking;
- model adapter request and structured response parsing;
- rejection of invented goal or ability codes;
- duration-total validation for four 40-minute periods;
- retry-once behavior and partial-run preservation;
- field candidate creation, acceptance, rejection, and no-overwrite-on-failure;
- administrator-only model configuration and masked secret responses;
- whole-course progress restoration after reload;
- existing manual editing and Word export regression coverage.

The feature is accepted when a teacher can configure a compatible model through an administrator, click once to generate all scheduled lessons, retain successful lessons if individual sessions fail, locally regenerate one field with a comparison step, and export the reviewed whole-course lesson plan while no unconfirmed ability code can enter the saved document.

## Explicit Non-Goals

- student accounts, submissions, or grading workflows;
- internet search or external retrieval-augmented generation;
- assignment and examination generation improvements;
- cross-semester resource inheritance;
- multi-version filing workflows;
- knowledge-graph generation.
