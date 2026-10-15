"""Prompt and skill length audit: every instruction must be long enough to do its job and short enough not to get lost in the context.

    python -m tools.prompt_audit          # table of words per skill, prompt file, stage prompt and per-role system prompt

Limits (checked by tests/test_prompts.py): a skill 60-520 words, a prompt file 60-950 words (the vision-critic taxonomy is the long one), a stage
prompt template 50-700 words, and the skills a role loads at most 1,500 words together. Data pasted into prompts is compacted separately
(common/ctx.compact_json, tables as small excerpts, paper_llm.md).
"""
from __future__ import annotations

import importlib
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
STAGE_PROMPTS = [("stages.digest", "PROMPT"), ("stages.difficulty", "PROMPT"), ("stages.prior_work", "PROMPT"), ("stages.plan", "PROMPT"),
                 ("stages.analyze", "PROMPT"), ("stages.author", "PROMPT"), ("stages.revise", "PROMPT"), ("stages.quiz", "PROMPT"),
                 ("stages.style", "PROMPT"), ("stages.style_compare", "PROMPT"), ("stages.factcheck", "PROMPT"), ("judges.checklist_gen", "PROMPT")]
LIMITS = {"skill": (60, 520), "prompt_file": (60, 950), "stage_prompt": (50, 700), "role_skills": (0, 1500)}


def words(s: str) -> int:
    return len(re.findall(r"\S+", s))


def audit() -> list[dict]:
    rows = []
    for f in sorted((ROOT / "skills").glob("*/SKILL.md")):
        rows.append({"kind": "skill", "name": f.parent.name, "words": words(f.read_text(encoding="utf-8"))})
    for f in sorted((ROOT / "prompts").glob("*.md")):
        rows.append({"kind": "prompt_file", "name": f.name, "words": words(f.read_text(encoding="utf-8"))})
    for mod, attr in STAGE_PROMPTS:
        rows.append({"kind": "stage_prompt", "name": f"{mod}.{attr}", "words": words(getattr(importlib.import_module(mod), attr))})
    roles = yaml.safe_load((ROOT / "config" / "models.yaml").read_text(encoding="utf-8"))["roles"]
    sk = {r["name"]: r["words"] for r in rows if r["kind"] == "skill"}
    for name, cfg in roles.items():
        rows.append({"kind": "role_skills", "name": name, "words": sum(sk[s] for s in cfg.get("skills", []))})
    for r in rows:
        lo, hi = LIMITS[r["kind"]]
        r["ok"] = (lo <= r["words"] <= hi) or (r["kind"] == "role_skills" and r["words"] <= hi)
    return rows


if __name__ == "__main__":
    for r in audit():
        print(f"{r['kind']:13s} {r['name']:34s} {r['words']:5d} words  {'ok' if r['ok'] else 'OUT OF RANGE ' + str(LIMITS[r['kind']])}")
