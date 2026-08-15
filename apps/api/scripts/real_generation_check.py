r"""Run the whole generation pipeline against the real model and real course materials.

Everything the automated suite exercises is mocked, so nothing in it says whether the
generated teaching content is usable. This script answers that one question: it drives
the production HTTP routes with the school's own talent plan and course standard, calls
the configured model for real, and writes the result out for a human to read.

It never prints or stores the API key, and it never touches the development database:
both the database and the upload directory are created fresh under --out.

Usage (PowerShell):

    $env:DEEPSEEK_API_KEY = "<key>"      # or put it in apps/api/.env
    cd apps/api
    .\.venv\Scripts\python.exe scripts\real_generation_check.py

Add --dry-run to verify parsing, evidence and prompts without spending a single token.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = API_DIR.parent.parent
sys.path.insert(0, str(API_DIR))


def read_api_key() -> str:
    """Take the key from the environment, falling back to the gitignored apps/api/.env."""
    for name in ("DEEPSEEK_API_KEY", "MODEL_API_KEY", "OPENAI_API_KEY"):
        value = os.getenv(name, "").strip()
        if value:
            return value
    env_file = API_DIR / ".env"
    if env_file.exists():
        # errors="ignore" so a file saved as ANSI on Windows still yields the
        # ASCII key line instead of blowing up on a Chinese comment.
        for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.lstrip().startswith("#"):
                continue
            key, _, value = line.partition("=")
            if key.strip() in ("DEEPSEEK_API_KEY", "MODEL_API_KEY", "OPENAI_API_KEY"):
                return value.strip().strip('"').strip("'")
    return ""


def build_schedule(path: Path, sessions: int, periods_per_session: int, first_monday: date) -> None:
    """Stand-in schedule, used only when no registrar export is supplied."""
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["周次", "日期", "星期", "节次", "课程", "班级", "地点"])
    for index in range(sessions):
        day = first_monday + timedelta(weeks=index)
        sheet.append([
            index + 1,
            day.isoformat(),
            "一",
            f"1-{periods_per_session}",
            "人工智能与创意设计",
            "数字艺术25级1班",
            "实训楼A301",
        ])
    workbook.save(path)


# Filename keywords, most specific first: 教案模板 must beat 教案.
CLASSIFIERS: list[tuple[str, tuple[str, ...]]] = [
    ("talent_plan", ("人才培养方案", "培养方案")),
    ("course_standard", ("课程标准",)),
    ("outline_template", ("实施大纲模板", "大纲模板", "授课计划模板", "课程实施大纲", "实施大纲")),
    ("lesson_template", ("教案模板", "教案模版")),
    ("schedule", ("课表", "课程表", "教学班课表")),
    ("sample_lesson", ("完整版教案", "教案样例")),
]


def classify(directory: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    # .docx before .doc so a converted copy wins over the original python-docx
    # cannot open; Office lock files (~$name) are not documents at all.
    def rank(path: Path) -> tuple[int, str]:
        return (0 if path.suffix.lower() in (".docx", ".xlsx") else 1, path.name)

    for path in sorted(directory.iterdir(), key=rank):
        if path.is_dir() or path.name.startswith("~$"):
            continue
        if path.suffix.lower() not in (".docx", ".doc", ".xlsx", ".xls", ".pdf"):
            continue
        for kind, keywords in CLASSIFIERS:
            if kind in found:
                continue
            if any(word in path.name for word in keywords):
                found[kind] = path
                break
    return found


REQUIRED_MATERIALS = ("talent_plan", "course_standard", "outline_template", "lesson_template")


def materials(directory: str) -> dict[str, Path]:
    """Locate the four school documents this check runs against.

    They are a school's own internal files, so the repository ships none of
    them and there is no default path to fall back on: point ``--materials`` at
    a directory of your own.
    """
    if not directory:
        raise SystemExit(
            "请用 --materials 指定材料目录，目录中需含四份学校文件，按文件名关键词识别：\n"
            "  人才培养方案 / 培养方案\n"
            "  课程标准\n"
            "  课程实施大纲模板（含「实施大纲」或「大纲模板」）\n"
            "  教案模板\n"
            "本仓库不附带任何学校真实材料。"
        )
    source = Path(directory)
    if not source.is_dir():
        raise SystemExit(f"材料目录不存在：{source}")
    found = classify(source)
    print(f"从 {source} 识别到：")
    for kind, path in found.items():
        print(f"  {kind:18s} <- {path.name}")
    missing = [kind for kind in REQUIRED_MATERIALS if kind not in found]
    if missing:
        raise SystemExit(f"缺少：{'、'.join(missing)}。请检查文件名是否含对应关键词。")
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(REPO_ROOT / "uat" / "real-model-run"))
    parser.add_argument("--sessions", type=int, default=8)
    parser.add_argument("--periods", type=int, default=4)
    # Defaults match the model configuration already proven to work on the server.
    parser.add_argument("--base-url", default="https://api.deepseek.com")
    parser.add_argument("--model", default="deepseek-v4-flash")
    parser.add_argument("--dry-run", action="store_true", help="只跑到证据组装，不调用模型")
    parser.add_argument("--materials", default="", help="学校材料目录（必填）：人才培养方案、课程标准、大纲模板、教案模板")
    parser.add_argument("--schedule", default="", help="教务导出的课表 xlsx；留空则按 --first-monday 生成替代课表")
    parser.add_argument("--first-monday", default="2026-03-02", help="第 1 周周一，替代课表按此推算")
    parser.add_argument("--teaching-class", default="", help="教务课表含多个教学班时选择其一")
    parser.add_argument("--course", default="", help="课程名称；留空时从教学班名推导")
    parser.add_argument(
        "--outline-template",
        default="",
        help="课程实施大纲模板；留空则用 templates/ 下的学校标准空白模板（正文由 AI 生成的那份）",
    )
    parser.add_argument("--class-name", default="数字艺术2431", help="授课班级")
    args = parser.parse_args()

    # The run seeds its own throwaway database under --out, so it decides the
    # admin password instead of relying on one baked into the source.
    admin_password = os.environ.setdefault("INITIAL_ADMIN_PASSWORD", "LocalCheck@2026!")

    api_key = read_api_key()
    if not api_key and not args.dry_run:
        print("未找到 API key。请设置 DEEPSEEK_API_KEY 环境变量，或写入 apps/api/.env（已被 gitignore）。")
        return 2

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    from cryptography.fernet import Fernet

    os.environ["MODEL_CONFIG_ENCRYPTION_KEY"] = Fernet.generate_key().decode("ascii")
    os.environ["DATABASE_URL"] = f"sqlite:///{(out / 'run.db').as_posix()}"

    from fastapi.testclient import TestClient
    from sqlmodel import Session, select

    from app.db import engine
    from app.main import app
    from app.models import AiModelConfig, LessonPlan, OutlineRow
    from app.routes import tasks as task_routes
    from app.services.secret_store import encrypt_secret

    task_routes.TASK_FILE_DIR = out / "task-files"

    source = materials(args.materials)
    # A finished outline sitting in the materials folder is somebody's document,
    # not a template: the school's blank one is what asks for a generated body.
    outline_template = (
        Path(args.outline_template)
        if args.outline_template
        else REPO_ROOT / "templates" / "课程实施大纲模板.docx"
    )
    if outline_template.exists():
        source["outline_template"] = outline_template
        print(f"大纲模板：{outline_template.name}")
    supplied_schedule = Path(args.schedule) if args.schedule else source.get("schedule")
    if supplied_schedule and supplied_schedule.suffix.lower() in (".xlsx", ".xls"):
        schedule_path = supplied_schedule
        print(f"使用真实课表：{schedule_path.name}")
    else:
        if supplied_schedule:
            print(f"课表 {supplied_schedule.name} 不是 xlsx，暂不支持，改用推算课表。")
        schedule_path = out / "schedule.xlsx"
        first_monday = date.fromisoformat(args.first_monday)
        build_schedule(schedule_path, args.sessions, args.periods, first_monday)
        print(f"使用推算课表：第 1 周周一 {first_monday}，共 {args.sessions} 次课")

    started = time.monotonic()
    with TestClient(app) as client:
        # The seeded admin password is random unless configured, so this run
        # sets one rather than assuming a default that no longer exists.
        login = client.post("/auth/login", json={
            "employee_no": os.getenv("INITIAL_ADMIN_EMPLOYEE_NO", "admin"),
            "password": admin_password,
        })
        login.raise_for_status()
        client.headers.update({"Authorization": f"Bearer {login.json()['access_token']}"})

        if not args.dry_run:
            with Session(engine) as db:
                db.add(AiModelConfig(
                    base_url=args.base_url,
                    model_name=args.model,
                    encrypted_api_key=encrypt_secret(api_key),
                    enabled=True,
                    # Generation requires a config that has passed a connection
                    # test; the generation calls below are that test.
                    connection_status="connected",
                ))
                db.commit()

        course_name = args.course or (
            args.teaching_class.rsplit("-", 1)[0] if args.teaching_class else "人工智能与创意设计"
        )
        from app.services.course_standard_parser import parse_course_standard

        standard = parse_course_standard(source["course_standard"])
        total_hours = sum(project.reference_hours for project in standard.projects) or (
            args.sessions * args.periods
        )
        print(f"课程「{course_name}」，课程标准项目合计 {total_hours} 学时")
        task_id = client.post("/tasks", json={
            "term": "2025-2026 第二学期",
            "major": "数字媒体艺术设计",
            "class_name": args.class_name,
            "course_name": course_name,
            "teacher_name": "张明",
            "location": "示例校区 教学楼101",
            "total_hours": total_hours,
            "hours_per_session": args.periods,
        }).json()["id"]
        print(f"课程 id={task_id}")

        for endpoint, key in (("talent-plan", "talent_plan"), ("course-standard", "course_standard")):
            with source[key].open("rb") as handle:
                response = client.post(f"/tasks/{task_id}/{endpoint}", files={"file": (source[key].name, handle)})
            print(f"  上传 {key}: {response.status_code} {response.json() if response.status_code == 200 else response.text[:200]}")
            response.raise_for_status()

        with schedule_path.open("rb") as handle:
            data = {"teaching_class": args.teaching_class} if args.teaching_class else None
            uploaded = client.post(
                f"/tasks/{task_id}/schedule",
                files={"file": (schedule_path.name, handle)},
                data=data,
            )
            print(f"  上传课表: {uploaded.status_code} {uploaded.json() if uploaded.status_code == 200 else uploaded.text[:300]}")
            uploaded.raise_for_status()
        for kind, key in (("outline", "outline_template"), ("lesson", "lesson_template")):
            with source[key].open("rb") as handle:
                client.post(f"/tasks/{task_id}/templates/{kind}", files={"file": (source[key].name, handle)}).raise_for_status()

        review = client.get(f"/tasks/{task_id}/sources/review").json()
        print(f"  依据校验: {len(review['goals'])} 个课程目标, {review['indicators_count']} 个能力指标, "
              f"未知代码 {review['unknown_codes']}, 可确认={review['can_confirm']}")
        (out / "source-review.json").write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
        if not review["can_confirm"]:
            print("  依据无法确认，终止。")
            return 1
        client.post(f"/tasks/{task_id}/sources/confirm").raise_for_status()

        if args.dry_run:
            print("\n--dry-run：材料解析与依据校验通过，未调用模型。")
            return 0

        print("\n生成课程实施大纲（真实模型）...")
        outline_started = time.monotonic()
        outline = client.post(f"/tasks/{task_id}/outline/generate")
        if outline.status_code != 200:
            print(f"  失败 {outline.status_code}: {outline.text[:500]}")
            return 1
        print(f"  完成 {len(outline.json())} 行，用时 {time.monotonic() - outline_started:.1f}s")

        print("\n生成整门课教案（真实模型）...")
        lesson_started = time.monotonic()
        run = client.post(f"/tasks/{task_id}/lesson-generation-runs", json={}).json()
        while run["status"] in ("pending", "running"):
            time.sleep(2)
            run = client.get(f"/tasks/{task_id}/lesson-generation-runs/{run['id']}").json()
        print(f"  状态={run['status']} 成功={run['succeeded_items']} 失败={run['failed_items']} "
              f"用时 {time.monotonic() - lesson_started:.1f}s")
        for item in run.get("items", []):
            if item.get("status") == "failed":
                print(f"    课次 {item.get('outline_row_id')} 失败：{item.get('error_code')}")

        dump_readable(out, task_id, engine, Session, select, OutlineRow, LessonPlan)

        for name, endpoint in (("课程实施大纲", "outline/export"), ("整门课教案", "lessons/export")):
            response = client.post(f"/tasks/{task_id}/{endpoint}")
            if response.status_code == 200:
                target = out / f"真实模型_{name}.docx"
                target.write_bytes(response.content)
                print(f"  导出 {name}: {len(response.content)} 字节 -> {target.name}")
            else:
                print(f"  导出 {name} 失败 {response.status_code}: {response.text[:300]}")

    print(f"\n总用时 {time.monotonic() - started:.1f}s，结果在 {out}")
    print("请直接阅读 生成内容.md 判断教案是否可用。")
    return 0


def dump_readable(out: Path, task_id: int, engine, Session, select, OutlineRow, LessonPlan) -> None:
    lines: list[str] = ["# 真实模型生成结果\n"]
    with Session(engine) as db:
        rows = db.exec(select(OutlineRow).where(OutlineRow.task_id == task_id).order_by(OutlineRow.session_no)).all()
        lessons = db.exec(select(LessonPlan).where(LessonPlan.task_id == task_id).order_by(LessonPlan.session_no)).all()

        lines.append("## 课程实施大纲\n")
        for row in rows:
            lines.append(f"### 第 {row.session_no} 次课 {row.date_text} {row.periods}节")
            for label, value in (
                ("主题", row.topic), ("教学内容", row.teaching_content), ("思政切入", row.ideological_point),
                ("教学方法", row.teaching_methods), ("课前", row.pre_task), ("课中", row.in_class_task),
                ("课后", row.post_task), ("目标代码", row.course_goal_codes), ("能力代码", row.ability_codes),
            ):
                lines.append(f"- **{label}**：{value}")
            lines.append("")

        lines.append("\n## 整门课教案\n")
        for lesson in lessons:
            lines.append(f"### 第 {lesson.session_no} 次课：{lesson.title}（{lesson.duration_minutes} 分钟）")
            for label, value in (
                ("教学目标", lesson.teaching_goals), ("重点", lesson.key_points), ("难点", lesson.difficult_points),
                ("教学准备", lesson.teaching_preparation), ("小结", lesson.summary), ("作业", lesson.homework),
                ("目标代码", lesson.course_goal_codes), ("能力代码", lesson.ability_codes),
            ):
                lines.append(f"- **{label}**：{value}")
            lines.append("\n**教学过程**\n")
            lines.append("```")
            lines.append(lesson.teaching_process)
            lines.append("```\n")

    (out / "生成内容.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\n  已写出 生成内容.md：大纲 {len(rows)} 行，教案 {len(lessons)} 份")


if __name__ == "__main__":
    raise SystemExit(main())
