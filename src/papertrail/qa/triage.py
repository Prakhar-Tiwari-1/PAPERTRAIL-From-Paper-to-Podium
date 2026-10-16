"""Triage of critic findings before they reach the author (no forced issues).

The vision critic is a model looking at a picture. Its claims about things we can MEASURE (overflow, cut-off, occlusion, font size, contrast,
text volume, image scaling) are checked against the DOM measurements of the same slide. A claim the measurements do not support is demoted to
low severity (advice, never sent to the author as a must-fix). An issue that is still reported unchanged after the author tried to fix it is
marked contested and stops being retried: a loop must not chase a finding that a fix cannot remove.
"""
from __future__ import annotations

from papertrail.common.schemas import QAIssue

# vision category -> the DOM rules that would confirm it
MEASURABLE = {
    "Content Overflow/Cut-off": {"overflow", "outside_safe_area"},
    "Improper Font Sizing": {"font_below_16px"},
    "Insufficient Color Contrast for Readability": {"contrast"},
    "Improper Image Sizing": {"image_upscaled"},
    "Excessive Text Volume": {"too_many_words", "too_many_bullets"},
}
OCCLUSION = "Occluded Content"


def overlapping(elements: list[dict], min_share: float = 0.06) -> bool:
    """True if two elements overlap by more than `min_share` of the smaller one and neither contains the other (a panel containing text is design)."""
    boxes = [(e["bbox"][0], e["bbox"][1], e["bbox"][0] + e["bbox"][2], e["bbox"][1] + e["bbox"][3]) for e in elements]

    def inside(a, b):  # a inside b
        return a[0] >= b[0] - 0.005 and a[1] >= b[1] - 0.005 and a[2] <= b[2] + 0.005 and a[3] <= b[3] + 0.005

    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            ix, iy = min(a[2], b[2]) - max(a[0], b[0]), min(a[3], b[3]) - max(a[1], b[1])
            if ix <= 0 or iy <= 0 or inside(a, b) or inside(b, a):
                continue
            small = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
            if small > 0 and ix * iy / small > min_share:
                return True
    return False


def confirmed(issue: QAIssue, dom_rules: set[str], elements: list[dict]) -> bool:
    if issue.category == OCCLUSION:
        return overlapping(elements)
    rules = MEASURABLE.get(issue.category)
    return True if rules is None else bool(rules & dom_rules)


def triage(issues: list[QAIssue], dom_rules_by_slide: dict[int, set[str]], elements_by_slide: dict[int, list[dict]],
           previously_sent: set[tuple[int, str]]) -> list[QAIssue]:
    out = []
    for i in issues:
        if i.source in ("vision_slide", "vision_deck") and i.severity == "high":
            if i.source == "vision_slide" and not confirmed(i, dom_rules_by_slide.get(i.slide, set()), elements_by_slide.get(i.slide, [])):
                i = i.model_copy(update={"severity": "low", "detail": "[not confirmed by measurement] " + i.detail})
            elif (i.slide, i.category) in previously_sent:
                i = i.model_copy(update={"severity": "low", "detail": "[contested: still reported after a fix attempt] " + i.detail})
        out.append(i)
    return out
