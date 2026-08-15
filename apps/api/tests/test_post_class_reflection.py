from app.services.post_class_reflection import (
    build_adjustment_block,
    generate_adjustment_suggestion,
    remove_adjustment_block,
)


def test_partial_progress_and_average_mastery_add_review_time():
    suggestion = generate_adjustment_suggestion("partial", "average", "normal", "示范环节未完成")

    assert suggestion.suggested_minutes == 20
    assert "补讲" in suggestion.text
    assert "复习" in suggestion.text
    assert "示范环节未完成" in suggestion.text


def test_all_good_requires_no_adjustment():
    suggestion = generate_adjustment_suggestion("completed", "good", "smooth", "")

    assert suggestion.requires_adjustment is False
    assert suggestion.suggested_minutes == 0


def test_remove_adjustment_block_preserves_later_teacher_changes():
    original = "导入\n讲授新知识"
    applied = build_adjustment_block(original, 7, "第 1 次课", "复习 20 分钟")
    edited = applied + "\n教师后来新增的总结"

    assert remove_adjustment_block(edited, 7) == original + "\n教师后来新增的总结"
