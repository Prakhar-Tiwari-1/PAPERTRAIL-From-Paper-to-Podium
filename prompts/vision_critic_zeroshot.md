<!-- No-taxonomy baseline used only in compare/critic_eval.py (SlideAudit Appendix B.2 minimal-instruction prompt). -->
Please examine the provided slide and identify any design flaws or deficiencies that negatively impact its effectiveness.
Consider all aspects of the slide design including layout, typography, color, visual elements, etc.

IMPORTANT:
- Never identify font-related issues (size, family, weight, color, etc.) based on missing properties in the element list. Always verify these visually from the image; the element list is incomplete.
- Do not force-find issues when there are none. If a slide is well designed and has no issues, return an empty array.

Return JSON {"issues": [{"slide": {slide_no}, "category": "<your own short flaw name>", "element_ids": [], "issue": "...", "problem_description": "...", "fix_steps": ["..."], "expected_improvement": "...", "severity": "low|high"}]}.

# Element list
{elements}
