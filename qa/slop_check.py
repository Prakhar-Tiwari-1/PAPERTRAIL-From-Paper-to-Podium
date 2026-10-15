"""AI-slop check for slide text AND speaker notes (the DOM checks in qa/overflow_check.mjs only see rendered slide text).

Looks for stock AI phrasing ("delve", "plays a crucial role", "not just X but Y", em dashes...). Each hit carries the slide, the
line in slides.md and where it was found (slide or notes). 'high' hits are sent back to the author; 'low' hits are advice.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from qa.source_map import Slide, parse_slides

CONFIG = Path(__file__).resolve().parent / "slop.json"


@lru_cache(maxsize=1)
def _cfg() -> dict:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    cfg["_high"] = [(p, re.compile(r"(?<![\w-])" + re.escape(p.lower()) + r"(?![\w-])")) for p in cfg["high_phrases"]]
    cfg["_low"] = [(p, re.compile(r"(?<![\w-])" + re.escape(p.lower()) + r"(?![\w-])")) for p in cfg["low_phrases"]]
    cfg["_hre"] = [(r["name"], re.compile(r["pattern"], re.I)) for r in cfg["high_regex"]]
    cfg["_lre"] = [(r["name"], re.compile(r["pattern"], re.I)) for r in cfg["low_regex"]]
    return cfg


def scan_line(line: str) -> list[tuple[str, str, str]]:
    """[(severity, rule, matched text)] for one line of prose."""
    cfg, low, out = _cfg(), line.lower(), []
    for p, rx in cfg["_high"]:
        if rx.search(low):
            out.append(("high", f"phrase: {p}", p))
    for p, rx in cfg["_low"]:
        if rx.search(low):
            out.append(("low", f"phrase: {p}", p))
    for name, rx in cfg["_hre"]:
        m = rx.search(line)
        if m:
            out.append(("high", name, m.group(0).strip()[:50]))
    for name, rx in cfg["_lre"]:
        if rx.search(line):
            out.append(("low", name, name))
    return out


def slide_hits(slide: Slide) -> list[dict]:
    """Hits for one slide: code fences, HTML tags and attribute values are not prose and are skipped."""
    hits, in_fence, in_notes = [], False, False
    for off, raw in enumerate(slide.lines):
        line_no = slide.start + off
        s = raw.strip()
        if s.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if "<!--" in s:
            in_notes = True
        prose = re.sub(r"<!--|-->", " ", raw)
        if not in_notes:
            prose = re.sub(r"<[^>]+>", " ", prose)
        for sev, rule, text in scan_line(prose):
            hits.append({"slide": slide.no, "line": line_no, "where": "notes" if in_notes else "slide", "severity": sev,
                         "rule": rule, "text": text})
        if "-->" in s:
            in_notes = False
    return hits


def deck_hits(md: str) -> list[dict]:
    return [h for s in parse_slides(md) for h in slide_hits(s)]


def describe(h: dict) -> str:
    return f"slide {h['slide']} line {h['line']} ({h['where']}): {h['rule']}" + (f" -> \"{h['text']}\"" if h["text"] != h["rule"] else "")
