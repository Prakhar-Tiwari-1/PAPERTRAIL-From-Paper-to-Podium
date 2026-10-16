import json
from pathlib import Path

from PIL import Image

from papertrail.qa.contact_sheet import annotate, contact_sheets
from papertrail.qa.source_map import parse_slides, resolve_source_lines
from papertrail.tools.mermaid_check import extract_mermaid

DECK = """---
theme: ./theme
canvasWidth: 1280
layout: title
---

# Title slide

Subtitle

<!--
notes one
-->

---
layout: claim-bullets
---

# Claim two

- first bullet here
- second bullet

---

# Claim three without frontmatter

```mermaid
flowchart LR
  A --> B
```
"""


def test_parse_slides_handles_headmatter_frontmatter_and_fences():
    s = parse_slides(DECK)
    assert [x.no for x in s] == [1, 2, 3]
    assert s[0].layout == "title" and s[1].layout == "claim-bullets" and s[2].layout == "default"
    assert "Claim two" in s[1].text and s[1].start > 10


def test_demo_deck_in_repo_parses_to_six_slides():
    md = (Path(__file__).resolve().parent.parent / "deck" / "slides.md").read_text(encoding="utf-8")
    assert len(parse_slides(md)) == 6


def test_source_line_resolution():
    s = parse_slides(DECK)[1]
    els = [{"id": 1, "type": "title", "text_excerpt": "Claim two", "src": ""},
           {"id": 2, "type": "list", "text_excerpt": "second bullet", "src": ""}]
    m = resolve_source_lines(s, els)
    lines = DECK.splitlines()
    assert "Claim two" in lines[int(m[1]) - 1]
    assert "second bullet" in lines[int(m[2]) - 1]


def test_mermaid_extraction_reports_fence_line():
    blocks = extract_mermaid(DECK)
    assert len(blocks) == 1 and "A --> B" in blocks[0][1]
    assert DECK.splitlines()[blocks[0][0] - 1].startswith("```mermaid")


def test_annotate_and_contact_sheet(tmp_path):
    for i in range(1, 6):
        Image.new("RGB", (1280, 720), (250, 250, 247)).save(tmp_path / f"s{i}.png")
    out = annotate(tmp_path / "s1.png", [{"id": 1, "bbox": [0.05, 0.1, 0.5, 0.1]}], tmp_path / "a.png")
    assert out.exists() and Image.open(out).size == (1280, 720)
    sheets = contact_sheets([tmp_path / f"s{i}.png" for i in range(1, 6)], tmp_path / "sheets")
    assert len(sheets) == 1 and Image.open(sheets[0]).size == (4 * 480, 2 * 270)


def test_banned_list_matches_slide_design_skill():
    root = Path(__file__).resolve().parent.parent
    banned = json.loads((root / "src" / "papertrail" / "qa" / "banned.json").read_text(encoding="utf-8"))
    skill = (root / "skills" / "slide-design" / "SKILL.md").read_text(encoding="utf-8").lower()
    for phrase in ("delve", "unlock", "revolutionize", "game-changer", "seamless"):
        assert phrase in skill and any(phrase in p for p in banned["phrases"])
    for t in ("introduction", "overview", "key takeaways", "conclusion"):
        assert t in skill and t in banned["titles"]
