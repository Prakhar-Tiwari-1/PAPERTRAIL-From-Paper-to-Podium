from common.llm import load_models
from common.skills import all_skills, load_skill, skills_prompt

SPEC_SKILLS = {"paper-comprehension", "explanation-devices", "slide-design", "slidev-authoring", "diagram-style", "figure-replot", "speaker-notes"}


def test_all_seven_spec_skills_exist_with_frontmatter():
    skills = {s.name: s for s in all_skills()}
    assert set(skills) == SPEC_SKILLS
    assert all(s.description and s.stages and s.body for s in skills.values())


def test_every_role_skill_resolves_and_prompt_contains_it():
    roles, _ = load_models()
    for r in roles.values():
        for name in r.skills:
            assert load_skill(name).name == name
    assert "Skill: slide-design" in skills_prompt(["slide-design"])


def test_slide_design_maps_rules_to_slideaudit_and_gestalt():
    body = load_skill("slide-design").body
    for term in ("Proximity", "Similarity", "Symmetry", "Continuity", "Figure-Ground", "Common Fate", "excessive text density"):
        assert term in body
