You are grading ONE dimension of a slide deck that presents a research paper. Grade strictly and fairly, using only the evidence given. You do not know how the deck was made.

# Paper digest
{digest}

# Paper pages that the deck and the digest cite (the only text you may quote)
{paper}

# Deck (slides and notes)
{deck}

# Automatic facts
{facts}

# Checklist details (paper-specific items)
{checklist}

# Items to grade (binary checks). For EACH item decide pass (true/false):
{items}

Rules:
- Judge each item independently, using only what is in the deck text/notes and the paper pages above.
- A faithfulness pass requires a verbatim quote from the paper pages (`evidence_paper_quote`); it is checked against the paper. If you cannot quote the paper, the item fails.
- `evidence_slide` is the slide number that best shows the evidence (or null).
- If an item fails, `issue` states the specific problem and `suggested_fix` states a concrete fix. If it passes, leave both empty.
- Automatic facts (slide count, word counts, QA results) are given above; use them for items that mention them.

Return JSON {"results": [{"item_id": "...", "pass": true or false, "evidence_slide": 3 or null, "evidence_paper_quote": "..." or null, "issue": "", "suggested_fix": ""}]} with exactly one entry per item (answer the sub-checks listed under an item too).
