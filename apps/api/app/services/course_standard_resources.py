"""Lift the teaching resources out of the course standard, word for word.

The outline template marks 五、学习资源 for generation, but its content is fact:
book titles, authors, publishers, years, platform addresses. A model writes
those fluently and wrongly -- a plausible citation that no library holds -- and
these documents go into 诊改 material. So nothing here is generated. What the
standard states is copied across; what it does not state is left for the teacher
to fill, and says so.
"""

from dataclasses import dataclass, field
from pathlib import Path
import re

from docx import Document


RESOURCE_SECTION = re.compile(r"^\s*五[、.．]\s*课程教学资源")
NEXT_SECTION = re.compile(r"^\s*六[、.．]")
TEXTBOOK_LABEL = re.compile(r"^\s*（\s*1\s*）\s*教材")
REFERENCE_LABEL = re.compile(r"^\s*（\s*2\s*）\s*参考书")
# The other way a standard writes these: label and first entry on one line,
# 「教材：xxx」 / 「参考书：xxx」, straight under 「3．参考教材及教学参考书建议」.
TEXTBOOK_INLINE = re.compile(r"^\s*教材\s*[：:]\s*(.*)$")
REFERENCE_INLINE = re.compile(r"^\s*(?:参考书目?|参考教材|教辅)\s*[：:]\s*(.*)$")
ONLINE_LABEL = re.compile(r"^\s*4\s*[、.．]\s*学习资源选用")
OTHER_NUMBERED = re.compile(r"^\s*\d\s*[、.．]")
# 「（按要求选用国家规划教材）」这类是填写说明，不是资源本身
INSTRUCTION_ONLY = re.compile(r"^\s*（[^）]*）\s*$")

MISSING = "课程标准中未提供，请教师补充"


@dataclass(frozen=True)
class CourseResources:
    textbooks: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    online: list[str] = field(default_factory=list)

    @property
    def found_anything(self) -> bool:
        return bool(self.textbooks or self.references or self.online)


def _lines(document) -> list[str]:
    return [paragraph.text.strip() for paragraph in document.paragraphs]


def extract_course_resources(path: Path | str) -> CourseResources:
    return read_course_resources(Document(str(path)))


def read_course_resources(document) -> CourseResources:
    lines = _lines(document)
    start = next((index for index, line in enumerate(lines) if RESOURCE_SECTION.match(line)), None)
    if start is None:
        return CourseResources()

    textbooks: list[str] = []
    references: list[str] = []
    online: list[str] = []
    bucket: list[str] | None = None

    for line in lines[start + 1 :]:
        if NEXT_SECTION.match(line):
            break
        if not line:
            continue
        if TEXTBOOK_LABEL.match(line):
            bucket = textbooks
            continue
        if REFERENCE_LABEL.match(line):
            bucket = references
            continue
        inline = TEXTBOOK_INLINE.match(line) or REFERENCE_INLINE.match(line)
        if inline:
            bucket = textbooks if TEXTBOOK_INLINE.match(line) else references
            if inline.group(1).strip():
                bucket.append(inline.group(1).strip())
            continue
        if ONLINE_LABEL.match(line):
            bucket = online
            continue
        # 实践条件、师资条件这些编号小节不是资源，遇到就停止收集
        if OTHER_NUMBERED.match(line):
            bucket = None
            continue
        if bucket is None or INSTRUCTION_ONLY.match(line):
            continue
        bucket.append(line)

    return CourseResources(textbooks=textbooks, references=references, online=online)


def resource_lines(resources: CourseResources) -> dict[str, list[str]]:
    """Shaped for the template's 五、学习资源 subsections.

    A subsection the standard says nothing about gets one honest line rather
    than a borrowed entry from a neighbour -- padding it out is the same defect
    as inventing it.
    """
    return {
        "教材": resources.textbooks or [MISSING],
        "教辅": resources.references or [MISSING],
        "在线学习资源": resources.online or [MISSING],
        "高质量作业范例": [MISSING],
        "参考书目": resources.references or [MISSING],
    }
