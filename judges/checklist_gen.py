"""Paper-specific checklist: binary sub-items per contribution, condition, main result, limitation and hard concept (SPEC §7.9)."""
from __future__ import annotations

from common.ctx import RunCtx
from common.schemas import Checklist

PROMPT = """Write a checklist for grading a slide deck that presents the paper below. Think step by step about the paper, then output ATOMIC binary items
(each answerable yes/no from the deck). Each item belongs to one static rubric item (`parent`):
- E1: one item per hard concept in the difficulty map ("the deck explains <concept> before using it").
- C2: one item per contribution the authors state.
- C3: one item per condition, variant, ablation or key design choice.
- C4: the headline result with its number.
- C5: one item per limitation (the authors' own and any known critique) and one for prior-work positioning.
- F1: items for the 5 most important numbers in the paper ("the deck's <thing> number matches the paper").
Use ids like E1.1, E1.2, C2.1 ... Return JSON {{"items": [{{"id": "...", "parent": "E1", "text": "..."}}]}}. Use only facts from the data below.

# Digest
{digest}

# Difficulty map
{difficulty}
"""


def run(ctx: RunCtx) -> Checklist:
    if ctx.exists("checklist.json"):
        return ctx.load("checklist.json", Checklist)
    cl = ctx.h.call("checklist", PROMPT.format(digest=ctx.text("digest.json"), difficulty=ctx.text("difficulty_map.json")),
                    output_type=Checklist)
    ctx.save("checklist.json", cl)
    return cl
