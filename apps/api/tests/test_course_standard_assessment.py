from pathlib import Path

import pytest
from docx import Document

from app.services.course_standard_assessment import (
    assessment_rows,
    extract_course_assessments,
    read_course_assessments,
)
from app.services.course_standard_resources import MISSING


# 只剩一份真实课程标准了：《人工智能与创意设计》那份 2026-08-11 随其整套材料一起
# 删掉（课程标准与大纲的主线互相打架，见 git 历史；用户确认那门课作废）。
# 这些文件都在 gitignore 的 cankao/ 下，干净检出时本来就不存在，所以下面按惯例 skip。
REAL_STANDARDS = (
    Path(__file__).resolve().parents[3]
    / "cankao"
    / "2026春季学期真实材料"
    / "24级《移动终端APP设计》课程标准.docx",
)


def _standard_with_assessment(path: Path) -> Path:
    document = Document()
    document.add_paragraph("四、课程评价")
    table = document.add_table(rows=4, cols=4)
    table.cell(0, 0).merge(table.cell(0, 1)).text = "考核项目"
    table.cell(0, 2).text = "考核方式"
    table.cell(0, 3).text = "比例"
    values = [
        ("过程考核（平时成绩）", "出勤", "按迟到早退请假综合评定。", "40%"),
        ("", "平时表现", "按作业与课堂表现评定。", "10%"),
        ("结果考核(期末成绩)", "期末项目", "由考核小组评定作品汇报。", "50%"),
    ]
    for row_index, row in enumerate(values, start=1):
        for column, value in enumerate(row):
            if value:
                table.cell(row_index, column).text = value
    # 过程考核 runs down the first two data rows, as both real standards write it.
    table.cell(1, 0).merge(table.cell(2, 0))
    total = table.add_row()
    total.cells[0].merge(total.cells[2]).text = "合计"
    total.cells[3].text = "100%"
    document.save(path)
    return path


def test_the_table_is_copied_cell_for_cell_including_how_it_merges(tmp_path):
    """六、考核方式 ships the standard's own table; a copy that loses the merges reads as another one."""
    assessments = extract_course_assessments(_standard_with_assessment(tmp_path / "standard.docx"))

    assert [row.cells[1] for row in assessments.rows] == ["出勤", "平时表现", "期末项目", "合计"]
    assert [row.cells[3] for row in assessments.rows] == ["40%", "10%", "50%", "100%"]
    # The second row carries on the first row's 过程考核 cell rather than repeating it.
    assert assessments.rows[0].continues_above == ()
    assert assessments.rows[1].continues_above == (0,)
    assert assessments.rows[1].cells[0] == "过程考核（平时成绩）"
    assert assessments.rows[2].continues_above == ()
    # 合计 runs across everything but the percentage.
    assert assessments.rows[3].spans == ((0, 1, 2), (3,))


def test_a_standard_without_a_course_evaluation_table_yields_nothing(tmp_path):
    document = Document()
    document.add_paragraph("四、课程评价")
    document.add_paragraph("按学校规定执行。")
    path = tmp_path / "bare.docx"
    document.save(path)

    assert extract_course_assessments(path).found_anything is False


def test_a_silent_standard_asks_the_teacher_instead_of_inventing_a_split(tmp_path):
    """These percentages decide grades; a plausible invented split is worse than a gap."""
    rows = assessment_rows(read_course_assessments(Document()), columns=4)

    assert len(rows) == 1
    assert rows[0].cells == (MISSING,) * 4
    assert rows[0].spans == ((0, 1, 2, 3),)


@pytest.mark.parametrize("path", REAL_STANDARDS, ids=lambda path: path.stem[:12])
def test_both_real_course_standards_read_the_same_way(path):
    """Two courses, one 四、课程评价 shape -- the school's own template."""
    if not path.exists():
        # Course standards are internal school material and stay out of Git, so
        # a fresh checkout has nothing to read here.
        pytest.skip(f"{path.name} 未入库（学校内部材料），仅在有真实材料的机器上运行")

    assessments = extract_course_assessments(path)

    assert [row.cells[1] for row in assessments.rows] == ["出勤", "平时表现", "单元项目", "期末项目", "合计"]
    assert [row.cells[3] for row in assessments.rows] == ["10%", "10%", "30%", "50%", "100%"]
    assert [row.continues_above for row in assessments.rows] == [(), (0,), (0,), (), ()]
    assert assessments.rows[-1].spans == ((0, 1, 2), (3,))
