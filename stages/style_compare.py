"""7.9b Style comparison: our final deck against the reference slides on the brief's quality bar (informational: it never edits the deck).

Also runs the near-copy guard: a slide of ours that looks like a reference at the level of coarse structure is flagged.
"""
from __future__ import annotations

import json

from common.ctx import RunCtx
from common.repair import call_validated
from common.schemas import StyleBrief, StyleComparison
from qa.contact_sheet import contact_sheets
from qa.source_map import parse_slides
from tools.references import collect, near_copies

DEFAULT_FEATURES = ["visual covers most of the slide", "amount of text per slide", "visual hierarchy of title, evidence and caption",
                    "purposeful use of colour", "consistency across slides", "legibility of figures", "flow from slide to slide"]

PROMPT = """You compare two sets of slides, from images only.
Image 1 (and 2 if present): contact sheets of REFERENCE slides the owner likes. The remaining images: contact sheets of OUR deck (numbered thumbnails).
Score both on each feature below from 1 (poor) to 5 (excellent), judging what you can see. Be fair, not generous: a 5 means no visible weakness.
Do not reward similarity to the references; reward quality on the feature.

Features:
{features}

Return JSON {{"features": [{{"feature": "...", "references": 1-5, "ours": 1-5, "note": "one short reason"}}], "verdict": "two sentences: where ours is at least as
good as the references and where it falls short", "slides_to_improve": [slide numbers of ours that clearly fall below the references]}}.
One entry per feature, in the same order."""


def run(ctx: RunCtx) -> None:
    refs, _ = collect(ctx.extra.get("refs"))
    if not refs:
        ctx.save("style_comparison.json", {"skipped": True, "reason": "no reference slides in references/slides/"})
        return
    rounds = sorted((p for p in ctx.p("render", ".keep").parent.glob("round_*") if p.is_dir()), key=lambda p: int(p.name.split("_")[1]))
    pngs = []
    for rd in reversed(rounds):
        pngs = sorted((p for p in rd.glob("slide-*.png") if p.stem.split("-")[1].isdigit()), key=lambda p: int(p.stem.split("-")[1]))
        if pngs:
            break
    if not pngs:
        ctx.save("style_comparison.json", {"skipped": True, "reason": "no rendered slides"})
        return
    brief = ctx.load("style_brief.json", StyleBrief)
    features = brief.quality_bar or DEFAULT_FEATURES
    tmp = ctx.p("render", "style_sheets", ".keep").parent
    ref_sheets = contact_sheets_from_bytes(refs, tmp / "refs")
    our_sheets = [s.read_bytes() for s in contact_sheets(pngs, tmp / "ours")[:2]]
    prompt = PROMPT.format(features="\n".join(f"- {f}" for f in features))
    cmp_ = call_validated(ctx, "style_compare", prompt, StyleComparison,
                          lambda c: [] if len(c.features) == len(features) else [f"{len(c.features)} features scored; need {len(features)}, in order"],
                          max_repairs=1, images=ref_sheets + our_sheets)
    slides = parse_slides(ctx.text("deck/slides.md"))
    ours = [(s.no, p.read_bytes()) for s, p in zip(slides, pngs)]
    copies = near_copies(ours, refs)
    out = cmp_.model_dump()
    out["near_copies"] = copies
    out["mean_references"] = round(sum(f.references for f in cmp_.features) / len(cmp_.features), 2)
    out["mean_ours"] = round(sum(f.ours for f in cmp_.features) / len(cmp_.features), 2)
    ctx.save("style_comparison.json", out)
    rows = "\n".join(f"| {f.feature} | {f.references} | {f.ours} | {f.note} |" for f in cmp_.features)
    ctx.p("style_comparison.md").write_text(
        f"# Style comparison with the reference slides\n\n| feature | references | ours | note |\n|---|---|---|---|\n{rows}\n\n"
        f"Mean: references {out['mean_references']}, ours {out['mean_ours']}.\n\n{cmp_.verdict}\n\n"
        + (f"Slides to improve: {cmp_.slides_to_improve}\n\n" if cmp_.slides_to_improve else "")
        + ("**Near-copy warning:** " + json.dumps(copies) + "\n" if copies else "Near-copy guard: no slide of ours resembles a reference slide.\n"),
        encoding="utf-8")


def contact_sheets_from_bytes(items: list[tuple[str, bytes]], out_dir) -> list[bytes]:
    """Contact sheets for in-memory images (the references)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, (_, b) in enumerate(items):
        p = out_dir / f"ref_{i + 1}.png"
        p.write_bytes(b)
        paths.append(p)
    return [s.read_bytes() for s in contact_sheets(paths, out_dir / "sheets")[:2]]
