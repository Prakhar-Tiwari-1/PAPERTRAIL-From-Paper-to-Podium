"""7.10 Export: final/slides.pdf (presenting copy), final/slides-editable.pptx (backup), trace.html, pipeline.mmd.

Gate: factcheck.json must have no unmatched numbers (waive them in waivers.json with a reason). The workflow slide is regenerated from the
final run totals first. human_review.json is created from the judge's failed items for the human step; accepted fixes go back through the author
(preferred) or are applied by hand as `manual:` commits.
"""
from __future__ import annotations

import json
import shutil

from common.ctx import RunCtx
from report import trace_page, workflow_slide
from stages import factcheck
from tools import render


def human_review_template(ctx: RunCtx) -> None:
    if ctx.exists("human_review.json") or not ctx.exists("judge_report.json"):
        return
    jr = ctx.load_json("judge_report.json")
    items = [{"item_id": i["id"], "issue": i["issue"], "suggested_fix": i["suggested_fix"], "decision": None, "note": ""}
             for i in jr["items"] if not i["pass"]]
    ctx.save("human_review.json", {"decision_values": ["accept", "reject", "modify"], "items": items})


def run(ctx: RunCtx) -> None:
    # 1. regenerate the Tools & Workflow slide from the final run totals (idempotent), 2. re-check every number in the final deck, 3. gate.
    workflow_slide.patch(ctx.run_dir)
    ctx.h.stage = "factcheck"  # attribute the re-check's model calls to the fact-check stage in the trace
    factcheck.run(ctx, max_revisions=0)  # check only: the deck was judged already, so export must never rewrite it
    ctx.h.stage = "export"
    fc = ctx.load_json("factcheck.json")
    if fc["unmatched"]:
        raise RuntimeError(f"{len(fc['unmatched'])} unmatched numbers block export; fix the deck or waive them in waivers.json: "
                           + ", ".join(f"slide {u['slide']}: {u['value']}" for u in fc["unmatched"][:10]))
    b = render.build(ctx.run_dir)
    final = ctx.p("final", ".keep").parent
    render.export(b, "pdf", final / "slides.pdf")
    try:
        render.export(b, "pptx", final / "slides-editable.pptx")
    except Exception as e:  # pptx is only a backup (SPEC §16)
        ctx.h.trace.log(stage="export", event="pptx_failed", error=str(e)[:300])
    shutil.copy(ctx.p("deck", "slides.md"), final / "slides.md")
    from report import speaker_script

    speaker_script.write(ctx.run_dir, final)  # the notes as one readable document, for rehearsing
    human_review_template(ctx)
    trace_page.write(ctx.run_dir, final)
    trace_page.write(ctx.run_dir)
