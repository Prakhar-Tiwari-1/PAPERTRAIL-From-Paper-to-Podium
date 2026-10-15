"""Load skills/<name>/SKILL.md (frontmatter: name, description, stages) into a system prompt (SPEC §8)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


@dataclass
class Skill:
    name: str
    description: str
    stages: list[str]
    body: str


def _parse(path: Path) -> Skill:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{path}: missing frontmatter")
    _, fm, body = text.split("---", 2)
    meta = yaml.safe_load(fm)
    for key in ("name", "description", "stages"):
        if key not in meta:
            raise ValueError(f"{path}: frontmatter lacks {key!r}")
    return Skill(meta["name"], meta["description"], list(meta["stages"]), body.strip())


def load_skill(name: str, skills_dir: Path | None = None) -> Skill:
    path = (skills_dir or SKILLS_DIR) / name / "SKILL.md"
    if not path.exists():
        raise FileNotFoundError(f"skill {name!r} not found at {path}")
    return _parse(path)


def skills_prompt(names: list[str], skills_dir: Path | None = None) -> str:
    """Concatenate the named skills into a system-prompt section."""
    if not names:
        return ""
    parts = []
    for n in names:
        s = load_skill(n, skills_dir)
        parts.append(f"## Skill: {s.name}\n{s.description}\n\n{s.body}")
    return "# Skills\n\n" + "\n\n".join(parts)


def all_skills(skills_dir: Path | None = None) -> list[Skill]:
    d = skills_dir or SKILLS_DIR
    return [_parse(p) for p in sorted(d.glob("*/SKILL.md"))]
