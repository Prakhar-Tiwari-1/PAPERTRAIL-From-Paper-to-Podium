"""7.9 Judge: checklist generation (paper-specific) + scoring by a different vendor than the author.

Runs BEFORE any human edit. The judge's feedback reaches the deck only through the human step (7.10).
Optional second judge (a third vendor): set env PAPERTRAIL_SECOND_JUDGE=1; agreement is written into judge_report.json.
"""
from __future__ import annotations

import os

from papertrail.common.ctx import RunCtx
from papertrail.common.llm import check_vendor_rules, vendor
from papertrail.judges import checklist_gen, score


def run(ctx: RunCtx) -> None:
    # The Tools & Workflow slide is generated from the real run (diagram, models, numbers). Do it BEFORE judging so the judge sees the
    # slide that will be presented, not the author's guess. Export refreshes only the numbers; nothing else changes the deck after this.
    if ctx.config == "full" and ctx.exists("deck/slides.md") and ctx.exists("qa.json"):
        from papertrail.report import workflow_slide

        workflow_slide.patch(ctx.run_dir)
    if vendor(ctx.h.slug_for("author")) == vendor(ctx.h.slug_for("judge")):
        raise RuntimeError("judge and author share a vendor; fix config/models.yaml (SPEC §5.1 rules)")
    # oneshot runs reuse the full run's checklist.json (copied in by compare/run_compare.py) so both decks face the same items
    checklist = checklist_gen.run(ctx) if (ctx.exists("checklist.json") or ctx.exists("difficulty_map.json")) else None
    report = score.score(ctx, "judge", repeats=2, checklist=checklist)
    if os.getenv("PAPERTRAIL_SECOND_JUDGE") == "1":
        second = score.score(ctx, "judge_second", repeats=1, checklist=checklist, out_name="judge_report_second.json")
        ids = [i["id"] for i in report.items]
        s_by = {i["id"]: i["pass"] for i in second.items}
        agree = sum(1 for i in report.items if s_by.get(i["id"]) == i["pass"])
        ctx.save("judge_agreement.json", {"items": len(ids), "agree": agree, "rate": round(agree / max(len(ids), 1), 3),
                                          "primary_total": report.total, "second_total": second.total})
