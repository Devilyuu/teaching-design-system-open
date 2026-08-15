"""Lift 四、课程评价 out of the course standard, cell for cell.

The same bargain as `course_standard_resources`: the school has already decided
how this course is assessed and in what proportions, those proportions are the
ones the 教务 record checks against, and the document goes into 诊改 material.
So the outline copies the table across rather than asking a model to restate it
-- and copies how it is laid out too, because the standard merges 过程考核 down
its first column and closes with a 合计 row, and a copy that loses those reads
as a different table.

Both real course standards and the finished outline they produced use the same
shape: 考核项目 spanning two grid columns in the header, then 大类 / 项目 /
说明 / 比例 below it.
"""

from dataclasses import dataclass
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

from app.services.course_standard_resources import MISSING


HEADER_MARKERS = ("考核项目", "考核方式", "比例")


@dataclass(frozen=True)
class AssessmentRow:
    """One row of the table, described the way Word lays it out."""

    cells: tuple[str, ...]
    """Text per grid column; a merged cell repeats across the columns it covers."""

    spans: tuple[tuple[int, ...], ...]
    """Grid columns grouped by the cell covering them."""

    continues_above: tuple[int, ...]
    """Grid columns whose cell carries on from the row above."""


@dataclass(frozen=True)
class CourseAssessments:
    rows: tuple[AssessmentRow, ...] = ()

    @property
    def found_anything(self) -> bool:
        return bool(self.rows)


def extract_course_assessments(path: Path | str) -> CourseAssessments:
    return read_course_assessments(Document(str(path)))


def read_course_assessments(document) -> CourseAssessments:
    for table in document.tables:
        if not table.rows:
            continue
        header = "".join(cell.text for cell in table.rows[0].cells)
        if all(marker in header for marker in HEADER_MARKERS):
            return CourseAssessments(tuple(_read_row(row) for row in table.rows[1:]))
    return CourseAssessments()


def assessment_rows(assessments: CourseAssessments, columns: int) -> tuple[AssessmentRow, ...]:
    """What to write, with one honest row when the standard states nothing.

    Inventing a plausible split of the marks would be the same defect as
    inventing a textbook, and this one decides grades.
    """
    if assessments.found_anything:
        return assessments.rows
    width = max(columns, 1)
    return (
        AssessmentRow(
            cells=(MISSING,) * width,
            spans=(tuple(range(width)),),
            continues_above=(),
        ),
    )


def _read_row(row) -> AssessmentRow:
    spans: list[tuple[int, ...]] = []
    continues: list[int] = []
    for start, span, merge in _grid_cells(row):
        columns = tuple(range(start, start + span))
        spans.append(columns)
        if merge == "continue":
            continues.extend(columns)
    return AssessmentRow(
        # A continued cell reads as the text of the cell it continues, which is
        # exactly what belongs in the merged cell being written.
        cells=tuple(cell.text.strip() for cell in row.cells),
        spans=tuple(spans),
        continues_above=tuple(continues),
    )


def _grid_cells(row):
    position = 0
    for cell in row._tr.findall(qn("w:tc")):
        properties = cell.find(qn("w:tcPr"))
        span = None if properties is None else properties.find(qn("w:gridSpan"))
        merge = None if properties is None else properties.find(qn("w:vMerge"))
        width = 1 if span is None else int(span.get(qn("w:val")) or 1)
        # w:vMerge with no w:val means "continue"; "restart" opens a new group.
        yield position, width, None if merge is None else (merge.get(qn("w:val")) or "continue")
        position += width
