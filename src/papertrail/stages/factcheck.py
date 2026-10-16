"""7.8 Fact-check (local model).

1. regex pulls every number/percentage from slides.md (+ notes);
2. the LOCAL model pairs each with the claim it supports -> {slide, value, claim} (Ollama; hosted fallback only if Ollama is down);
3. Python checks each value against the source cited for it in deck.json (paper page/table/figure, or an artifact CSV):
   exact match, or equal after rounding. NOT a search of the whole paper (small numbers would match by accident).
Unmatched items block export unless waived in waivers.json with a reason.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from papertrail.common.ctx import RunCtx
from papertrail.common.deckcheck import NOTES_RE, body_of
from papertrail.common.schemas import DeckClaim, FactCheck, NumberPair, NumberPairs, QAIssue
from papertrail.qa.source_map import Slide, parse_slides

NUM_RE = re.compile(r"(?<![\w./#-])(\d[\d,]*(?:\.\d+)?)\s*(%?)")
PROMPT = """You pair numbers with the claims they support. Below is a JSON list of items {{slide, value, context}} taken from slides.
For each item return {{slide, value, claim}} where `claim` is a short phrase (max 15 words) saying what the number is a measurement of.
Do not change `value`. Return JSON {{"pairs": [...]}} with one entry per input item.

{items}
"""


# ------------------------------------------------------------------ step 1: extraction
def extract_numbers(slide: Slide) -> list[dict]:
    """Numbers shown on a slide or said in its notes, minus structural noise (list markers, anchors, code, img names)."""
    out = []
    text = slide.text
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        clean = re.sub(r"<SourceCaption>.*?</SourceCaption>", " ", line)   # citations ("Laban et al., 2025, Fig. 3"), not claims
        clean = re.sub(r'<span class="qa-n">\d+</span>', " ", clean)        # question numbers on the quiz slide are labels, not claims
        clean = re.sub(r"<[^>]+>", " ", clean)
        clean = re.sub(r"(Fig\.?|Figure|Table|p\.|pp\.|Section|Sec\.|§)\s*\d+(\.\d+)?", " ", clean)
        clean = re.sub(r"^\s*(\d+[.)]|[-*])\s+", "", clean)           # ordered-list markers
        clean = re.sub(r"\b\d+\s*x\s*\d+\b|\b16/9\b", " ", clean)      # dimensions/ratios
        for m in NUM_RE.finditer(clean):
            val = m.group(1).rstrip(".,") + m.group(2)
            out.append({"slide": slide.no, "value": val, "context": clean.strip()[:160]})
    seen, uniq = set(), []
    for o in out:
        k = (o["slide"], o["value"])
        if k not in seen:
            seen.add(k)
            uniq.append(o)
    return uniq


# ------------------------------------------------------------------ step 3: anchor-scoped matching
def _numbers_in(text: str) -> list[str]:
    return [m.group(1).replace(",", "") for m in re.finditer(r"(?<![\w])(\d[\d,]*(?:\.\d+)?)", text)]


def _decimals(s: str) -> int:
    return len(s.split(".")[1]) if "." in s else 0


WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"]


def value_matches(value: str, source_text: str) -> bool:
    v = value.replace("%", "").replace(",", "")
    if v.isdigit() and int(v) < len(WORDS) and "%" not in value and re.search(rf"\b{WORDS[int(v)]}\b", source_text, re.I):
        return True  # "6 tasks" on the slide, "six tasks" in the paper
    try:
        fv = float(v)
    except ValueError:
        return False
    d = _decimals(v)
    for tok in _numbers_in(source_text):
        if tok == v:
            return True
        try:
            ft = float(tok)
        except ValueError:
            continue
        if round(ft, d) == round(fv, d) or (d == 0 and abs(ft - fv) < 0.5 and ft != int(ft) and round(ft) == int(fv)):
            return True
        # source states a fraction (0.39) and the slide a percentage (39%), or the reverse
        if "%" in value and abs(ft * 100 - fv) < 10 ** -d / 2 + 1e-9:
            return True
    return False


def source_text(source: str, ctx: RunCtx, paper_pages: dict[int, str], tables: list[dict], figs: list[dict]) -> str:
    s = source.strip()
    m = re.match(r"p\.\s?(\d+)", s, re.I)
    if m:
        return paper_pages.get(int(m.group(1)), "")
    m = re.match(r"Table\s+(\w+)", s, re.I)
    if m:
        want = f"Table {m.group(1)}".lower()
        parts = [json.dumps(t["rows"]) + " " + t.get("caption", "") for t in tables if t["id"].lower() == want]
        return " ".join(parts)
    m = re.match(r"Fig(?:ure|\.)\s?(\w+)", s, re.I)
    if m:
        want = f"fig. {m.group(1)}".lower()
        return " ".join(f["caption"] for f in figs if f["id"].lower() == want)
    m = re.match(r"dataset:(\S+)", s)  # a real record of the paper profile's released dataset: its text and every part
    if m:
        from papertrail.tools import dataset as dataset_tool

        ds = dataset_tool.active()
        return ds.full_text(m.group(1)) if ds else ""
    m = re.match(r"(artifacts/\S+)", s)
    if m and (ctx.run_dir / m.group(1)).exists():
        p = ctx.run_dir / m.group(1)
        return p.read_text(encoding="utf-8", errors="ignore") if p.suffix in (".csv", ".md", ".json", ".txt") else ""
    return ""


def split_pages(md: str) -> dict[int, str]:
    parts = re.split(r"^\[p\.(\d+)\]$", md, flags=re.M)
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def check(ctx: RunCtx, pairs: list[NumberPair], claims: list[DeckClaim]) -> tuple[list[NumberPair], list[NumberPair]]:
    pages = split_pages(ctx.text("paper.md"))
    tables = ctx.load_json("tables.json")
    figs = ctx.load_json("ingested.json")["figures"]
    matched, unmatched = [], []
    for p in pairs:
        cited = [c for c in claims if c.slide == p.slide and (p.value.rstrip("%") in c.text.replace(",", "") or value_matches(p.value, c.text))]
        ok = False
        for c in cited:
            if value_matches(p.value, source_text(c.source, ctx, pages, tables, figs)):
                ok = True
                break
        (matched if ok else unmatched).append(p)
    return matched, unmatched


# ------------------------------------------------------------------ stage
def load_waivers(ctx: RunCtx) -> list[dict]:
    return json.loads(ctx.p("waivers.json").read_text(encoding="utf-8")) if ctx.exists("waivers.json") else []


def check_deck(ctx: RunCtx) -> FactCheck:
    """One pass: extract numbers, pair them with claims (local model), check each against its cited source, apply waivers."""
    slides = parse_slides(ctx.text("deck/slides.md"))
    items = [i for s in slides for i in extract_numbers(s)]
    claims = [DeckClaim(**c) for c in ctx.load_json("deck.json")["claims"]]
    pairs: list[NumberPair] = []
    for i in range(0, len(items), 25):  # small local models: short batches
        batch = items[i:i + 25]
        try:
            res = ctx.h.call("fact_extractor", PROMPT.format(items=json.dumps(batch, ensure_ascii=False)), output_type=NumberPairs)
            got = {(p.slide, p.value): p for p in res.pairs}
        except RuntimeError as e:  # the pairing only labels each number; the check itself is plain Python, so degrade instead of failing
            ctx.h.trace.log(stage=ctx.h.stage, event="extractor_batch_failed", batch=i // 25, error=str(e)[:200])
            got = {}
        for it in batch:  # never trust the model to keep every item: unpaired numbers are still checked
            pairs.append(got.get((it["slide"], it["value"])) or NumberPair(slide=it["slide"], value=it["value"], claim=it["context"][:80]))
    matched, unmatched = check(ctx, pairs, claims)
    waivers = load_waivers(ctx)
    waived = [u for u in unmatched if any(w["slide"] == u.slide and w["value"] == u.value and w.get("reason") for w in waivers)]
    left = [u for u in unmatched if u not in waived]
    fc = FactCheck(n_extracted=len(pairs), n_matched=len(matched), unmatched=left, waived=waived)
    ctx.save("factcheck.json", fc)
    return fc


FIX_HINT = ("is not found in the source cited for it in deck_claims. Fix it one of these ways: (a) correct the number to what the paper says; "
            "(b) cite the right source in deck_claims (a page 'p.N', 'Table N', 'Fig. N' that actually contains the number); (c) if it is a made-up "
            "illustration, replace it with the real dataset example from the difficulty map (worked examples must come from real data); "
            "(d) remove the number. Never invent a number or a source.")


def run(ctx: RunCtx, max_revisions: int = 2) -> None:
    """Check; if numbers are unverified, send them back to the author (at most twice), then re-check. Export blocks what is left."""
    from papertrail.stages import render_loop  # local import: render_loop imports author, which must not import this module at load time

    fc = check_deck(ctx)
    for k in range(1, max_revisions + 1):
        if not fc.unmatched or ctx.config == "oneshot":
            break
        issues = [QAIssue(round=k, source="automatic", slide=u.slide, category="unverified_number", severity="high",
                          detail=f"the number {u.value} ({u.claim}) {FIX_HINT}") for u in fc.unmatched]
        ctx.h.trace.log(stage=ctx.h.stage, event="factcheck_revision", attempt=k, n_unmatched=len(fc.unmatched))
        if not render_loop.revise(ctx, 100 + k, issues):
            break
        render_loop.measure_round(ctx, "post-factcheck")  # layout may have changed: re-measure (automatic checks only)
        fc = check_deck(ctx)
