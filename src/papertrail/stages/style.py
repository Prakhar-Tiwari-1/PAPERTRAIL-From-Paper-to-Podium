"""7.5c Style study: look at the reference slides the owner likes and distil a style brief (principles and a checkable quality bar).

No references -> an empty brief and the pipeline runs as before. The brief goes to the author and the reviser as design guidance. It never carries
a reference's text, images or branding: only transferable moves. The goal is a deck that matches or beats the references, not a copy.
"""
from __future__ import annotations

from papertrail.common.ctx import RunCtx
from papertrail.common.repair import call_validated
from papertrail.common.schemas import StyleBrief
from papertrail.tools.references import collect

PROMPT = """You study example slides that the owner likes, to help a different talk (an academic paper presentation) reach the same level of quality.
The images are: {labels}.

For each image describe (1) the layout pattern, (2) what carries the message visually, (3) up to three specific design moves that make it effective, and
(4) what is specific to that deck and must NOT be reproduced (its text, logos, brand colours, photos). Then distil:
- `principles`: 6 to 10 concrete, transferable rules a slide author can follow (for example "one large visual covers at least half the slide and the title
  states its conclusion", "numbers shown as one oversized figure with a one-line caption", "three-step process drawn as a left-to-right flow, not as bullets").
  Describe moves, not look-alike instructions: no "copy the blue header".
- `quality_bar`: 5 to 8 features that can be checked on a finished slide (visual coverage of the slide, text amount, hierarchy, colour use, consistency,
  figure legibility, narrative flow from slide to slide). Each is a short phrase.
Keep it specific to what you see; do not invent features the images do not show. Plain wording."""


def run(ctx: RunCtx) -> None:
    refs, notes = collect(ctx.extra.get("refs"))
    if notes:
        ctx.h.trace.log(stage="style", event="reference_notes", notes=notes)
    if not refs:
        ctx.save("style_brief.json", StyleBrief(examples=[], principles=[], quality_bar=[]))
        ctx.h.trace.log(stage="style", event="no_references", note="put example slides in references/slides/ (png, jpg, pdf) to use this feature")
        return
    labels = "; ".join(f"image {i}: {name}" for i, (name, _) in enumerate(refs, start=1))

    def validate(b: StyleBrief) -> list[str]:
        errs = []
        if not 6 <= len(b.principles) <= 10:
            errs.append(f"{len(b.principles)} principles; need 6 to 10")
        if not 5 <= len(b.quality_bar) <= 8:
            errs.append(f"{len(b.quality_bar)} quality-bar features; need 5 to 8")
        if len(b.examples) != len(refs):
            errs.append(f"{len(b.examples)} example entries for {len(refs)} images; describe every image once, in order")
        return errs

    brief = call_validated(ctx, "style", PROMPT.format(labels=labels), StyleBrief, validate, max_repairs=2, images=[b for _, b in refs])
    ctx.save("style_brief.json", brief)
