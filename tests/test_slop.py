import json
from pathlib import Path

from qa.slop_check import deck_hits, describe, scan_line

DECK = """---
theme: ./theme
layout: title
---

# Models lose the thread

Why they delve into the wrong answer

<!--
Let's dive in. It's not just a bug, but a pattern. The result — as you see — plays a crucial role.
-->

---
layout: claim-bullets
---

# The drop is 39 percent

- First answers stick
- Later turns add details

```python
delve = "code is not prose"
```

<!--
The drop is 39 percent across six tasks. Next slide.
-->
"""


def test_phrases_in_slides_and_notes_are_found_with_line_numbers():
    hits = deck_hits(DECK)
    rules = {(h["slide"], h["where"], h["rule"]) for h in hits}
    assert (1, "slide", "phrase: delve") in rules
    assert (1, "notes", "phrase: let's dive") in rules
    assert (1, "notes", "not just X but Y") in rules
    assert (1, "notes", "phrase: crucial role") in rules or (1, "notes", "phrase: plays a crucial role") in rules
    assert any(h["rule"] == "em dash" and h["severity"] == "low" for h in hits)
    h = next(h for h in hits if h["rule"] == "phrase: delve")
    assert DECK.splitlines()[h["line"] - 1].count("delve") == 1 and "line" in describe(h)


def test_clean_slide_and_code_fences_are_not_flagged():
    assert [h for h in deck_hits(DECK) if h["slide"] == 2] == []


def test_word_boundaries():
    assert scan_line("We delve deeper") and not scan_line("The seamstress sewed")
    assert not scan_line("A well-known robust estimator")  # 'a robust' is only flagged as praise phrasing
    assert any(r[1] == "emoji" for r in scan_line("Great job \U0001F680"))


def test_banned_json_phrases_are_a_subset_of_slop_json():
    root = Path(__file__).resolve().parent.parent / "qa"
    banned = json.loads((root / "banned.json").read_text(encoding="utf-8"))["phrases"]
    slop = json.loads((root / "slop.json").read_text(encoding="utf-8"))
    allp = {p.lower() for p in slop["high_phrases"] + slop["low_phrases"]}
    missing = [p for p in banned if p.lower() not in allp and p.lower() not in {"robust and", "a robust"}]
    assert missing == [], missing


def test_author_validation_sends_slop_back(tmp_path):
    from common.deckcheck import validate_deck

    errs = validate_deck(DECK, tmp_path, check_mermaid=False, check_notes_total=False)
    assert any("AI-sounding writing" in e and "delve" in e for e in errs)
