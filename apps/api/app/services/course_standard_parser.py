from dataclasses import dataclass, replace
from pathlib import Path
import re

from docx import Document

ABILITY_CODE_RE = re.compile(r"\d+-\d+-\d+")
GOAL_CODE_RE = re.compile(r"M\d+")
# Schools write the hours column either as "理论/实践" (8/4) or as a bare total
# (12). Only the total is load-bearing downstream (it must sum to the course
# hours), so a bare number is accepted and the practice split recorded as unknown.
REFERENCE_HOURS_RE = re.compile(r"^(\d+)(?:\s*/\s*(\d+))?\s*(?:学时|课时)?$")


@dataclass(frozen=True)
class ParsedCourseGoal:
    code: str
    description: str
    ability_codes: list[str]


@dataclass(frozen=True)
class ParsedCourseProject:
    name: str
    description: str
    teaching_content: str
    suggested_methods: str
    course_goal_codes: list[str]
    ability_codes: list[str]
    reference_hours: int
    practice_hours: int


@dataclass(frozen=True)
class ParsedCourseStandard:
    goals: list[ParsedCourseGoal]
    projects: list[ParsedCourseProject]


def _cell_text(cell) -> str:
    return " ".join(cell.text.split())


def parse_course_standard(path: Path | str) -> ParsedCourseStandard:
    doc = Document(str(path))
    goals: list[ParsedCourseGoal] = []
    projects: list[ParsedCourseProject] = []

    for table in doc.tables:
        rows = [[_cell_text(cell) for cell in row.cells] for row in table.rows]
        if not rows:
            continue
        header = rows[0]
        has_goal_header = any("课程教学目标" in item or "课程目标" in item for item in header)
        if "编号" in header and has_goal_header:
            for row in rows[1:]:
                if len(row) < 3:
                    continue
                code = row[0].strip()
                if not re.fullmatch(r"M\d+", code):
                    continue
                goals.append(
                    ParsedCourseGoal(
                        code=code,
                        description=row[1].strip(),
                        ability_codes=ABILITY_CODE_RE.findall(row[2]),
                    )
                )

        if not {"项目名称", "教学内容", "参考课时"}.issubset(set(header)):
            continue
        name_index = header.index("项目名称")
        content_index = header.index("教学内容")
        method_index = next((index for index, value in enumerate(header) if "教学方法" in value), content_index)
        hours_index = header.index("参考课时")
        for row in rows[1:]:
            if len(row) <= hours_index:
                continue
            name = row[name_index].strip()
            hours_match = REFERENCE_HOURS_RE.fullmatch(row[hours_index].strip())
            if hours_match and name and name != "合计":
                code_text = " ".join(row[method_index + 1 : hours_index])
                projects.append(
                    ParsedCourseProject(
                        name=name,
                        description="",
                        teaching_content=row[content_index].strip(),
                        suggested_methods=row[method_index].strip(),
                        course_goal_codes=list(dict.fromkeys(GOAL_CODE_RE.findall(code_text))),
                        ability_codes=list(dict.fromkeys(ABILITY_CODE_RE.findall(code_text))),
                        reference_hours=int(hours_match.group(1)),
                        practice_hours=int(hours_match.group(2) or 0),
                    )
                )
                continue
            if projects and name == projects[-1].name:
                descriptions = [
                    value.split("项目描述：", 1)[1].strip()
                    for value in row
                    if "项目描述：" in value and value.split("项目描述：", 1)[1].strip()
                ]
                if descriptions:
                    projects[-1] = replace(projects[-1], description=max(descriptions, key=len))

    return ParsedCourseStandard(goals=goals, projects=projects)
