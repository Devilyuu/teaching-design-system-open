from types import SimpleNamespace

from app.services.course_readiness import build_course_readiness


def item(**values):
    return SimpleNamespace(**values)


def ready_inputs(**overrides):
    values = {
        "task": item(id=1, total_hours=8),
        "materials": [
            item(kind="talent_plan", original_filename="talent.docx", status="ready", summary_json="{}", updated_at=None, uploaded_by_id=1),
            item(kind="course_standard", original_filename="standard.docx", status="ready", summary_json="{}", updated_at=None, uploaded_by_id=1),
            item(kind="schedule", original_filename="schedule.xlsx", status="ready", summary_json="{}", updated_at=None, uploaded_by_id=1),
            item(kind="outline_template", original_filename="outline.docx", status="ready", summary_json="{}", updated_at=None, uploaded_by_id=1),
            item(kind="lesson_template", original_filename="lesson.docx", status="ready", summary_json="{}", updated_at=None, uploaded_by_id=1),
        ],
        "goals": [item(code="M1", description="目标", ability_codes="1-3-4")],
        "projects": [item(name="项目一", reference_hours=8)],
        "indicators": [item(code="1-3-4", description="指标")],
        "confirmation": item(task_id=1),
        "schedule": [item(hours=4), item(hours=4)],
        "outline_rows": [],
        "ai_config": item(enabled=True, connection_status="connected"),
        "notices": [],
        "legacy_templates": set(),
        "uploader_names": {1: "系统管理员"},
    }
    values.update(overrides)
    return values


def test_readiness_lists_each_missing_requirement():
    result = build_course_readiness(
        task=item(id=1, total_hours=32),
        materials=[],
        goals=[],
        projects=[],
        indicators=[],
        confirmation=None,
        schedule=[],
        outline_rows=[],
        ai_config=None,
        notices=[],
        legacy_templates=set(),
    )

    assert result.can_generate_outline is False
    assert [entry.code for entry in result.blocking_reasons] == [
        "talent_plan_missing",
        "course_standard_missing",
        "schedule_missing",
        "outline_template_missing",
        "sources_unconfirmed",
        "ai_model_unavailable",
    ]
    assert result.next_action == "complete_materials"


def test_an_uploaded_timetable_awaiting_confirmation_does_not_read_as_missing():
    """The first teacher to upload one concluded it had failed.

    A timetable becomes a material only once confirmed, so the row said 尚未上传
    while the file sat right there in the panel below, waiting to be checked.
    """
    result = build_course_readiness(
        task=item(id=1, total_hours=80),
        materials=[],
        goals=[],
        projects=[],
        indicators=[],
        confirmation=None,
        schedule=[],
        outline_rows=[],
        ai_config=None,
        notices=[],
        legacy_templates=set(),
        pending_schedule={"status": "pending", "session_count": 40, "filename": "1001张明课表.xls"},
    )

    schedule = result.materials["schedule"]
    assert schedule.status == "awaiting_confirmation"
    assert schedule.filename == "1001张明课表.xls"
    assert "40 次课" in schedule.message

    blocker = next(entry for entry in result.blocking_reasons if entry.material_kind == "schedule")
    assert blocker.code == "schedule_awaiting_confirmation"
    assert "已上传" in blocker.message and "确认" in blocker.message


def test_a_discarded_candidate_leaves_the_timetable_reading_as_missing():
    result = build_course_readiness(
        task=item(id=1, total_hours=80),
        materials=[],
        goals=[],
        projects=[],
        indicators=[],
        confirmation=None,
        schedule=[],
        outline_rows=[],
        ai_config=None,
        notices=[],
        legacy_templates=set(),
        pending_schedule={"status": "discarded", "session_count": 40, "filename": "旧课表.xls"},
    )

    assert result.materials["schedule"].status == "missing"
    assert [entry.code for entry in result.blocking_reasons if entry.material_kind == "schedule"] == ["schedule_missing"]


def test_readiness_allows_first_generation_only_when_every_condition_is_ready():
    result = build_course_readiness(**ready_inputs())

    assert result.can_generate_outline is True
    assert result.blocking_reasons == []
    assert result.next_action == "generate_outline"
    assert result.schedule_hours == 8


def test_readiness_routes_existing_outline_to_editor_instead_of_generation():
    result = build_course_readiness(**ready_inputs(outline_rows=[item(id=1, session_no=1)]))

    assert result.can_generate_outline is False
    assert result.next_action == "open_outline"
    assert result.blocking_reasons == []


def test_readiness_recognizes_legacy_parsed_sources_and_templates():
    inputs = ready_inputs(materials=[], legacy_templates={"outline", "lesson"})
    result = build_course_readiness(**inputs)

    assert result.materials["course_standard"].status == "ready"
    assert "原文件名未记录" in result.materials["course_standard"].message
    assert result.materials["talent_plan"].status == "ready"
    assert result.materials["outline_template"].status == "ready"


def test_readiness_reports_unknown_ability_codes_and_hour_mismatch():
    result = build_course_readiness(
        **ready_inputs(
            goals=[item(code="M1", description="目标", ability_codes="9-9-9")],
            confirmation=None,
            schedule=[item(hours=4)],
        )
    )

    assert [entry.code for entry in result.blocking_reasons] == [
        "ability_codes_unknown",
        "schedule_hours_mismatch",
        "sources_unconfirmed",
    ]
    assert result.next_action == "confirm_sources"
