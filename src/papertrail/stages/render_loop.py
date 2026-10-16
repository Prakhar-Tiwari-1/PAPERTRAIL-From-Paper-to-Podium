"""7.7 Render loop (DeepPresenter-style, two critics): render -> automatic checks (incl. empty-space) -> vision critic (slide + deck) ->
student critic -> triage (no forced issues) -> per-slide revision. Stop at zero high-severity issues, or after `max_rounds` rounds
followed by one verifying critique. Output: qa.json.

oneshot config: one measuring round (automatic checks only), no critics and no revision.
"""
from __future__ import annotations

import json
import shutil
from collections import Counter
from pathlib import Path

from papertrail.common.ctx import RunCtx
from papertrail.common.deckcheck import body_of, notes_of
from papertrail.common.repair import fill, load_prompt
from papertrail.common.schemas import QAIssue, StudentReport, VisionReport
from papertrail.qa.contact_sheet import annotate, contact_sheets
from papertrail.qa.slop_check import describe, slide_hits
from papertrail.qa.source_map import Slide, parse_slides, resolve_source_lines
from papertrail.qa.triage import triage
from papertrail.stages.revise import revise  # noqa: F401  (re-exported: stages.factcheck calls render_loop.revise)
from papertrail.tools import render

# a slide whose content leaves a hole this tall (px, of the 576 px content area) or uses less of the area than this is "sparse"
SPARSE_BAND_PX = 100
SPARSE_COVERAGE = 0.40
SPARSE_EXEMPT = ("title", "section", "workflow")

SPARSE_DETAIL = ("{pct}% of the content area is used and the largest empty band is {band}px tall. Do not add text: add a relevant visual "
                 "(paper figure, table excerpt, Mermaid diagram of the mechanism, worked example, or one big number), or use layout claim-split")


# ------------------------------------------------------------------ gathering issues for one round
def automatic_issues(k: int, out_dir: Path, slides: list[Slide]) -> list[QAIssue]:
    issues = []
    for s in slides:
        f = out_dir / f"slide-{s.no}.checks.json"
        if not f.exists():
            continue
        for c in json.loads(f.read_text(encoding="utf-8")):
            issues.append(QAIssue(round=k, source="automatic", slide=s.no, category=c["rule"], severity=c["severity"],
                                  detail=c["detail"], source_lines=f"{s.start}-{s.end}"))
        m = out_dir / f"slide-{s.no}.metrics.json"
        if m.exists() and s.layout not in SPARSE_EXEMPT:
            met = json.loads(m.read_text(encoding="utf-8"))
            if "coverage" in met and (met["empty_band_px"] >= SPARSE_BAND_PX or met["coverage"] < SPARSE_COVERAGE):
                issues.append(QAIssue(round=k, source="automatic", slide=s.no, category="sparse_slide", severity="high",
                                      detail=SPARSE_DETAIL.format(pct=round(met["coverage"] * 100), band=met["empty_band_px"]),
                                      source_lines=f"{s.start}-{s.end}"))
    for s in slides:  # slop check: slide text AND speaker notes, with the real line in slides.md
        for h in slide_hits(s):
            issues.append(QAIssue(round=k, source="automatic", slide=s.no, category="slop: " + h["rule"], severity=h["severity"],
                                  detail=describe(h), source_lines=str(h["line"])))
    return issues


def vision_slide_issues(ctx: RunCtx, k: int, out_dir: Path, slides: list[Slide], template: str) -> list[QAIssue]:
    """One call per slide: annotated PNG + element list (names only) + the taxonomy prompt. Output is validated JSON."""
    issues = []
    for s in slides:
        emap = json.loads((out_dir / f"slide-{s.no}.elements.json").read_text(encoding="utf-8"))
        els = emap["elements"]
        ann = annotate(out_dir / f"slide-{s.no}.png", els, out_dir / f"slide-{s.no}.annotated.png")
        names = "\n".join(f"{e['id']}: {e['type']} \"{e['text_excerpt'][:50]}\"" for e in els)
        prompt = fill(template, slide_no=s.no, elements=names)
        rep = ctx.h.call("vision_critic", prompt, output_type=VisionReport, images=[ann.read_bytes()])
        lines = resolve_source_lines(s, els)
        for v in rep.issues:
            ref = sorted({lines[i] for i in v.element_ids if i in lines}) or [f"{s.start}-{s.end}"]
            detail = f"{v.issue} | fix: {'; '.join(v.fix_steps)}"
            issues.append(QAIssue(round=k, source="vision_slide", slide=s.no, category=v.category, severity=v.severity,
                                  detail=detail, source_lines=", ".join(ref)))
    return issues


def vision_deck_issues(ctx: RunCtx, k: int, out_dir: Path, slides: list[Slide], template: str) -> list[QAIssue]:
    pngs = [out_dir / f"slide-{s.no}.png" for s in slides]
    issues = []
    for sheet in contact_sheets(pngs, out_dir / "sheets"):
        rep = ctx.h.call("vision_critic", template, output_type=VisionReport, images=[sheet.read_bytes()])
        for v in rep.issues:
            sl = next((s for s in slides if s.no == v.slide), slides[0])
            issues.append(QAIssue(round=k, source="vision_deck", slide=v.slide, category=v.category, severity=v.severity,
                                  detail=f"{v.issue} | fix: {'; '.join(v.fix_steps)}", source_lines=f"{sl.start}-{sl.end}"))
    return issues


def student_issues(ctx: RunCtx, k: int, slides: list[Slide], template: str) -> list[QAIssue]:
    """The student sees ONLY slide text and notes (never the paper)."""
    blob = "\n\n".join(f"## Slide {s.no}\n{body_of(s)}\n\nNOTES: {notes_of(s)}" for s in slides)
    rep = ctx.h.call("student_critic", fill(template, slides=blob), output_type=StudentReport)
    by_no = {s.no: s for s in slides}
    out = []
    for v in rep.issues:
        sl = by_no.get(v.slide)
        out.append(QAIssue(round=k, source="student", slide=v.slide, category=v.confusion, severity=v.severity,
                           detail=v.question_they_would_ask, source_lines=f"{sl.start}-{sl.end}" if sl else None))
    return out


def measurements(out_dir: Path, slides: list[Slide]) -> tuple[dict[int, set[str]], dict[int, list[dict]]]:
    """DOM rules found per slide and the element boxes per slide: the ground truth the vision critic is checked against."""
    rules, els = {}, {}
    for s in slides:
        rules[s.no] = {c["rule"] for c in json.loads((out_dir / f"slide-{s.no}.checks.json").read_text(encoding="utf-8"))}
        els[s.no] = json.loads((out_dir / f"slide-{s.no}.elements.json").read_text(encoding="utf-8")).get("elements", [])
    return rules, els


# ------------------------------------------------------------------ the loop
def summarize(k: int, issues: list[QAIssue]) -> dict:
    return {
        "round": k,
        "n_issues": len(issues),
        "n_high": sum(i.severity == "high" for i in issues),
        "by_source": dict(Counter(i.source for i in issues)),
        "by_category": dict(Counter(i.category for i in issues)),
        "issues": [i.model_dump() for i in issues],
    }


def run(ctx: RunCtx) -> None:
    measure_only = ctx.config == "oneshot"
    max_rounds = 1 if measure_only else ctx.max_rounds
    t_slide = load_prompt("vision_critic.md")
    t_deck = load_prompt("vision_critic_deck.md")
    t_student = load_prompt("student_critic.md")
    rounds: list[dict] = []
    sent: set[tuple[int, str]] = set()   # (slide, category) of vision issues already sent to the reviser
    # up to `max_rounds` critique+revise rounds, then one final verifying critique (no revision)
    for k in range(1, max_rounds + 2):
        b = render.build(ctx.run_dir)
        out_dir = ctx.p("render", f"round_{k}", ".keep").parent
        render.capture(b, out_dir)
        slides = parse_slides(ctx.text("deck/slides.md"))
        issues = automatic_issues(k, out_dir, slides)
        if not measure_only:
            raw = vision_slide_issues(ctx, k, out_dir, slides, t_slide) + vision_deck_issues(ctx, k, out_dir, slides, t_deck)
            rules, els = measurements(out_dir, slides)
            issues += triage(raw, rules, els, sent) + student_issues(ctx, k, slides, t_student)
        rounds.append(summarize(k, issues))
        shutil.copy(ctx.p("deck", "slides.md"), out_dir / "slides.md")
        ctx.h.trace.log(stage="render_loop", event="round", round=k, n_issues=len(issues), n_high=rounds[-1]["n_high"])
        ctx.save("qa.json", _qa(rounds, measure_only, done=False))
        if measure_only or rounds[-1]["n_high"] == 0 or k == max_rounds + 1:
            break
        sent |= {(i.slide, i.category) for i in issues if i.source.startswith("vision") and i.severity == "high"}
        if not revise(ctx, k, issues):
            break
    ctx.save("qa.json", _qa(rounds, measure_only, done=True))


def measure_round(ctx: RunCtx, label: str) -> None:
    """Append an automatic-checks-only round for the CURRENT deck to qa.json (used after the fact-check revised the deck)."""
    b = render.build(ctx.run_dir)
    qa = ctx.load_json("qa.json")
    k = len(qa["rounds"]) + 1
    out_dir = ctx.p("render", f"round_{k}", ".keep").parent
    render.capture(b, out_dir)
    slides = parse_slides(ctx.text("deck/slides.md"))
    r = summarize(k, automatic_issues(k, out_dir, slides))
    r["label"] = label
    r["note"] = "automatic checks only (no vision/student critic); the deck was revised after the first fact-check"
    shutil.copy(ctx.p("deck", "slides.md"), out_dir / "slides.md")
    qa["rounds"].append(r)
    qa["rounds_run"] = len(qa["rounds"])
    qa["final_high"] = r["n_high"]
    qa["final_by_category"] = r["by_category"]
    ctx.save("qa.json", qa)


def _qa(rounds: list[dict], measure_only: bool, done: bool) -> dict:
    last = rounds[-1]
    return {
        "mode": "measure_only" if measure_only else "full",
        "rounds_run": len(rounds),
        "final_high": last["n_high"],
        "final_by_category": last["by_category"],
        "finished": done,
        "rounds": rounds,
    }
