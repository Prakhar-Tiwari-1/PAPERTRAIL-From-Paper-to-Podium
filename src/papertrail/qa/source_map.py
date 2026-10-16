"""Slidev slide parsing and element -> slides.md line mapping (SPEC §7.7 step 6, "source_line")."""
from __future__ import annotations

import re
from dataclasses import dataclass

_YAMLISH = re.compile(r"^(\s*[\w\-]+\s*:.*|\s+.*|\s*-\s+.*|\s*#.*)$")


@dataclass
class Slide:
    no: int            # 1-based
    start: int         # 1-based line of the first content line
    end: int           # 1-based, inclusive
    front: dict        # parsed simple key: value frontmatter
    lines: list[str]   # content lines (without frontmatter)
    block_start: int = 1  # 1-based line of the `---` that opens this slide's block (frontmatter included)

    @property
    def layout(self) -> str:
        return str(self.front.get("layout", "default"))

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def _is_sep(line: str) -> bool:
    return line.rstrip() == "---"


def parse_slides(md: str) -> list[Slide]:
    """Split Slidev markdown into slides, honouring code fences and per-slide frontmatter blocks."""
    lines = md.splitlines()
    n = len(lines)
    # separator positions outside code fences
    seps, in_fence = [], False
    for i, l in enumerate(lines):
        if l.lstrip().startswith("```"):
            in_fence = not in_fence
        elif not in_fence and _is_sep(l):
            seps.append(i)
    slides: list[Slide] = []
    # segments between separators; a segment that is entirely yaml-ish and is followed by content is a frontmatter block
    bounds = ([-1] if not seps or seps[0] != 0 else []) + seps + [n]
    segs = [(bounds[k] + 1, bounds[k + 1] - 1) for k in range(len(bounds) - 1)]
    k = 0
    pending_front: dict | None = None
    front_a = 0
    while k < len(segs):
        a, b = segs[k]
        body = [l for l in lines[a:b + 1]]
        nonempty = [l for l in body if l.strip()]
        is_front = bool(nonempty) and all(_YAMLISH.match(l) for l in nonempty) and re.match(r"^\s*[\w\-]+\s*:", nonempty[0]) \
            and (lines[a - 1].rstrip() == "---" if a > 0 else True) and pending_front is None and k + 1 < len(segs)
        if is_front:
            pending_front = _simple_yaml(nonempty)
            front_a = a
            k += 1
            continue
        if not nonempty and pending_front is None and not slides and k == 0:
            k += 1
            continue
        bs = front_a if pending_front is not None else a
        slides.append(Slide(no=len(slides) + 1, start=a + 1, end=b + 1, front=pending_front or {}, lines=body, block_start=max(bs, 1)))
        pending_front = None
        k += 1
    # the first slide's frontmatter is the headmatter; slides after the first that are empty are ignored
    return [s for s in slides if s.text.strip() or s.front]


def _simple_yaml(lines: list[str]) -> dict:
    d = {}
    for l in lines:
        m = re.match(r"^([\w\-]+)\s*:\s*(.*)$", l)
        if m:
            d[m.group(1)] = m.group(2).strip().strip("'\"")
    return d


def _norm(s: str) -> str:
    return re.sub(r"[`*_#>\-\[\]()<>/!]", "", s).lower().strip()


def resolve_source_lines(slide: Slide, elements: list[dict]) -> dict[int, str]:
    """element id -> 'a-b' (or 'a') lines in slides.md. Falls back to the slide's whole range."""
    out: dict[int, str] = {}
    for el in elements:
        found: int | None = None
        excerpt = _norm(el.get("text_excerpt", ""))[:28]
        src = el.get("src", "")
        for off, l in enumerate(slide.lines):
            ln = slide.start + off
            nl = _norm(l)
            if el["type"] in ("diagram",) and l.lstrip().startswith("```mermaid"):
                found = ln
                break
            if el["type"] == "figure" and src and src.split("/")[-1] in l:
                found = ln
                break
            if excerpt and len(excerpt) >= 6 and excerpt in nl:
                found = ln
                break
        out[el["id"]] = f"{found}" if found else f"{slide.start}-{slide.end}"
    return out
