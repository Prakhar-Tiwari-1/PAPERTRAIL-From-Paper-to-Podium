"""Per-paper profile: everything the pipeline needs to know about ONE paper that cannot be read off the paper itself.

papers/<arxiv-id or pdf-name>.yaml (optional) overrides papers/default.yaml (all empty: the pipeline is paper-independent without any profile).
Nothing in a profile is required. What it can hold:
  candidate_concepts   concepts you already know are hard (the difficulty stage must still confirm them against the text)
  extra_required_slides  [{name, keywords}] slides the plan must contain besides the generic ones
  known_critiques      critiques of the paper that belong in the limitations (for example from reviewers or an award committee)
  quiz_hints           what-if directions that suit this paper
  analysis_hints       a sentence for the analyst about the data it may use
  paper_citation / cite_short   override the citation shown on the title page and in figure captions
  dataset              a released dataset the deck may draw worked examples from (see DatasetSpec)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from papertrail.paths import ROOT
PAPERS = ROOT / "papers"


@dataclass
class DatasetSpec:
    name: str
    url: str = ""                       # downloaded once to `path` if the file is missing
    path: str = ""                      # relative to the repo root (gitignored: data/...)
    description: str = ""               # one sentence for the prompts: what a record is
    id_field: str = "id"
    task_field: str = ""                # optional grouping field (for example a task name)
    text_fields: list[str] = field(default_factory=lambda: ["prompt", "question", "instruction", "query"])
    shards_field: str = ""              # optional: a list of parts of the record, shown one per turn in a worked example
    shard_text_field: str = "shard"
    example_tasks: list[str] = field(default_factory=list)   # task values to pre-fetch examples from for the difficulty prompt
    citation_prefix: str = "dataset"    # claims cite records as "dataset:<id>"


@dataclass
class Profile:
    paper_id: str = "default"
    candidate_concepts: list[str] = field(default_factory=list)
    extra_required_slides: list[dict] = field(default_factory=list)
    known_critiques: list[str] = field(default_factory=list)
    quiz_hints: list[str] = field(default_factory=list)
    analysis_hints: str = ""
    paper_citation: str = ""
    cite_short: str = ""
    dataset: DatasetSpec | None = None


def _read(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {} if path.exists() else {}


def load_profile(paper_id: str = "default", path: str | Path | None = None) -> Profile:
    """papers/<paper_id>.yaml on top of papers/default.yaml; an explicit `path` wins."""
    raw = {**_read(PAPERS / "default.yaml"), **_read(PAPERS / f"{paper_id}.yaml")}
    if path:
        raw.update(_read(Path(path)))
    ds = raw.pop("dataset", None)
    known = {k: v for k, v in raw.items() if k in Profile.__dataclass_fields__ and k != "dataset"}
    return Profile(paper_id=paper_id, dataset=DatasetSpec(**ds) if ds else None, **known)


_current = Profile()


def current() -> Profile:
    return _current


def set_current(p: Profile) -> None:
    global _current
    _current = p


def _surname(name: str) -> str:
    return name.strip().split()[-1] if name.strip() else ""


def _ingested(run_dir: Path) -> dict:
    import json

    f = Path(run_dir) / "ingested.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def cite_short(run_dir: Path) -> str:
    """Short citation for figure and table captions: the profile's, else built from the arXiv metadata ("Smith et al., 2024")."""
    if current().cite_short:
        return current().cite_short
    d = _ingested(run_dir)
    authors = d.get("authors") or []
    if not authors:
        return "the paper"
    names = [_surname(a) for a in authors]
    who = names[0] if len(names) == 1 else f"{names[0]} and {names[1]}" if len(names) == 2 else f"{names[0]} et al."
    return f"{who}, {d['year']}" if d.get("year") else who


def citation_line(run_dir: Path, configured: str = "") -> str:
    """Line under the title: the profile's, else the owner's text in deck/footer.json (unless it says "auto" or is empty), else built from the metadata."""
    if current().paper_citation:
        return current().paper_citation
    if configured and configured.strip().lower() != "auto":
        return configured
    d = _ingested(run_dir)
    authors = d.get("authors") or []
    names = [_surname(a) for a in authors]
    who = ", ".join(names[:-1]) + " and " + names[-1] if 1 < len(names) <= 3 else names[0] if len(names) == 1 else f"{names[0]} et al." if names else ""
    parts = [p for p in (who, d.get("venue"), f"arXiv:{d['paper_id']}" if d.get("source") and d.get("paper_id") and "." in str(d.get("paper_id")) else "") if p]
    return "  ·  ".join(parts)
