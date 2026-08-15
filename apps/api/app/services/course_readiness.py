from dataclasses import dataclass, field
import json

from app.services.lesson_evidence import canonical_code


MATERIAL_KINDS = (
    "talent_plan",
    "course_standard",
    "schedule",
    "outline_template",
    "lesson_template",
)


@dataclass(frozen=True)
class MaterialReadiness:
    kind: str
    status: str
    filename: str = ""
    uploaded_at: object | None = None
    uploaded_by: str = ""
    message: str = ""
    summary: dict = field(default_factory=dict)


def _pending_field(pending_schedule, name: str):
    """The candidate arrives as a dict from the route and as an object in tests."""
    if isinstance(pending_schedule, dict):
        return pending_schedule.get(name) or ""
    return getattr(pending_schedule, name, "") or ""


def _pending_session_count(pending_schedule) -> int | None:
    """How many sessions a still-unconfirmed timetable would bring, if any."""
    if pending_schedule is None:
        return None
    if _pending_field(pending_schedule, "status") != "pending":
        return None
    return int(_pending_field(pending_schedule, "session_count") or 0)


@dataclass(frozen=True)
class ReadinessBlocker:
    code: str
    message: str
    material_kind: str | None = None


@dataclass(frozen=True)
class CourseReadinessResult:
    task_id: int
    materials: dict[str, MaterialReadiness]
    schedule_hours: int
    expected_hours: int
    can_generate_outline: bool
    blocking_reasons: list[ReadinessBlocker]
    next_action: str
    unknown_codes: list[str]
    sources_confirmed: bool
    pending_schedule: object | None = None
    review_notices: list = field(default_factory=list)


def _codes(value: str | list[str]) -> list[str]:
    values = value if isinstance(value, list) else value.replace("，", " ").replace(",", " ").split()
    return list(dict.fromkeys(canonical_code(item) for item in values if canonical_code(item)))


def _asset_readiness(asset, uploader_names: dict[int, str]) -> MaterialReadiness:
    try:
        summary = json.loads(asset.summary_json or "{}")
    except (TypeError, json.JSONDecodeError):
        summary = {}
    return MaterialReadiness(
        kind=asset.kind,
        status=asset.status,
        filename=asset.original_filename,
        uploaded_at=asset.updated_at,
        uploaded_by=uploader_names.get(asset.uploaded_by_id, ""),
        message="资料已就绪" if asset.status == "ready" else (asset.error_message or "资料需要处理"),
        summary=summary,
    )


def build_course_readiness(
    *,
    task,
    materials,
    goals,
    projects,
    indicators,
    confirmation,
    schedule,
    outline_rows,
    ai_config,
    notices,
    legacy_templates,
    pending_schedule=None,
    uploader_names=None,
) -> CourseReadinessResult:
    uploader_names = uploader_names or {}
    assets = {asset.kind: asset for asset in materials}
    material_states: dict[str, MaterialReadiness] = {}

    legacy_ready = {
        "talent_plan": bool(indicators),
        "course_standard": bool(goals and projects),
        "schedule": bool(schedule),
        "outline_template": "outline" in legacy_templates,
        "lesson_template": "lesson" in legacy_templates,
    }
    for kind in MATERIAL_KINDS:
        asset = assets.get(kind)
        if asset is not None:
            material_states[kind] = _asset_readiness(asset, uploader_names)
        elif legacy_ready[kind]:
            material_states[kind] = MaterialReadiness(
                kind=kind,
                status="ready",
                message="历史资料已就绪，原文件名未记录",
            )
        else:
            material_states[kind] = MaterialReadiness(kind=kind, status="missing", message="尚未上传")

    # An uploaded timetable is not a material until it is confirmed, so the row
    # read "尚未上传" while the file was sitting right there waiting -- the first
    # teacher to hit this concluded the upload had failed.
    awaiting_schedule = _pending_session_count(pending_schedule)
    if awaiting_schedule is not None and material_states["schedule"].status != "ready":
        material_states["schedule"] = MaterialReadiness(
            kind="schedule",
            status="awaiting_confirmation",
            filename=_pending_field(pending_schedule, "filename"),
            message=f"已解析 {awaiting_schedule} 次课，待你确认后生效",
        )

    blockers: list[ReadinessBlocker] = []
    if material_states["talent_plan"].status != "ready":
        blockers.append(ReadinessBlocker("talent_plan_missing", "尚未上传人才培养方案", "talent_plan"))
    if material_states["course_standard"].status != "ready":
        blockers.append(ReadinessBlocker("course_standard_missing", "尚未上传课程标准", "course_standard"))
    if material_states["schedule"].status == "awaiting_confirmation":
        blockers.append(
            ReadinessBlocker(
                "schedule_awaiting_confirmation",
                f"教务课表已上传（{awaiting_schedule} 次课），请在下方「新课表待确认」里核对并确认",
                "schedule",
            )
        )
    elif material_states["schedule"].status != "ready":
        blockers.append(ReadinessBlocker("schedule_missing", "尚未上传并确认教务课表", "schedule"))
    if material_states["outline_template"].status != "ready":
        blockers.append(ReadinessBlocker("outline_template_missing", "尚未上传课程实施大纲模板", "outline_template"))

    indicator_codes = {canonical_code(item.code) for item in indicators}
    referenced_codes = {code for goal in goals for code in _codes(goal.ability_codes)}
    unknown_codes = sorted(referenced_codes - indicator_codes)
    if unknown_codes:
        blockers.append(
            ReadinessBlocker(
                "ability_codes_unknown",
                f"课程标准包含人才培养方案中不存在的能力代码：{', '.join(unknown_codes)}",
                "course_standard",
            )
        )

    project_hours = sum(item.reference_hours for item in projects)
    if projects and project_hours != task.total_hours:
        blockers.append(
            ReadinessBlocker(
                "project_hours_mismatch",
                f"课程项目参考学时为 {project_hours}，课程总学时为 {task.total_hours}",
                "course_standard",
            )
        )
    schedule_hours = sum(item.hours for item in schedule)
    if schedule and schedule_hours != task.total_hours:
        blockers.append(
            ReadinessBlocker(
                "schedule_hours_mismatch",
                f"课表总学时为 {schedule_hours}，课程总学时为 {task.total_hours}",
                "schedule",
            )
        )
    if confirmation is None:
        blockers.append(ReadinessBlocker("sources_unconfirmed", "课程依据尚未确认"))
    if ai_config is None or not ai_config.enabled or ai_config.connection_status != "connected":
        blockers.append(ReadinessBlocker("ai_model_unavailable", "AI 模型尚未测试并启用"))

    if outline_rows:
        next_action = "open_outline"
    elif any(item.code.endswith("_missing") for item in blockers) or any(
        item.code == "ai_model_unavailable" for item in blockers
    ):
        next_action = "complete_materials"
    elif confirmation is None or unknown_codes:
        next_action = "confirm_sources"
    else:
        next_action = "generate_outline"

    return CourseReadinessResult(
        task_id=task.id,
        materials=material_states,
        schedule_hours=schedule_hours,
        expected_hours=task.total_hours,
        can_generate_outline=not blockers and not outline_rows,
        blocking_reasons=blockers,
        next_action=next_action,
        unknown_codes=unknown_codes,
        sources_confirmed=confirmation is not None,
        pending_schedule=pending_schedule,
        review_notices=list(notices),
    )
