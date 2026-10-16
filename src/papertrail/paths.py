"""Where things live. One place, so no module computes its own location.

The code is the package in `src/papertrail/`. Everything it reads and writes sits at the repository root: `config/`, `prompts/`, `skills/`,
`deck/` (the Slidev project), `media/`, `papers/`, `references/`, `data/`, `runs/` and `results/`.

Set `PAPERTRAIL_ROOT` to run the package against another working directory (for example after a plain `pip install`).
"""
from __future__ import annotations

import os
from pathlib import Path

PKG = Path(__file__).resolve().parent                     # src/papertrail: the code and the JS helpers that ship with it
ROOT = Path(os.environ["PAPERTRAIL_ROOT"]).resolve() if os.environ.get("PAPERTRAIL_ROOT") else PKG.parents[1]

CONFIG = ROOT / "config"          # models.yaml, budget.yaml, rubric.yaml, slideaudit_sample.json
PROMPTS = ROOT / "prompts"        # single-role prompts
SKILLS = ROOT / "skills"          # skills/<name>/SKILL.md, injected into stage prompts
DECK = ROOT / "deck"              # the Slidev project and theme
MEDIA = ROOT / "media"            # images and their credits
PAPERS = ROOT / "papers"          # per-paper profiles (papers/<arxiv-id>.yaml); the PDFs stay local
REFERENCES = ROOT / "references"  # example slides the owner likes (local)
DATA = ROOT / "data"              # external datasets (local)
RUNS = ROOT / "runs"              # every run's working files (local)
RESULTS = ROOT / "results"        # archived outputs and costs (tracked)
CACHE = ROOT / ".cache"           # LLM response cache and tool caches (local)


def results_dir(name: str, root: Path | None = None) -> Path:
    """<root>/results/<name>/, created on first use. For writing only (reading uses the path directly so that it creates nothing).
    Modules pass their own ROOT, so a test that points ROOT at a temp folder never writes into the real results/."""
    d = (root or ROOT) / "results" / name
    d.mkdir(parents=True, exist_ok=True)
    return d
