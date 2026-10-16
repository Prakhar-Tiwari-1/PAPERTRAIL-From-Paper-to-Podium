"""Anchors point at where the paper says something: "p.7", "pp. 22-24", "Table 1", "Fig. 4 (p.5)", "Appendix F (p.22-24)".

Models write them in many shapes, so we accept an anchor when it contains a page, table, figure or appendix reference anywhere,
and keep the strict part (a real page number, within the paper) for page references.
"""
from __future__ import annotations

import re

PAGE_RE = re.compile(r"\bpp?\.\s?(\d+)(?:\s*[-–]\s*(\d+))?", re.I)
OTHER_RE = re.compile(r"\b(Table\s+[\w.]+|Fig(?:ure|\.)\s?[\w.]+|Appendix\s+[\w.]+)", re.I)


def valid_anchor(anchor: str, n_pages: int | None = None) -> bool:
    a = anchor.strip()
    if not a:
        return False
    pages = PAGE_RE.findall(a)
    if n_pages is not None:
        for lo, hi in pages:
            if not 1 <= int(lo) <= n_pages or (hi and not int(lo) <= int(hi) <= n_pages):
                return False
    return bool(pages) or bool(OTHER_RE.search(a))


def first_page(anchor: str) -> int | None:
    m = PAGE_RE.search(anchor)
    return int(m.group(1)) if m else None


def anchor_pages_of(anchors: list[str]) -> list[int]:
    """Page numbers named by anchors such as 'p.7', 'Fig. 4 (p.5)', 'Appendix F (p.22-24)' (a short range is expanded)."""
    pages: set[int] = set()
    for a in anchors:
        for lo, hi in PAGE_RE.findall(a):
            lo_i = int(lo)
            pages.update(range(lo_i, int(hi) + 1) if hi and int(hi) - lo_i < 4 else [lo_i])
    return sorted(pages)
