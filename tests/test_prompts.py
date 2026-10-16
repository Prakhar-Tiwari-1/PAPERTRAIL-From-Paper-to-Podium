from papertrail.tools.prompt_audit import LIMITS, audit


def test_every_prompt_and_skill_is_long_enough_and_not_too_long():
    bad = [r for r in audit() if not r["ok"]]
    assert bad == [], [(r["kind"], r["name"], r["words"], LIMITS[r["kind"]]) for r in bad]


def test_author_context_is_compact():
    """The author's own instructions (skills + template) stay under 2,300 words; the data blocks are compacted separately."""
    rows = {(r["kind"], r["name"]): r["words"] for r in audit()}
    assert rows[("role_skills", "author")] + rows[("stage_prompt", "papertrail.stages.author.PROMPT")] < 2300
