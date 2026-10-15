"""Put quiz.json on the quiz slide: the questions in the upper block, the answers in a block below (revealed on click in the live talk,
all visible in the PDF). The content is generated here, not by the author model, so the questions and answers are exactly the ones that were
validated, and every answer is registered in deck.json with its anchor so the fact-check covers it. The author writes only the slide title
and the speaker notes."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

from common.schemas import QUIZ_LAYOUT, Quiz
from qa.source_map import parse_slides

DEFAULT_TITLE = "Check your understanding"


def body(quiz: Quiz) -> str:
    qs = "\n".join(f'<div class="qa-q"><span class="qa-n">{n}</span><span>{html.escape(i.question)}</span></div>'
                   for n, i in enumerate(quiz.items, start=1))
    ans = "\n".join(f'<div class="qa-a"><span class="qa-n">{n}</span><span>{html.escape(i.answer)}</span></div>'
                    for n, i in enumerate(quiz.items, start=1))
    # no blank lines inside the HTML block: a blank line would end it and the markdown parser would wrap the rest in paragraphs
    return f'<div class="qa-board">\n<div class="qa-block qa-questions">\n{qs}\n</div>\n<div v-click class="qa-block qa-answers">\n{ans}\n</div>\n</div>'


def has_data_number(text: str) -> bool:
    """True if the text has a number that is a claim about the paper's data (bare 0, 1 and 2 are counting words)."""
    return any(n not in ("0", "1", "2") for n in re.findall(r"\d[\d,]*(?:\.\d+)?%?", text))


def apply(md: str, quiz: Quiz) -> tuple[str, int | None]:
    """Return slides.md with the quiz slide's body replaced by the quiz (title and notes kept) and the slide number, or (md, None)."""
    slide = next((s for s in parse_slides(md) if s.layout == QUIZ_LAYOUT), None)
    if slide is None:
        return md, None
    title = next((l[2:].strip() for l in slide.lines if l.startswith("# ")), DEFAULT_TITLE)
    start = next((k for k, l in enumerate(slide.lines) if l.strip().startswith("<!--")), None)
    notes_block = "\n".join(slide.lines[start:]).strip() if start is not None else "<!--\nAsk the questions, pause, then reveal the answers.\n-->"
    block = f"---\nlayout: {QUIZ_LAYOUT}\n---\n\n# {title}\n\n{body(quiz)}\n\n{notes_block}"
    lines = md.splitlines()
    new = "\n".join(lines[:slide.block_start - 1] + block.splitlines() + [""] + lines[slide.end:])
    return new.rstrip("\n") + "\n", slide.no


def load(run_dir: Path) -> Quiz | None:
    f = run_dir / "quiz.json"
    return Quiz.model_validate_json(f.read_text(encoding="utf-8")) if f.exists() else None


def patch(run_dir: Path) -> bool:
    """Rewrite the quiz slide in the run's slides.md from quiz.json and register its answers as claims. Idempotent."""
    quiz, mdf = load(run_dir), run_dir / "deck" / "slides.md"
    if quiz is None or not mdf.exists():
        return False
    new, no = apply(mdf.read_text(encoding="utf-8"), quiz)
    if no is None:
        return False
    mdf.write_text(new, encoding="utf-8")
    dj = run_dir / "deck.json"
    deck = json.loads(dj.read_text(encoding="utf-8")) if dj.exists() else {"claims": []}
    deck["claims"] = [c for c in deck["claims"] if c["slide"] != no]
    deck["claims"] += [{"slide": no, "text": i.answer, "kind": "claim", "source": i.anchor} for i in quiz.items]
    # a number written in a question is a claim too: without one the fact-check has nothing to match it against
    deck["claims"] += [{"slide": no, "text": i.question, "kind": "claim", "source": i.anchor} for i in quiz.items if has_data_number(i.question)]
    dj.write_text(json.dumps(deck, indent=2), encoding="utf-8")
    return True
