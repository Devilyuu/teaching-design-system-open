import pytest

from app.services.academic_term import normalize_term


@pytest.mark.parametrize(
    "written",
    [
        "2025-2026第二学期",
        "2025-2026 第二学期",
        "  2025-2026　第二学期  ",
        "2025-2026学年第二学期",
        "2025-2026 第2学期",
        "2025－2026 第二学期",
        "2025/2026 第二学期",
    ],
)
def test_the_same_semester_written_differently_lands_on_one_value(written):
    """线上真的出现过前两种写法指同一个学期，其余是同一类手滑。"""
    assert normalize_term(written) == "2025-2026 第二学期"


def test_the_first_half_keeps_its_own_value():
    assert normalize_term("2026-2027第一学期") == "2026-2027 第一学期"


def test_normalised_terms_sort_in_time_order():
    """规范形式的字典序就是时间序，下游分组排序因此不需要映射表。"""
    terms = ["2026-2027 第一学期", "2025-2026 第二学期", "2025-2026 第一学期"]
    assert sorted(terms) == [
        "2025-2026 第一学期",
        "2025-2026 第二学期",
        "2026-2027 第一学期",
    ]


@pytest.mark.parametrize(
    "written",
    [
        "2025-2027 第二学期",  # 学年不相接，是笔误不是写法
        "第二学期",
        "2025 秋",
        "",
    ],
)
def test_what_cannot_be_read_is_left_alone(written):
    """学期会印进大纲和教案的抬头，猜错比留着错的更糟。"""
    assert normalize_term(written) == written.strip()
