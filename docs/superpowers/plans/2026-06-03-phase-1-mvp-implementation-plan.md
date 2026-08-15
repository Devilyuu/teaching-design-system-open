# Phase 1 MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first runnable MVP slice for the teaching design system: project skeleton, teacher task creation, course standard parsing, ability indicator lookup, Excel schedule import, editable course outline rows, and DOCX placeholder export.

**Architecture:** Use a small monorepo with a React/Vite frontend and Python/FastAPI backend. Keep document parsing and DOCX generation in focused backend service modules, store structured task data in SQLite, and expose simple JSON APIs consumed by the web app.

**Tech Stack:** React, Vite, TypeScript, Python 3.12, FastAPI, SQLModel, SQLite, python-docx, openpyxl, pytest, vitest.

---

## Delivery Roadmap

Phase 1 creates a working vertical slice:

- Teacher creates a备课任务.
- Teacher uploads or imports structured course standard data.
- System stores `M -> 能力指标代码` relationships.
- Teacher uploads an Excel schedule.
- System creates editable course implementation outline rows.
- Teacher exports a DOCX through a placeholder template.

Later phases:

- Phase 2: smart Word template recognition, PDF schedule confirmation, richer course implementation outline generation.
- Phase 3: lesson plan generation with `K -> M -> ability code` validation and single/all lesson DOCX export.
- Phase 4: assignment/test generation, web editing, Word export, and generation history.
- Phase 5: administrator libraries, AI configuration, logs, quality checks, and deployment hardening.

## File Structure

Create:

- `README.md`: local setup and development commands.
- `.env.example`: local environment variable names without secrets.
- `apps/api/pyproject.toml`: backend dependencies and test config.
- `apps/api/app/main.py`: FastAPI app entrypoint.
- `apps/api/app/db.py`: SQLite engine/session setup.
- `apps/api/app/models.py`: SQLModel data models.
- `apps/api/app/schemas.py`: request/response DTOs.
- `apps/api/app/services/course_standard_parser.py`: parse course standard DOCX tables into course goals and ability codes.
- `apps/api/app/services/schedule_parser.py`: parse Excel schedule rows into structured sessions.
- `apps/api/app/services/outline_generator.py`: create course implementation outline rows from course goals and schedule sessions.
- `apps/api/app/services/docx_exporter.py`: fill DOCX placeholders without changing unrelated formatting.
- `apps/api/app/routes/tasks.py`: teaching task CRUD and generation routes.
- `apps/api/app/routes/uploads.py`: file upload endpoints.
- `apps/api/tests/test_course_standard_parser.py`: parser tests.
- `apps/api/tests/test_schedule_parser.py`: schedule parser tests.
- `apps/api/tests/test_outline_generator.py`: outline generation tests.
- `apps/api/tests/test_docx_exporter.py`: DOCX placeholder export tests.
- `apps/web/package.json`: frontend dependencies and scripts.
- `apps/web/index.html`: Vite entry HTML.
- `apps/web/src/main.tsx`: React entrypoint.
- `apps/web/src/api.ts`: typed API client.
- `apps/web/src/App.tsx`: app shell and simple routing.
- `apps/web/src/pages/DashboardPage.tsx`: task list and create entry.
- `apps/web/src/pages/NewTaskPage.tsx`: task creation form.
- `apps/web/src/pages/OutlineEditorPage.tsx`: editable course implementation outline table.
- `apps/web/src/components/EditableOutlineTable.tsx`: table editor component.
- `apps/web/src/types.ts`: shared frontend types.
- `apps/web/src/App.test.tsx`: smoke test.

Modify:

- `.gitignore`: add app artifacts such as SQLite files, upload folders, frontend build outputs, and dependency folders.

Do not add:

- `cankao/`
- Raw school DOCX/PDF files
- API keys
- Generated Word outputs

## Task 1: Repository Hygiene and Documentation

**Files:**
- Modify: `.gitignore`
- Create: `README.md`
- Create: `.env.example`

- [ ] **Step 1: Extend `.gitignore`**

Add these lines below the existing rules:

```gitignore
# App runtime artifacts
apps/api/.venv/
apps/api/.pytest_cache/
apps/api/*.db
apps/api/uploads/
apps/api/generated/

apps/web/node_modules/
apps/web/dist/
apps/web/.vite/

# Local editor files
.DS_Store
Thumbs.db
```

- [ ] **Step 2: Create `README.md`**

```markdown
# Teaching Design System

Web-based intelligent preparation document generation system for vocational college teachers.

## MVP Scope

Phase 1 supports:

- Teaching task creation
- Course standard parsing
- Ability indicator mapping
- Excel schedule import
- Course implementation outline row generation and editing
- DOCX placeholder export

Internal school materials are intentionally excluded from Git.

## Local Development

Backend:

```powershell
cd apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

Frontend:

```powershell
cd apps/web
npm install
npm run dev
```

Run backend tests:

```powershell
cd apps/api
pytest
```

Run frontend tests:

```powershell
cd apps/web
npm test
```
```

- [ ] **Step 3: Create `.env.example`**

```env
DATABASE_URL=sqlite:///./teaching_design.db
UPLOAD_DIR=./uploads
GENERATED_DIR=./generated
OPENAI_API_KEY=
MODEL_NAME=
```

- [ ] **Step 4: Verify status**

Run:

```powershell
git status -sb
```

Expected: only `.gitignore`, `README.md`, `.env.example`, and planned app files appear as changed/untracked.

- [ ] **Step 5: Commit**

```powershell
git add .gitignore README.md .env.example
git commit -m "chore: document local development setup"
```

## Task 2: Backend Project Skeleton

**Files:**
- Create: `apps/api/pyproject.toml`
- Create: `apps/api/app/main.py`
- Create: `apps/api/app/db.py`
- Create: `apps/api/app/models.py`
- Create: `apps/api/app/schemas.py`
- Create: `apps/api/app/routes/tasks.py`
- Create: `apps/api/app/routes/uploads.py`

- [ ] **Step 1: Create backend package directories**

```powershell
New-Item -ItemType Directory -Force apps/api/app/routes, apps/api/app/services, apps/api/tests | Out-Null
New-Item -ItemType File -Force apps/api/app/__init__.py, apps/api/app/routes/__init__.py, apps/api/app/services/__init__.py | Out-Null
```

- [ ] **Step 2: Create `apps/api/pyproject.toml`**

```toml
[project]
name = "teaching-design-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.30.0",
  "sqlmodel>=0.0.22",
  "python-multipart>=0.0.9",
  "python-docx>=1.1.2",
  "openpyxl>=3.1.5",
  "pydantic-settings>=2.4.0"
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3.0",
  "httpx>=0.27.0"
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 3: Create `apps/api/app/db.py`**

```python
from sqlmodel import SQLModel, Session, create_engine

DATABASE_URL = "sqlite:///./teaching_design.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
```

- [ ] **Step 4: Create `apps/api/app/models.py`**

```python
from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class TeachingTask(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    term: str
    major: str
    class_name: str
    course_name: str
    teacher_name: str
    location: str
    total_hours: int = 32
    hours_per_session: int = 4
    status: str = "materials_pending"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CourseGoal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: int = Field(index=True)
    code: str
    description: str
    ability_codes: str


class OutlineRow(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: int = Field(index=True)
    session_no: int
    date_text: str
    week_no: int
    weekday: str
    periods: str
    topic: str
    teaching_content: str
    ideological_point: str = ""
    teaching_methods: str = ""
    pre_task: str = ""
    in_class_task: str = ""
    post_task: str = ""
    course_goal_codes: str = ""
    ability_codes: str = ""
    note: str = ""
```

- [ ] **Step 5: Create `apps/api/app/schemas.py`**

```python
from pydantic import BaseModel


class TeachingTaskCreate(BaseModel):
    term: str
    major: str
    class_name: str
    course_name: str
    teacher_name: str
    location: str
    total_hours: int = 32
    hours_per_session: int = 4


class TeachingTaskRead(TeachingTaskCreate):
    id: int
    status: str


class OutlineRowRead(BaseModel):
    id: int
    session_no: int
    date_text: str
    week_no: int
    weekday: str
    periods: str
    topic: str
    teaching_content: str
    ideological_point: str
    teaching_methods: str
    pre_task: str
    in_class_task: str
    post_task: str
    course_goal_codes: str
    ability_codes: str
    note: str


class OutlineRowUpdate(BaseModel):
    date_text: str
    week_no: int
    weekday: str
    periods: str
    topic: str
    teaching_content: str
    ideological_point: str = ""
    teaching_methods: str = ""
    pre_task: str = ""
    in_class_task: str = ""
    post_task: str = ""
    course_goal_codes: str = ""
    ability_codes: str = ""
    note: str = ""
```

- [ ] **Step 6: Create `apps/api/app/routes/tasks.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.db import get_session
from app.models import OutlineRow, TeachingTask
from app.schemas import OutlineRowRead, OutlineRowUpdate, TeachingTaskCreate, TeachingTaskRead

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TeachingTaskRead)
def create_task(payload: TeachingTaskCreate, session: Session = Depends(get_session)):
    task = TeachingTask(**payload.model_dump())
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@router.get("", response_model=list[TeachingTaskRead])
def list_tasks(session: Session = Depends(get_session)):
    return session.exec(select(TeachingTask).order_by(TeachingTask.created_at.desc())).all()


@router.get("/{task_id}/outline", response_model=list[OutlineRowRead])
def list_outline_rows(task_id: int, session: Session = Depends(get_session)):
    return session.exec(
        select(OutlineRow).where(OutlineRow.task_id == task_id).order_by(OutlineRow.session_no)
    ).all()


@router.put("/{task_id}/outline/{row_id}", response_model=OutlineRowRead)
def update_outline_row(
    task_id: int,
    row_id: int,
    payload: OutlineRowUpdate,
    session: Session = Depends(get_session),
):
    row = session.get(OutlineRow, row_id)
    if row is None or row.task_id != task_id:
        raise HTTPException(status_code=404, detail="Outline row not found")
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row
```

- [ ] **Step 7: Create `apps/api/app/routes/uploads.py`**

```python
from pathlib import Path
from fastapi import APIRouter, File, UploadFile

router = APIRouter(prefix="/uploads", tags=["uploads"])
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("")
async def upload_file(file: UploadFile = File(...)):
    target = UPLOAD_DIR / file.filename
    content = await file.read()
    target.write_bytes(content)
    return {"filename": file.filename, "size": len(content)}
```

- [ ] **Step 8: Create `apps/api/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db import init_db
from app.routes import tasks, uploads

app = FastAPI(title="Teaching Design System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(tasks.router)
app.include_router(uploads.router)
```

- [ ] **Step 9: Run backend smoke test**

Run:

```powershell
cd apps/api
python -m pip install -e ".[dev]"
pytest
```

Expected: pytest runs and reports no tests collected or passing tests once later tasks add them.

- [ ] **Step 10: Commit**

```powershell
git add apps/api
git commit -m "feat: add backend api skeleton"
```

## Task 3: Course Standard Parser

**Files:**
- Create: `apps/api/app/services/course_standard_parser.py`
- Test: `apps/api/tests/test_course_standard_parser.py`

- [ ] **Step 1: Write failing parser test**

```python
from pathlib import Path
from docx import Document
from app.services.course_standard_parser import parse_course_standard


def make_docx(path: Path) -> None:
    doc = Document()
    table = doc.add_table(rows=5, cols=3)
    table.cell(0, 0).text = "编号"
    table.cell(0, 1).text = "课程教学目标"
    table.cell(0, 2).text = "对应的知识能力素养集"
    table.cell(1, 0).text = "M1"
    table.cell(1, 1).text = "【知识】理解AIGC基础"
    table.cell(1, 2).text = "1-3-4, 1-3-5"
    table.cell(2, 0).text = "M2"
    table.cell(2, 1).text = "【能力】完成AI创意项目"
    table.cell(2, 2).text = "2-3-4 2-3-5"
    table.cell(3, 0).text = "M3"
    table.cell(3, 1).text = "【素养】形成审美判断"
    table.cell(3, 2).text = "3-2-1, 3-3-3"
    table.cell(4, 0).text = "M4"
    table.cell(4, 1).text = "【素养】塑造求实创新精神"
    table.cell(4, 2).text = "3-5-1"
    doc.save(path)


def test_parse_course_goals_from_standard(tmp_path):
    path = tmp_path / "standard.docx"
    make_docx(path)

    result = parse_course_standard(path)

    assert [goal.code for goal in result.goals] == ["M1", "M2", "M3", "M4"]
    assert result.goals[0].ability_codes == ["1-3-4", "1-3-5"]
    assert result.goals[1].ability_codes == ["2-3-4", "2-3-5"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd apps/api
pytest tests/test_course_standard_parser.py -v
```

Expected: FAIL because `app.services.course_standard_parser` does not exist.

- [ ] **Step 3: Implement parser**

```python
from dataclasses import dataclass
from pathlib import Path
import re
from docx import Document

ABILITY_CODE_RE = re.compile(r"\d+-\d+-\d+")


@dataclass
class ParsedCourseGoal:
    code: str
    description: str
    ability_codes: list[str]


@dataclass
class ParsedCourseStandard:
    goals: list[ParsedCourseGoal]


def _cell_text(cell) -> str:
    return " ".join(cell.text.split())


def parse_course_standard(path: Path | str) -> ParsedCourseStandard:
    doc = Document(str(path))
    goals: list[ParsedCourseGoal] = []

    for table in doc.tables:
        rows = [[_cell_text(cell) for cell in row.cells] for row in table.rows]
        if not rows:
            continue
        header = rows[0]
        if "编号" not in header or not any("课程教学目标" in item for item in header):
            continue
        for row in rows[1:]:
            if len(row) < 3:
                continue
            code = row[0].strip()
            if not re.fullmatch(r"M\d+", code):
                continue
            ability_codes = ABILITY_CODE_RE.findall(row[2])
            goals.append(
                ParsedCourseGoal(
                    code=code,
                    description=row[1].strip(),
                    ability_codes=ability_codes,
                )
            )

    return ParsedCourseStandard(goals=goals)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
cd apps/api
pytest tests/test_course_standard_parser.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/services/course_standard_parser.py apps/api/tests/test_course_standard_parser.py
git commit -m "feat: parse course standard goals"
```

## Task 4: Excel Schedule Parser

**Files:**
- Create: `apps/api/app/services/schedule_parser.py`
- Test: `apps/api/tests/test_schedule_parser.py`

- [ ] **Step 1: Write failing parser test**

```python
from pathlib import Path
from openpyxl import Workbook
from app.services.schedule_parser import parse_schedule


def make_xlsx(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.append(["周次", "日期", "星期", "节次", "课程", "班级", "地点"])
    ws.append([1, "2026-09-07", "一", "1-4", "人工智能与创意设计", "数字艺术25级1班", "智慧教室"])
    ws.append([2, "2026-09-14", "一", "1-4", "人工智能与创意设计", "数字艺术25级1班", "智慧教室"])
    wb.save(path)


def test_parse_schedule_rows(tmp_path):
    path = tmp_path / "schedule.xlsx"
    make_xlsx(path)

    sessions = parse_schedule(path)

    assert len(sessions) == 2
    assert sessions[0].week_no == 1
    assert sessions[0].periods == "1-4"
    assert sessions[0].hours == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd apps/api
pytest tests/test_schedule_parser.py -v
```

Expected: FAIL because `schedule_parser` does not exist.

- [ ] **Step 3: Implement parser**

```python
from dataclasses import dataclass
from pathlib import Path
from openpyxl import load_workbook


@dataclass
class ScheduleSession:
    week_no: int
    date_text: str
    weekday: str
    periods: str
    course_name: str
    class_name: str
    location: str
    hours: int


def _norm(value) -> str:
    return "" if value is None else str(value).strip()


def _hours_from_periods(periods: str) -> int:
    if "-" not in periods:
        return 1
    start, end = periods.split("-", 1)
    return int(end) - int(start) + 1


def parse_schedule(path: Path | str) -> list[ScheduleSession]:
    wb = load_workbook(path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []

    header = [_norm(value) for value in rows[0]]
    index = {name: idx for idx, name in enumerate(header)}
    required = ["周次", "日期", "星期", "节次", "课程", "班级", "地点"]
    missing = [name for name in required if name not in index]
    if missing:
        raise ValueError(f"Missing schedule columns: {', '.join(missing)}")

    sessions: list[ScheduleSession] = []
    for row in rows[1:]:
        periods = _norm(row[index["节次"]])
        if not periods:
            continue
        sessions.append(
            ScheduleSession(
                week_no=int(row[index["周次"]]),
                date_text=_norm(row[index["日期"]]),
                weekday=_norm(row[index["星期"]]),
                periods=periods,
                course_name=_norm(row[index["课程"]]),
                class_name=_norm(row[index["班级"]]),
                location=_norm(row[index["地点"]]),
                hours=_hours_from_periods(periods),
            )
        )
    return sessions
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
cd apps/api
pytest tests/test_schedule_parser.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/services/schedule_parser.py apps/api/tests/test_schedule_parser.py
git commit -m "feat: parse excel schedule sessions"
```

## Task 5: Course Implementation Outline Generator

**Files:**
- Create: `apps/api/app/services/outline_generator.py`
- Test: `apps/api/tests/test_outline_generator.py`

- [ ] **Step 1: Write failing generator test**

```python
from app.services.course_standard_parser import ParsedCourseGoal
from app.services.outline_generator import generate_outline_rows
from app.services.schedule_parser import ScheduleSession


def test_generate_outline_rows_maps_sessions_to_goals():
    sessions = [
        ScheduleSession(1, "2026-09-07", "一", "1-4", "人工智能与创意设计", "数字艺术25级1班", "智慧教室", 4),
        ScheduleSession(2, "2026-09-14", "一", "1-4", "人工智能与创意设计", "数字艺术25级1班", "智慧教室", 4),
    ]
    goals = [
        ParsedCourseGoal("M1", "理解AIGC基础", ["1-3-4"]),
        ParsedCourseGoal("M2", "完成AI创意项目", ["2-3-4"]),
    ]

    rows = generate_outline_rows(sessions, goals)

    assert len(rows) == 2
    assert rows[0].session_no == 1
    assert rows[0].course_goal_codes == "M1"
    assert rows[1].course_goal_codes == "M2"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd apps/api
pytest tests/test_outline_generator.py -v
```

Expected: FAIL because `outline_generator` does not exist.

- [ ] **Step 3: Implement generator**

```python
from dataclasses import dataclass
from app.services.course_standard_parser import ParsedCourseGoal
from app.services.schedule_parser import ScheduleSession


@dataclass
class GeneratedOutlineRow:
    session_no: int
    date_text: str
    week_no: int
    weekday: str
    periods: str
    topic: str
    teaching_content: str
    ideological_point: str
    teaching_methods: str
    pre_task: str
    in_class_task: str
    post_task: str
    course_goal_codes: str
    ability_codes: str
    note: str = ""


def generate_outline_rows(
    sessions: list[ScheduleSession],
    goals: list[ParsedCourseGoal],
) -> list[GeneratedOutlineRow]:
    rows: list[GeneratedOutlineRow] = []
    if not goals:
        raise ValueError("At least one course goal is required")

    for index, session in enumerate(sessions):
        goal = goals[index % len(goals)]
        topic = f"第{index + 1}次课：{goal.description[:24]}"
        rows.append(
            GeneratedOutlineRow(
                session_no=index + 1,
                date_text=session.date_text,
                week_no=session.week_no,
                weekday=session.weekday,
                periods=session.periods,
                topic=topic,
                teaching_content=goal.description,
                ideological_point="职业规范与学习责任",
                teaching_methods="讲授、案例分析、任务驱动、实训操作",
                pre_task="预习本次课相关案例并记录问题。",
                in_class_task="完成本次课项目任务并保留过程记录。",
                post_task="完善课堂成果并提交阶段材料。",
                course_goal_codes=goal.code,
                ability_codes=" ".join(goal.ability_codes),
            )
        )
    return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
cd apps/api
pytest tests/test_outline_generator.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/services/outline_generator.py apps/api/tests/test_outline_generator.py
git commit -m "feat: generate course outline rows"
```

## Task 6: DOCX Placeholder Export

**Files:**
- Create: `apps/api/app/services/docx_exporter.py`
- Test: `apps/api/tests/test_docx_exporter.py`

- [ ] **Step 1: Write failing exporter test**

```python
from pathlib import Path
from docx import Document
from app.services.docx_exporter import fill_docx_placeholders


def test_fill_docx_placeholders_in_paragraphs_and_tables(tmp_path):
    template = tmp_path / "template.docx"
    output = tmp_path / "output.docx"

    doc = Document()
    doc.add_paragraph("课程：{{课程名称}}")
    table = doc.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "任课教师"
    table.cell(0, 1).text = "{{任课教师}}"
    doc.save(template)

    fill_docx_placeholders(
        template,
        output,
        {"课程名称": "人工智能与创意设计", "任课教师": "张明"},
    )

    rendered = Document(output)
    assert rendered.paragraphs[0].text == "课程：人工智能与创意设计"
    assert rendered.tables[0].cell(0, 1).text == "张明"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd apps/api
pytest tests/test_docx_exporter.py -v
```

Expected: FAIL because `docx_exporter` does not exist.

- [ ] **Step 3: Implement exporter**

```python
from pathlib import Path
from docx import Document


def _replace_in_paragraph(paragraph, values: dict[str, str]) -> None:
    full_text = paragraph.text
    replaced = full_text
    for key, value in values.items():
        replaced = replaced.replace(f"{{{{{key}}}}}", value)

    if replaced == full_text:
        return

    for run in paragraph.runs:
        run.text = ""
    if paragraph.runs:
        paragraph.runs[0].text = replaced
    else:
        paragraph.add_run(replaced)


def fill_docx_placeholders(
    template_path: Path | str,
    output_path: Path | str,
    values: dict[str, str],
) -> None:
    doc = Document(str(template_path))

    for paragraph in doc.paragraphs:
        _replace_in_paragraph(paragraph, values)

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    _replace_in_paragraph(paragraph, values)

    doc.save(str(output_path))
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
cd apps/api
pytest tests/test_docx_exporter.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/services/docx_exporter.py apps/api/tests/test_docx_exporter.py
git commit -m "feat: export placeholder docx"
```

## Task 7: Frontend Skeleton

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/index.html`
- Create: `apps/web/src/main.tsx`
- Create: `apps/web/src/App.tsx`
- Create: `apps/web/src/api.ts`
- Create: `apps/web/src/types.ts`
- Create: `apps/web/src/pages/DashboardPage.tsx`
- Create: `apps/web/src/pages/NewTaskPage.tsx`
- Create: `apps/web/src/pages/OutlineEditorPage.tsx`
- Create: `apps/web/src/components/EditableOutlineTable.tsx`
- Test: `apps/web/src/App.test.tsx`

- [ ] **Step 1: Create `apps/web/package.json`**

```json
{
  "name": "teaching-design-web",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "test": "vitest run"
  },
  "dependencies": {
    "@vitejs/plugin-react": "^5.0.0",
    "vite": "^7.0.0",
    "typescript": "^5.6.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "^6.6.0",
    "jsdom": "^25.0.0",
    "vitest": "^2.1.0"
  }
}
```

- [ ] **Step 2: Create Vite files**

`apps/web/index.html`:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>智能备课文档生成系统</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`apps/web/src/main.tsx`:

```tsx
import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 3: Create frontend types and API client**

`apps/web/src/types.ts`:

```ts
export interface TeachingTask {
  id: number;
  term: string;
  major: string;
  class_name: string;
  course_name: string;
  teacher_name: string;
  location: string;
  total_hours: number;
  hours_per_session: number;
  status: string;
}

export interface OutlineRow {
  id: number;
  session_no: number;
  date_text: string;
  week_no: number;
  weekday: string;
  periods: string;
  topic: string;
  teaching_content: string;
  ideological_point: string;
  teaching_methods: string;
  pre_task: string;
  in_class_task: string;
  post_task: string;
  course_goal_codes: string;
  ability_codes: string;
  note: string;
}
```

`apps/web/src/api.ts`:

```ts
import type { OutlineRow, TeachingTask } from "./types";

const API_BASE = "http://localhost:8000";

export async function listTasks(): Promise<TeachingTask[]> {
  const response = await fetch(`${API_BASE}/tasks`);
  if (!response.ok) throw new Error("Failed to load tasks");
  return response.json();
}

export async function createTask(payload: Omit<TeachingTask, "id" | "status">): Promise<TeachingTask> {
  const response = await fetch(`${API_BASE}/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Failed to create task");
  return response.json();
}

export async function listOutlineRows(taskId: number): Promise<OutlineRow[]> {
  const response = await fetch(`${API_BASE}/tasks/${taskId}/outline`);
  if (!response.ok) throw new Error("Failed to load outline rows");
  return response.json();
}
```

- [ ] **Step 4: Create simple pages**

`apps/web/src/App.tsx`:

```tsx
import { useState } from "react";
import { DashboardPage } from "./pages/DashboardPage";
import { NewTaskPage } from "./pages/NewTaskPage";
import { OutlineEditorPage } from "./pages/OutlineEditorPage";

type View = "dashboard" | "new-task" | "outline";

export function App() {
  const [view, setView] = useState<View>("dashboard");
  const [activeTaskId, setActiveTaskId] = useState<number | null>(null);

  if (view === "new-task") {
    return <NewTaskPage onDone={(taskId) => { setActiveTaskId(taskId); setView("outline"); }} />;
  }

  if (view === "outline" && activeTaskId) {
    return <OutlineEditorPage taskId={activeTaskId} onBack={() => setView("dashboard")} />;
  }

  return <DashboardPage onCreate={() => setView("new-task")} onOpen={(taskId) => { setActiveTaskId(taskId); setView("outline"); }} />;
}
```

`apps/web/src/pages/DashboardPage.tsx`:

```tsx
import { useEffect, useState } from "react";
import { listTasks } from "../api";
import type { TeachingTask } from "../types";

export function DashboardPage({ onCreate, onOpen }: { onCreate: () => void; onOpen: (taskId: number) => void }) {
  const [tasks, setTasks] = useState<TeachingTask[]>([]);

  useEffect(() => {
    listTasks().then(setTasks).catch(() => setTasks([]));
  }, []);

  return (
    <main>
      <h1>智能备课文档生成系统</h1>
      <button onClick={onCreate}>新建备课任务</button>
      <section>
        <h2>我的备课任务</h2>
        {tasks.map((task) => (
          <button key={task.id} onClick={() => onOpen(task.id)}>
            {task.course_name} / {task.class_name} / {task.status}
          </button>
        ))}
      </section>
    </main>
  );
}
```

- [ ] **Step 5: Create task form page**

`apps/web/src/pages/NewTaskPage.tsx`:

```tsx
import { FormEvent } from "react";
import { createTask } from "../api";

export function NewTaskPage({ onDone }: { onDone: (taskId: number) => void }) {
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const task = await createTask({
      term: String(data.get("term")),
      major: String(data.get("major")),
      class_name: String(data.get("class_name")),
      course_name: String(data.get("course_name")),
      teacher_name: String(data.get("teacher_name")),
      location: String(data.get("location")),
      total_hours: Number(data.get("total_hours")),
      hours_per_session: Number(data.get("hours_per_session")),
    });
    onDone(task.id);
  }

  return (
    <main>
      <h1>新建备课任务</h1>
      <form onSubmit={submit}>
        <input name="term" defaultValue="2026-2027 第一学期" aria-label="学期" />
        <input name="major" defaultValue="数字媒体艺术设计" aria-label="专业" />
        <input name="class_name" defaultValue="数字艺术25级1班" aria-label="班级" />
        <input name="course_name" defaultValue="人工智能与创意设计" aria-label="课程" />
        <input name="teacher_name" defaultValue="张明" aria-label="任课教师" />
        <input name="location" defaultValue="智慧教室/数字媒体实训室" aria-label="上课地点" />
        <input name="total_hours" type="number" defaultValue={32} aria-label="课程总学时" />
        <input name="hours_per_session" type="number" defaultValue={4} aria-label="每次课学时" />
        <button type="submit">创建</button>
      </form>
    </main>
  );
}
```

- [ ] **Step 6: Create outline editor components**

`apps/web/src/components/EditableOutlineTable.tsx`:

```tsx
import type { OutlineRow } from "../types";

export function EditableOutlineTable({ rows }: { rows: OutlineRow[] }) {
  return (
    <table>
      <thead>
        <tr>
          <th>课次</th>
          <th>日期</th>
          <th>周次</th>
          <th>节次</th>
          <th>教学内容</th>
          <th>课程目标</th>
          <th>能力指标代码</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.id}>
            <td>{row.session_no}</td>
            <td>{row.date_text}</td>
            <td>{row.week_no}</td>
            <td>{row.periods}</td>
            <td>{row.teaching_content}</td>
            <td>{row.course_goal_codes}</td>
            <td>{row.ability_codes}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

`apps/web/src/pages/OutlineEditorPage.tsx`:

```tsx
import { useEffect, useState } from "react";
import { listOutlineRows } from "../api";
import { EditableOutlineTable } from "../components/EditableOutlineTable";
import type { OutlineRow } from "../types";

export function OutlineEditorPage({ taskId, onBack }: { taskId: number; onBack: () => void }) {
  const [rows, setRows] = useState<OutlineRow[]>([]);

  useEffect(() => {
    listOutlineRows(taskId).then(setRows).catch(() => setRows([]));
  }, [taskId]);

  return (
    <main>
      <button onClick={onBack}>返回</button>
      <h1>课程实施大纲</h1>
      <EditableOutlineTable rows={rows} />
    </main>
  );
}
```

- [ ] **Step 7: Add smoke test**

`apps/web/src/App.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { App } from "./App";

test("renders dashboard title", () => {
  render(<App />);
  expect(screen.getByText("智能备课文档生成系统")).toBeInTheDocument();
});
```

- [ ] **Step 8: Run frontend checks**

Run:

```powershell
cd apps/web
npm install
npm test
npm run build
```

Expected: test and build pass.

- [ ] **Step 9: Commit**

```powershell
git add apps/web
git commit -m "feat: add frontend mvp skeleton"
```

## Task 8: Integration Route for Outline Generation

**Files:**
- Modify: `apps/api/app/routes/tasks.py`
- Test: `apps/api/tests/test_outline_generator.py`

- [ ] **Step 1: Add route test using TestClient**

Append to `apps/api/tests/test_outline_generator.py`:

```python
from fastapi.testclient import TestClient
from app.main import app


def test_create_task_endpoint():
    client = TestClient(app)
    response = client.post(
        "/tasks",
        json={
            "term": "2026-2027 第一学期",
            "major": "数字媒体艺术设计",
            "class_name": "数字艺术25级1班",
            "course_name": "人工智能与创意设计",
            "teacher_name": "张明",
            "location": "智慧教室",
            "total_hours": 32,
            "hours_per_session": 4,
        },
    )

    assert response.status_code == 200
    assert response.json()["course_name"] == "人工智能与创意设计"
```

- [ ] **Step 2: Run route test**

Run:

```powershell
cd apps/api
pytest tests/test_outline_generator.py::test_create_task_endpoint -v
```

Expected: PASS after Task 2 skeleton exists.

- [ ] **Step 3: Commit**

```powershell
git add apps/api/tests/test_outline_generator.py
git commit -m "test: cover task creation endpoint"
```

## Task 9: Manual MVP Verification

**Files:**
- No file changes required unless bugs are found.

- [ ] **Step 1: Start backend**

Run:

```powershell
cd apps/api
uvicorn app.main:app --reload --port 8000
```

Expected: API starts and `/health` returns `{"status":"ok"}`.

- [ ] **Step 2: Start frontend**

Run in a second terminal:

```powershell
cd apps/web
npm run dev
```

Expected: Vite shows a local URL, usually `http://localhost:5173`.

- [ ] **Step 3: Create task through UI**

Open `http://localhost:5173`, click `新建备课任务`, submit defaults.

Expected: app navigates to `课程实施大纲` page.

- [ ] **Step 4: Run full backend tests**

Run:

```powershell
cd apps/api
pytest -v
```

Expected: all backend tests pass.

- [ ] **Step 5: Run frontend checks**

Run:

```powershell
cd apps/web
npm test
npm run build
```

Expected: test and build pass.

- [ ] **Step 6: Commit any verification fixes**

If fixes were required:

```powershell
git add apps/api apps/web
git commit -m "fix: stabilize mvp verification"
```

## Self-Review

Spec coverage:

- Teacher task creation: Task 2 and Task 7.
- Course standard parsing: Task 3.
- Ability indicator relationships: Task 3 and Task 5.
- Excel schedule parsing: Task 4.
- Course implementation outline row generation: Task 5.
- DOCX placeholder export: Task 6.
- Frontend outline editing surface: Task 7.
- Backend verification: Task 8 and Task 9.

Known Phase 1 gaps intentionally deferred:

- PDF schedule parsing with manual confirmation.
- Smart Word template recognition without placeholders.
- Lesson plan generation.
- Assignment/test generation.
- Administrator UI.
- External model API integration.
- Full `K -> M -> ability code` lesson validation.

These deferred items are part of later phases and are not hidden scope.
