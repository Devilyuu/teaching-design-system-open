"""Render the numbers Word paints in front of auto-numbered paragraphs.

python-docx's ``paragraph.text`` carries only the typed characters. A plan whose
indicator codes come from a multilevel list ("%1-%2-%3" → 1-1-1, 1-1-2 …) looks
perfectly numbered on screen and on paper, but reads as plain sentences here,
and the parser concluded the group had no codes at all. The 2026 艺术设计 plan
mixes both: some groups typed the codes, others let Word number them.

The rendering follows Word's rules as far as the school's documents exercise
them: counters live per ``w:num``, an item at one level resets every deeper
level, a level that has not appeared yet shows its start value, and
``w:startOverride`` on the num wins over the abstract level's ``w:start``.
"""

from __future__ import annotations

import re

from docx.oxml.ns import qn

_PLACEHOLDER_RE = re.compile(r"%(\d)")


def _int_attr(element, default: int) -> int:
    if element is None:
        return default
    try:
        return int(element.get(qn("w:val")))
    except (TypeError, ValueError):
        return default


class _Numbering:
    def __init__(self, document) -> None:
        self._levels: dict[str, dict[int, tuple[int, str, str]]] = {}
        self._style_numpr: dict[str, tuple[str, int] | None] = {}
        self._styles = document.styles.element
        try:
            root = document.part.numbering_part.element
        except (NotImplementedError, AttributeError, KeyError):
            root = None
        if root is None:
            return
        abstract = {
            item.get(qn("w:abstractNumId")): item
            for item in root.findall(qn("w:abstractNum"))
        }
        for num in root.findall(qn("w:num")):
            num_id = num.get(qn("w:numId"))
            abstract_id = num.find(qn("w:abstractNumId"))
            base = abstract.get(abstract_id.get(qn("w:val"))) if abstract_id is not None else None
            levels: dict[int, tuple[int, str, str]] = {}
            if base is not None:
                for lvl in base.findall(qn("w:lvl")):
                    levels[int(lvl.get(qn("w:ilvl")))] = self._level_spec(lvl)
            for override in num.findall(qn("w:lvlOverride")):
                ilvl = int(override.get(qn("w:ilvl")))
                lvl = override.find(qn("w:lvl"))
                if lvl is not None:
                    levels[ilvl] = self._level_spec(lvl)
                start = override.find(qn("w:startOverride"))
                if start is not None and ilvl in levels:
                    _, fmt, text = levels[ilvl]
                    levels[ilvl] = (_int_attr(start, 1), fmt, text)
            self._levels[num_id] = levels

    @staticmethod
    def _level_spec(lvl) -> tuple[int, str, str]:
        fmt = lvl.find(qn("w:numFmt"))
        text = lvl.find(qn("w:lvlText"))
        return (
            _int_attr(lvl.find(qn("w:start")), 0),
            fmt.get(qn("w:val")) if fmt is not None else "decimal",
            text.get(qn("w:val")) if text is not None else "",
        )

    def paragraph_numpr(self, paragraph) -> tuple[str, int] | None:
        ppr = paragraph.find(qn("w:pPr"))
        if ppr is not None:
            numpr = ppr.find(qn("w:numPr"))
            if numpr is not None:
                num_id = numpr.find(qn("w:numId"))
                ilvl = numpr.find(qn("w:ilvl"))
                if num_id is None:
                    return None
                return num_id.get(qn("w:val")), _int_attr(ilvl, 0)
            style = ppr.find(qn("w:pStyle"))
            if style is not None:
                return self._style_numpr_for(style.get(qn("w:val")))
        return None

    def _style_numpr_for(self, style_id: str) -> tuple[str, int] | None:
        if style_id in self._style_numpr:
            return self._style_numpr[style_id]
        self._style_numpr[style_id] = None
        style = self._styles.find(f'{qn("w:style")}[@{qn("w:styleId")}="{style_id}"]')
        if style is None:
            return None
        ppr = style.find(qn("w:pPr"))
        numpr = ppr.find(qn("w:numPr")) if ppr is not None else None
        found = None
        if numpr is not None and numpr.find(qn("w:numId")) is not None:
            found = (numpr.find(qn("w:numId")).get(qn("w:val")), _int_attr(numpr.find(qn("w:ilvl")), 0))
        else:
            based_on = style.find(qn("w:basedOn"))
            if based_on is not None:
                found = self._style_numpr_for(based_on.get(qn("w:val")))
        self._style_numpr[style_id] = found
        return found

    def levels(self, num_id: str) -> dict[int, tuple[int, str, str]]:
        return self._levels.get(num_id, {})


def paragraph_numbers(document) -> dict:
    """Map each paragraph element (``CT_P``) to the label Word shows before it.

    Keys are the lxml elements themselves, not ``id()`` values: lxml only hands
    back the same proxy object for an element while something still references
    it, and holding the keys here is what keeps them alive.

    Paragraphs without a list, in a bullet list, or in a list with no
    definition are absent from the result.
    """
    numbering = _Numbering(document)
    counters: dict[str, dict[int, int]] = {}
    labels: dict = {}
    for paragraph in document.element.body.iter(qn("w:p")):
        numpr = numbering.paragraph_numpr(paragraph)
        if numpr is None:
            continue
        num_id, ilvl = numpr
        levels = numbering.levels(num_id)
        if num_id == "0" or ilvl not in levels:
            continue
        state = counters.setdefault(num_id, {})
        state[ilvl] = state[ilvl] + 1 if ilvl in state else levels[ilvl][0]
        for deeper in [level for level in state if level > ilvl]:
            del state[deeper]
        _, fmt, text = levels[ilvl]
        if fmt == "bullet" or not text:
            continue

        def value(match: re.Match[str]) -> str:
            level = int(match.group(1)) - 1
            spec = levels.get(level)
            number = state.get(level, spec[0] if spec else 0)
            return str(number)

        labels[paragraph] = _PLACEHOLDER_RE.sub(value, text)
    return labels


def cell_text(cell, labels: dict) -> str:
    """The cell's text as a reader sees it: list numbers included, whitespace
    collapsed, paragraphs joined by single spaces."""
    pieces: list[str] = []
    for paragraph in cell.paragraphs:
        label = labels.get(paragraph._p)
        text = " ".join(paragraph.text.split())
        if label:
            text = f"{label} {text}".strip()
        if text:
            pieces.append(text)
    return " ".join(pieces)
