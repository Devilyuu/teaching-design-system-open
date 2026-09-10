from dataclasses import dataclass
from pathlib import Path
import re

from docx import Document


INDICATOR_CODE_RE = re.compile(r"(?<![\d-])(\d+-\d+-\d+)(?![\d-])")
# The 2024/2025 plans write the group cell as a bare "1-1"; the 2026 plans
# append the group's name ("1-1 艺术设计基础知识"). Anchor on the leading code
# and refuse a third segment so an indicator code ("1-1-10") is never taken
# for a group.
GROUP_CODE_RE = re.compile(r"^(\d+-\d+)(?![\d-])")


@dataclass(frozen=True)
class ParsedAbilityIndicator:
    code: str
    category: str
    group_code: str
    description: str


@dataclass(frozen=True)
class ParsedTalentPlan:
    indicators: list[ParsedAbilityIndicator]


def _cell_text(cell) -> str:
    return " ".join(cell.text.split())


def parse_talent_plan(path: Path | str) -> ParsedTalentPlan:
    doc = Document(str(path))
    indicators: list[ParsedAbilityIndicator] = []
    seen_codes: set[str] = set()

    for table in doc.tables:
        rows = [[_cell_text(cell) for cell in row.cells] for row in table.rows]
        for header_index, header in enumerate(rows):
            header_text = " ".join(header)
            if not all(
                marker in header_text for marker in ("培养规格代码", "TOP10", "其他")
            ):
                continue

            current_category = ""
            current_group_code = ""
            for row in rows[header_index + 1 :]:
                if len(row) < 2:
                    continue

                category, group_cell = row[0], row[1]
                group_match = GROUP_CODE_RE.match(group_cell)
                if group_match is not None:
                    current_group_code = group_match.group(1)
                elif group_cell:
                    current_category = ""
                    current_group_code = ""
                    continue
                elif not current_group_code:
                    continue

                if category:
                    current_category = category
                if not current_category:
                    continue

                indicator_text = " ".join(row[2:])
                matches = [
                    match
                    for match in INDICATOR_CODE_RE.finditer(indicator_text)
                    if match.group(1).rsplit("-", 1)[0] == current_group_code
                ]
                for index, match in enumerate(matches):
                    code = match.group(1)
                    if code in seen_codes:
                        continue

                    next_start = (
                        matches[index + 1].start()
                        if index + 1 < len(matches)
                        else len(indicator_text)
                    )
                    indicators.append(
                        ParsedAbilityIndicator(
                            code=code,
                            category=current_category,
                            group_code=current_group_code,
                            description=indicator_text[match.end() : next_start].strip(),
                        )
                    )
                    seen_codes.add(code)

    return ParsedTalentPlan(indicators=indicators)
