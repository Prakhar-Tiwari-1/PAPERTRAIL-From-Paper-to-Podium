"""Paper text for prompts, kept small.

The full paper.md (about 155k characters: bibliography, one-token figure labels, 15 appendices) is only used to VERIFY things in Python.
Prompts get `paper_llm.md` (main body, junk removed, appendices reduced to a stub each) and, where a model needs evidence, only the pages
that the anchors point at.
"""
from __future__ import annotations

import re

STUB_CHARS = 700
JUNK_RE = re.compile(r"[\d\s.,%/()\-–+:]*")


def _junk(line: str) -> bool:
    s = line.strip()
    return len(s) <= 3 or JUNK_RE.fullmatch(s) is not None


def make_llm_text(md: str, stub_chars: int = STUB_CHARS) -> str:
    """Main body without the bibliography and figure-label junk; each appendix cut to its heading plus the first `stub_chars`."""
    out: list[str] = []
    in_refs = in_appendix = False
    stub_left = 0
    for line in md.splitlines():
        if line.strip() == "## References":
            in_refs = True
            continue
        if line.startswith("## Appendices"):
            in_refs, in_appendix = False, True
            out.append(line)
            continue
        if in_refs:
            continue
        if _junk(line) and not re.match(r"^\[p\.\d+\]$", line):
            continue
        if in_appendix:
            if re.match(r"^## Appendix [A-Z]\b", line):
                stub_left = stub_chars
                out.append(line)
                continue
            if re.match(r"^\[p\.\d+\]$", line):
                out.append(line)
                continue
            if stub_left > 0:
                out.append(line)
                stub_left -= len(line) + 1
            continue
        out.append(line)
    return "\n".join(out)


def split_pages(md: str) -> dict[int, str]:
    parts = re.split(r"^\[p\.(\d+)\]$", md, flags=re.M)
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def anchor_pages(anchors: list[str]) -> list[int]:
    from papertrail.common.anchors import PAGE_RE

    pages: set[int] = set()
    for a in anchors:
        for lo, hi in PAGE_RE.findall(a):
            lo_i = int(lo)
            pages.update(range(lo_i, int(hi) + 1) if hi and int(hi) - lo_i < 4 else [lo_i])
    return sorted(pages)


def pages_text(md: str, pages: list[int], max_chars: int = 40000) -> str:
    """Cleaned text of the given pages, capped. Pages the anchors point at are what a judge needs for verbatim quotes."""
    by = split_pages(md)
    out, used = [], 0
    for p in pages:
        body = "\n".join(l for l in by.get(p, "").splitlines() if not _junk(l))
        chunk = f"[p.{p}]\n{body}"
        if used + len(chunk) > max_chars:
            break
        out.append(chunk)
        used += len(chunk)
    return "\n".join(out)
