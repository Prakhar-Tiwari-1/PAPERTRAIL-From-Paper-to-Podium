"""final/speaker_script.md: the speaker notes as one readable document (slide number, title, planned minutes, words, the text to say).

The notes live in slides.md as an HTML comment at the end of each slide and inside slides-editable.pptx (notes pane); this file is the
version to print or read from while rehearsing.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from common.deckcheck import body_of, notes_of, split_main_backup, words
from qa.source_map import parse_slides

WPM = 140  # speaking pace used when the notes were written (skills/speaker-notes)


def build(run_dir: Path) -> str:
    md = (run_dir / "deck" / "slides.md").read_text(encoding="utf-8")
    slides = parse_slides(md)
    main, backup = split_main_backup(slides)
    planned: dict[int, float] = {}
    plan = run_dir / "plan.json"
    if plan.exists():
        for i, s in enumerate(json.loads(plan.read_text(encoding="utf-8"))["slides"], start=1):
            planned[i] = s["minutes"]
    main_ids = {s.no for s in main}
    total_words = sum(words(notes_of(s)) for s in main)
    out = ["# Speaker script", "",
           f"Main deck: {len(main)} slides, {total_words} words, about {total_words / WPM:.0f} minutes at {WPM} words per minute. "
           "Backup slides are for the Q&A and are not part of the 20 minutes.", ""]
    for s in slides:
        title = (re.findall(r"^#\s+(.+)$", body_of(s), re.M) or ["(no title)"])[0].strip()
        n = words(notes_of(s))
        part = "main" if s.no in main_ids else "backup"
        mins = f", planned {planned[s.no]:.1f} min" if s.no in planned and s.no in main_ids else ""
        out += [f"## Slide {s.no}: {title}", f"*{part}{mins}, {n} words, about {n / WPM:.1f} min*", "", notes_of(s) or "(no notes)", ""]
    return "\n".join(out)


def write(run_dir: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "speaker_script.md"
    p.write_text(build(run_dir), encoding="utf-8")
    return p


if __name__ == "__main__":
    import sys

    r = Path(sys.argv[1])
    print(write(r, r / "final"))
