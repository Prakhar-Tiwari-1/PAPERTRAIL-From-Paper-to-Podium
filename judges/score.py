"""Judge scoring (SPEC §7.9): one call per rubric dimension, temperature 0, strict JSON per item, two real repeats.

Bias controls: atomic items; a verbatim paper quote is required for any faithfulness pass (and the quote must really occur in the paper);
generator identity is not in the inputs. Items marked `auto` in rubric.yaml are computed from measurements; items marked `vision` are judged
from the slide images. The judge never steers the deck it grades: this module only reads the deck.

Context is kept small and cache-friendly: the judge sees the digest and only the paper pages the deck and digest cite (not the whole paper),
and the prompt puts the shared context first and the dimension's items last, so providers with prefix caching reuse it across dimensions.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from common.ctx import RunCtx
from common.deckcheck import body_of, notes_of, split_main_backup, words
from common.papertext import anchor_pages, pages_text
from common.repair import fill, load_prompt
from common.schemas import Checklist, JudgeDimensionResult, JudgeReport, Plan
from qa.contact_sheet import contact_sheets
from qa.source_map import parse_slides

ROOT = Path(__file__).resolve().parent.parent
LAYOUT_CATS = {"Object Alignment Issues", "Content Overflow/Cut-off", "Occluded Content"}
DENSITY_RULES = {"too_many_words", "too_many_bullets", "banned_phrase", "banned_title", "rhetorical_question_title",
                 "emoji", "gradient", "shadow"}

VISION_PROMPT = """You are grading the VISUAL quality of a slide deck from images: contact sheets of all slides (numbered thumbnails, left to right, top to bottom).
Judge only what you can see. Grade each item pass or fail.

Items:
{items}

Rules: if an item fails, `issue` names the slides and the specific problem, and `suggested_fix` a concrete fix; if it passes, leave both empty.
`evidence_paper_quote` is not needed here (leave null). `evidence_slide` is the slide number that best shows the evidence, or null.
Return JSON {"results": [{"item_id": "...", "pass": true or false, "evidence_slide": 3 or null, "evidence_paper_quote": null, "issue": "", "suggested_fix": ""}]}
with exactly one entry per item.

Automatic facts about the deck:
{facts}
"""


def load_rubric() -> dict:
    return yaml.safe_load((ROOT / "config" / "rubric.yaml").read_text(encoding="utf-8"))["dimensions"]


# ------------------------------------------------------------------ automatic items
def auto_results(ctx: RunCtx) -> dict[str, tuple[bool, str]]:
    """N3, D1, D2, D3: measured, not judged."""
    slides = parse_slides(ctx.text("deck/slides.md"))
    main, _ = split_main_backup(slides)
    notes_total = sum(words(notes_of(s)) for s in main)
    plan_ok, minutes = True, ""
    if ctx.exists("plan.json"):
        plan = ctx.load("plan.json", Plan)
        plan_ok = all(s.minutes <= 2 for s in plan.slides)
        minutes = f", planned minutes {sum(s.minutes for s in plan.slides):.1f}"
    n3 = 12 <= len(main) <= 14 and 2400 <= notes_total <= 2900 and plan_ok
    res = {"N3": (n3, f"{len(main)} main slides, {notes_total} words of notes{minutes}")}
    qa = ctx.load_json("qa.json") if ctx.exists("qa.json") else None
    if qa is None:
        return {**res, "D1": (False, "no qa.json"), "D2": (False, "no qa.json"), "D3": (False, "no qa.json")}
    last = qa["rounds"][-1]["issues"]
    d1_bad = [i for i in last if i["source"] == "automatic" and (i["category"] in DENSITY_RULES or (
        i["category"].startswith("slop:") and i["severity"] == "high"))]
    res["D1"] = (not d1_bad, f"{len(d1_bad)} density, banned-pattern or AI-sounding-phrase issues in the last round")
    d2_bad = [i for i in last if i["severity"] == "high" and (
        (i["source"] == "automatic" and i["category"] in {"overflow", "outside_safe_area", "contrast", "font_below_16px"})
        or (i["source"].startswith("vision") and i["category"] in LAYOUT_CATS))]
    res["D2"] = (not d2_bad, f"{len(d2_bad)} high overflow/alignment/contrast issues in the last round")
    d3_bad = [i for i in last if i["category"] in ("image_upscaled", "font_below_16px", "Improper Image Sizing")]
    res["D3"] = (not d3_bad, f"{len(d3_bad)} figure-size/readability issues in the last round")
    return res


def pipeline_facts(ctx: RunCtx) -> str:
    """What actually produced this deck. The Tools & Workflow slide (B2) must be judged against THIS, not against the paper."""
    from report import trace_page

    st = trace_page.stage_stats(trace_page.read_trace(ctx.run_dir))
    parts = []
    for name, s in st.items():
        if name and s["models"]:
            parts.append(f"{name}: " + ", ".join(trace_page.short_model(m) for m in s["models"]))
    return ("- PIPELINE FACTS for item B2 (the Tools & Workflow slide describes the pipeline, not the paper; check it against these, "
            "not against the paper): own Python harness (state machine), PydanticAI for typed calls via OpenRouter, skills and tools, "
            "two critics (vision + student) in a render loop, fact-check, cross-vendor judge. Models per stage so far: " + "; ".join(parts))


def facts_block(ctx: RunCtx, auto: dict[str, tuple[bool, str]]) -> str:
    claims = ctx.load_json("deck.json")["claims"] if ctx.exists("deck.json") else []
    lines = [f"- {k}: {'meets' if ok else 'does NOT meet'} the rule ({d})" for k, (ok, d) in auto.items()]
    lines.append(pipeline_facts(ctx))
    lines.append("- deck claim -> source map (slide, text, source):")
    lines += [f"  * slide {c['slide']}: {c['text'][:90]} <- {c['source']}" for c in claims[:120]]
    return "\n".join(lines)


def deck_blob(ctx: RunCtx) -> str:
    return "\n\n".join(f"## Slide {s.no} ({s.layout})\n{body_of(s)}\nNOTES: {notes_of(s)}" for s in parse_slides(ctx.text("deck/slides.md")))


def evidence_text(ctx: RunCtx) -> str:
    """The paper pages the judge may quote: those cited by the deck's claims and the digest, plus page 1. Small, not the whole paper."""
    anchors: list[str] = []
    if ctx.exists("deck.json"):
        anchors += [c["source"] for c in ctx.load_json("deck.json")["claims"]]
    if ctx.exists("digest.json"):
        d = ctx.load_json("digest.json")
        anchors += [c["anchor"] for c in d.get("claims", [])] + [t["anchor"] for t in d.get("terms", [])]
    pages = sorted(set(anchor_pages(anchors)) | {1})
    text = pages_text(ctx.text("paper.md"), pages, max_chars=36000)
    return text or (ctx.text("paper_llm.md") if ctx.exists("paper_llm.md") else ctx.text("paper.md")[:36000])


def _norm(s: str) -> str:
    return re.sub(r"\W+", "", s).lower()


def latest_sheets(ctx: RunCtx) -> list[bytes]:
    """Contact sheets of the final deck: rebuilt from the latest round's slide PNGs, so they always match the last render."""
    rounds = sorted((p for p in ctx.p("render", ".keep").parent.glob("round_*") if p.is_dir()), key=lambda p: int(p.name.split("_")[1]))
    for rd in reversed(rounds):
        pngs = sorted((p for p in rd.glob("slide-*.png") if re.fullmatch(r"slide-\d+\.png", p.name)),  # not the .annotated.png copies
                      key=lambda p: int(p.stem.split("-")[1]))
        if pngs:
            return [s.read_bytes() for s in contact_sheets(pngs, rd / "judge_sheets")[:2]]
    return []


# ------------------------------------------------------------------ scoring
def _new_row(i: dict, dim: str) -> dict:
    return {"id": i["id"], "dimension": dim, "points": i["points"], "hard_gate": bool(i.get("hard_gate")), "passes": [], "auto": False,
            "issue": "", "suggested_fix": "", "evidence_slide": None, "evidence_paper_quote": None}


def score(ctx: RunCtx, judge_role: str = "judge", repeats: int = 2, checklist: Checklist | None = None,
          out_name: str = "judge_report.json") -> JudgeReport:
    rubric = load_rubric()
    auto = auto_results(ctx)
    facts = facts_block(ctx, auto)
    deck = deck_blob(ctx)
    paper = evidence_text(ctx)
    paper_all = _norm(ctx.text("paper.md"))
    digest = ctx.text("digest.json") if ctx.exists("digest.json") else ""
    children: dict[str, list] = {}
    for it in (checklist.items if checklist else []):
        children.setdefault(it.parent, []).append(it)
    template = load_prompt("judge_dimension.md")

    item_rows: dict[str, dict] = {}
    for dim, d in rubric.items():
        for i in d["items"]:
            if i.get("auto"):
                ok, detail = auto[i["id"]]
                item_rows[i["id"]] = {**_new_row(i, dim), "passes": [ok] * repeats, "auto": True, "issue": "" if ok else detail}
        # vision items: judged from the slide images
        vis_items = [i for i in d["items"] if i.get("vision")]
        if vis_items:
            sheets = latest_sheets(ctx)
            for i in vis_items:
                row = item_rows.setdefault(i["id"], _new_row(i, dim))
                if not sheets:
                    row["passes"] += [False] * repeats
                    row["issue"] = "not judged: no rendered slide images found"
                    continue
                prompt = fill(VISION_PROMPT, items=f"- {i['id']} ({i['points']} pts): {i['text']}", facts=facts)
                for r in range(repeats):
                    res = ctx.h.call(judge_role, prompt, output_type=JudgeDimensionResult, repeat_idx=r, images=sheets)
                    x = {y.item_id: y for y in res.results}.get(i["id"])
                    row["passes"].append(bool(x and x.passed))
                    if x and not x.passed and not row["issue"]:
                        row["issue"], row["suggested_fix"] = x.issue, x.suggested_fix
                    if x and r == 0:
                        row["evidence_slide"] = x.evidence_slide
        llm_items = [i for i in d["items"] if not i.get("auto") and not i.get("vision")]
        if not llm_items:
            continue
        lines, detail_lines = [], []
        for i in llm_items:
            lines.append(f"- {i['id']} ({i['points']} pts): {i['text']}")
            for c in children.get(i["id"], []):
                detail_lines.append(f"- {c.id} (sub-check of {i['id']}; {i['id']} fails if this fails): {c.text}")
                lines.append(f"- {c.id}: {c.text}")
        details = "\n".join(detail_lines) or "(none)"

        def build(item_lines: list[str]) -> str:
            return fill(template, items="\n".join(item_lines), facts=facts, checklist=details, digest=digest, paper=paper, deck=deck)

        prompt = build(lines)
        for r in range(repeats):  # distinct repeat_idx: a repeat is a real second call, never a cache hit
            res = ctx.h.call(judge_role, prompt, output_type=JudgeDimensionResult, repeat_idx=r)
            by_id = {x.item_id: x for x in res.results}
            # cheap judges sometimes skip items: ask once more for just those (a parent answered through all its sub-checks is fine)
            missing = [i for i in llm_items if i["id"] not in by_id
                       and not (children.get(i["id"]) and all(c.id in by_id for c in children[i["id"]]))]
            if missing:
                sub = []
                for i in missing:
                    sub.append(f"- {i['id']} ({i['points']} pts): {i['text']}")
                    sub += [f"- {c.id}: {c.text}" for c in children.get(i["id"], []) if c.id not in by_id]
                res2 = ctx.h.call(judge_role, build(sub), output_type=JudgeDimensionResult, repeat_idx=r + 10)
                by_id.update({x.item_id: x for x in res2.results})
            for i in llm_items:
                row = item_rows.setdefault(i["id"], _new_row(i, dim))
                x = by_id.get(i["id"])
                kids = children.get(i["id"], [])
                if x is None and kids and all(c.id in by_id for c in kids):
                    ok = True  # the judge answered every sub-check but skipped the parent: the parent is the AND of its children
                elif x is None:
                    ok = False
                    row["issue"] = row["issue"] or "not judged: the judge returned no verdict for this item"
                else:
                    ok = bool(x.passed)
                if ok and i["id"].startswith("F"):
                    # a faithfulness pass needs a verbatim quote that really occurs in the paper; every repeat is recorded, and one
                    # verified quote is enough as long as every repeat's VERDICT is pass (a second call may paraphrase the same quote)
                    quote = (x.evidence_paper_quote or "").strip() if x else ""
                    if quote and _norm(quote) in paper_all:
                        row["quote_verified"] = True
                        row.setdefault("verified_quote", quote)
                for c in kids:
                    cx = by_id.get(c.id)
                    if not (cx and cx.passed):
                        ok = False
                        if not row["issue"] and cx:
                            row["issue"], row["suggested_fix"] = cx.issue, cx.suggested_fix
                row["passes"].append(ok)
                if x and not ok and not row["issue"]:
                    row["issue"], row["suggested_fix"] = x.issue, x.suggested_fix
                if x and r == 0:
                    row["evidence_slide"], row["evidence_paper_quote"] = x.evidence_slide, x.evidence_paper_quote

    scores = {dim: 0.0 for dim in rubric}
    disagreements, hard_fail = [], False
    for row in item_rows.values():
        row["pass"] = all(row["passes"])  # conservative: pass only if every repeat passes
        if row["pass"] and row["id"].startswith("F") and not row.get("quote_verified") and not row.get("auto"):
            row["pass"] = False  # all repeats said pass, but none of them gave a quote that exists in the paper
            row["issue"] = row["issue"] or "faithfulness pass without a verbatim paper quote (no quote found in the paper)"
        if row.get("verified_quote"):
            row["evidence_paper_quote"] = row["verified_quote"]
        if len(set(row["passes"])) > 1:
            disagreements.append(row["id"])
        if row["pass"]:
            scores[row["dimension"]] += row["points"]
        elif row["hard_gate"]:
            hard_fail = True
    report = JudgeReport(judge_role=judge_role, judge_model=ctx.h.slug_for(judge_role), repeats=repeats, scores=scores,
                         total=sum(scores.values()), hard_fail=hard_fail, items=sorted(item_rows.values(), key=lambda r: r["id"]),
                         disagreements=sorted(disagreements))
    ctx.save(out_name, report)
    return report
