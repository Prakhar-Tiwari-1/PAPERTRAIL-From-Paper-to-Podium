"""Rule checks on an authored deck (slides.md): layouts, counts, notes length, visuals, text limits, assets, mermaid, claims (SPEC §7.4/§7.6/§9)."""
from __future__ import annotations

import re
from pathlib import Path

from common.anchors import valid_anchor
from common.schemas import MAIN_MAX, MAIN_MIN, QUIZ_LAYOUT, QUIZ_QUESTIONS, DeckClaim
from qa.slop_check import deck_hits, describe
from qa.source_map import Slide, parse_slides

ALLOWED_LAYOUTS = {"title", "claim-figure", "claim-two-figures", "claim-split", "claim-diagram", "claim-example", "claim-table",
                   "claim-bullets", "claim-number", QUIZ_LAYOUT, "section", "workflow"}
MAX_WORDS = 70          # visible words per slide (target 50-70)
MAX_WORDS_QUIZ = 300    # the quiz slide carries its questions and their answers
MAX_WORDS_WORKFLOW = 90 # generated from the run: diagram labels, numbers, repo
MAX_BULLET_ONLY = 2     # main slides with no visual at all
NO_VISUAL_NEEDED = ("title", "section", "workflow", QUIZ_LAYOUT)
VISUAL_RE = re.compile(r"<img|```mermaid|<Turn|<BigNumber|^\s*\|\s*-{3}", re.M)
NOTES_RE = re.compile(r"<!--(.*?)-->", re.S)
IMG_RE = re.compile(r"""(?:src=["']|\]\()(/(?:figures|artifacts)/[^"')\s]+)""")
QUIZ_Q_RE = re.compile(r'class="qa-q"')
NOTES_MIN, NOTES_MAX = 2100, 2900   # 15 to about 20 minutes of speaking at 140 words per minute


def notes_of(slide: Slide) -> str:
    return " ".join(m.strip() for m in NOTES_RE.findall(slide.text))


def body_of(slide: Slide) -> str:
    return NOTES_RE.sub("", slide.text).strip()


def words(s: str) -> int:
    return len(re.findall(r"\S+", s))


def visible_words(slide: Slide) -> int:
    """Words a viewer reads: no notes, no HTML tags, no code fences, no table separator rows, no table pipes."""
    vis = re.sub(r"<[^>]+>", " ", re.sub(r"```.*?```", " ", body_of(slide), flags=re.S))
    return words(re.sub(r"\|", " ", re.sub(r"\|[-: ]+\|[-| :]*", " ", vis)))


def word_limit(layout: str) -> int:
    return MAX_WORDS_QUIZ if layout == QUIZ_LAYOUT else MAX_WORDS_WORKFLOW if layout == "workflow" else MAX_WORDS


def split_main_backup(slides: list[Slide]) -> tuple[list[Slide], list[Slide]]:
    """Backup slides start at a `section` slide titled 'Backup'."""
    for i, s in enumerate(slides):
        if s.layout == "section" and re.search(r"^#\s*backup", body_of(s), re.I | re.M):
            return slides[:i], slides[i:]
    return slides, []


def validate_deck(md: str, run_dir: Path, *, check_notes_total: bool = True, check_mermaid: bool = True,
                  claims: list[DeckClaim] | None = None, require_quiz: bool = True) -> list[str]:
    errs: list[str] = []
    slides = parse_slides(md)
    if not slides:
        return ["no slides parsed from slides.md"]
    if not re.search(r"^theme:\s*\./theme\s*$", md, re.M):
        errs.append("headmatter must contain `theme: ./theme`")
    main, backup = split_main_backup(slides)
    n_main = len(main)
    if not MAIN_MIN <= n_main <= MAIN_MAX:
        errs.append(f"{n_main} main slides before the Backup section; need {MAIN_MIN}-{MAIN_MAX}")
    if backup and len([s for s in backup if s.layout != "section"]) != 3:
        errs.append(f"{len([s for s in backup if s.layout != 'section'])} backup slides; need exactly 3")
    if not backup:
        errs.append("no Backup section slide (`layout: section`, title `# Backup`) before the backup slides")
    for s in slides:
        if s.layout not in ALLOWED_LAYOUTS:
            errs.append(f"slide {s.no}: layout {s.layout!r} is not allowed")
        if not NOTES_RE.search(s.text):
            errs.append(f"slide {s.no}: missing speaker notes (HTML comment at the end of the slide)")
    quiz = [s for s in main if s.layout == QUIZ_LAYOUT]
    if require_quiz:
        if len(quiz) != 1:
            errs.append(f"need exactly one quiz slide (layout `{QUIZ_LAYOUT}`) in the main deck; found {len(quiz)}")
        elif len(QUIZ_Q_RE.findall(quiz[0].text)) != QUIZ_QUESTIONS:
            errs.append(f"quiz slide {quiz[0].no} has {len(QUIZ_Q_RE.findall(quiz[0].text))} questions; need {QUIZ_QUESTIONS} (the pipeline fills them in from quiz.json)")
    no_visual = [s.no for s in main if s.layout not in NO_VISUAL_NEEDED and not VISUAL_RE.search(body_of(s))]
    if len(no_visual) > MAX_BULLET_ONLY:
        errs.append(f"slides {no_visual} have no visual (figure, table, diagram, worked example or big number); at most {MAX_BULLET_ONLY} main slides may be bullets only. "
                    "Use a paper figure, a table excerpt or a diagram from the lists you were given")
    for s in backup:
        if s.layout not in ("section",) and not VISUAL_RE.search(body_of(s)):
            errs.append(f"backup slide {s.no} has no visual (use a table excerpt or a figure)")
    for s in slides:
        if s.layout != "section" and visible_words(s) > word_limit(s.layout):
            errs.append(f"slide {s.no} has {visible_words(s)} visible words; the limit is {word_limit(s.layout)} (aim for 50-70): cut text or split the slide")
    if main and main[-1].layout != "workflow":
        errs.append("the last main slide must use layout `workflow` (Tools & Workflow)")
    if check_notes_total:
        total = sum(words(notes_of(s)) for s in main)
        if not NOTES_MIN <= total <= NOTES_MAX:
            errs.append(f"main-slide notes total {total} words; need {NOTES_MIN}-{NOTES_MAX} (15 to 20 minutes of speaking); "
                        f"the planned minutes per slide times 140 words is the target for each slide")
    for s in slides:
        for src in IMG_RE.findall(s.text):
            rel = src.lstrip("/")
            if not (run_dir / "deck" / "public" / rel).exists() and not (run_dir / rel).exists():
                errs.append(f"slide {s.no}: image {src} does not exist")
        h1 = re.findall(r"^#\s+(.+)$", body_of(s), re.M)
        if s.layout not in ("title", "section") and not h1:
            errs.append(f"slide {s.no}: no `# title` line")
        if s.layout not in ("title", "section") and h1 and (h1[0].strip().endswith("?")):
            errs.append(f"slide {s.no}: rhetorical-question title")
    seen = set()
    for h in deck_hits(md):  # AI-sounding phrasing in slides AND notes: high-severity hits go back to the author
        if h["severity"] == "high" and (h["slide"], h["rule"]) not in seen:
            seen.add((h["slide"], h["rule"]))
            errs.append("AI-sounding writing, rewrite plainly: " + describe(h))
    if check_mermaid:
        from tools.mermaid_check import mermaid_problems

        errs += mermaid_problems(md, run_dir / "deck" if (run_dir / "deck" / "node_modules").exists() else None)
    if claims is not None:
        if not claims:
            errs.append("deck_claims is empty: every number and claim needs an anchor or artifact source")
        for c in claims:
            if c.source.strip().startswith("dataset:"):
                from tools import dataset as dataset_tool

                ds = dataset_tool.active()
                if ds is None:
                    errs.append(f"deck_claims slide {c.slide}: {c.source!r} cites a dataset, but this paper has none; cite the paper (p.N, Table N, Fig. N)")
                elif c.source.strip()[len("dataset:"):] not in ds.ids():
                    errs.append(f"deck_claims slide {c.slide}: {c.source!r} is not a record id of the released dataset")
                continue
            if not (valid_anchor(c.source) or c.source.strip().startswith("artifacts/")):
                errs.append(f"deck_claims slide {c.slide}: source {c.source!r} is not an anchor or artifacts/ path")
            elif c.source.strip().startswith("artifacts/") and not (run_dir / c.source.strip().split()[0]).exists():
                errs.append(f"deck_claims slide {c.slide}: artifact {c.source!r} does not exist")
    return errs
