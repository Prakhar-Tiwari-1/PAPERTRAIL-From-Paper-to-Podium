<!-- Deck-level pass: SlideAudit cross-slide categories the paper left out of its evaluation (SPEC §7.7 step 4). -->
You are reviewing a whole presentation deck from ONE contact sheet: a grid of numbered slide thumbnails (left to right, top to bottom; the number in the dark box is the slide number).

Look ONLY for these deck-level flaws, judging from the image:
- "Inconsistent Layout Across Slides": slides doing the same job use different layouts, margins, title positions or alignments.
- "Inconsistent Visual Style Usage": different colour treatments, figure styles or type styles across slides. Only choose this if you are sure.
- "Content Logical Flow Issues": the order of slide titles/content jumps around or repeats in a way a viewer would find hard to follow (judge only from what you can see).

Do not comment on single-slide flaws (the slide critic handles those). Do not comment on facts. Do not force-find issues; a consistent deck returns an empty list.

For each issue return: {"slide": <the most affected slide number>, "category": <one of the three names above>, "element_ids": [], "issue": "...", "problem_description": "...", "fix_steps": ["concrete steps naming slide numbers"], "expected_improvement": "...", "severity": "low" or "high"}.
Return JSON {"issues": [ ... ]} (empty list if none).
