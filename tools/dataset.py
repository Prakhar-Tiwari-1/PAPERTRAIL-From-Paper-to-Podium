"""dataset_lookup: read-only access to ONE released dataset named in the paper profile (papers/<id>.yaml, field `dataset`), SPEC §6.

Used for worked examples: real records, optionally with their parts ("shards") shown turn by turn. Without a `dataset` in the profile this module
reports `active() is None` and the pipeline works from the paper alone. The data file is downloaded once to the profile's `path` (gitignored).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import httpx

from common import profile as profile_mod
from common.profile import DatasetSpec

ROOT = Path(__file__).resolve().parent.parent


class Dataset:
    def __init__(self, spec: DatasetSpec, records: list[dict] | None = None):
        self.spec = spec
        self._records = records

    # -- loading
    @property
    def path(self) -> Path:
        return ROOT / self.spec.path

    def records(self) -> list[dict]:
        if self._records is None:
            p = self.path
            if not p.exists():
                if not self.spec.url:
                    raise FileNotFoundError(f"dataset file {p} is missing and the profile has no url")
                p.parent.mkdir(parents=True, exist_ok=True)
                r = httpx.get(self.spec.url, timeout=120, follow_redirects=True)
                r.raise_for_status()
                p.write_bytes(r.content)
            data = json.loads(p.read_text(encoding="utf-8"))
            self._records = data if isinstance(data, list) else next(v for v in data.values() if isinstance(v, list))
        return self._records

    # -- access
    def rid(self, rec: dict) -> str:
        return str(rec.get(self.spec.id_field, ""))

    def ids(self) -> set[str]:
        return {self.rid(r) for r in self.records()}

    def text_of(self, rec: dict) -> str:
        for k in self.spec.text_fields:
            if isinstance(rec.get(k), str) and rec[k].strip():
                return rec[k].strip()
        return ""

    def parts(self, rec: dict) -> list[str]:
        f = self.spec.shards_field
        return [str(p.get(self.spec.shard_text_field, "")) if isinstance(p, dict) else str(p) for p in (rec.get(f) or [])] if f else []

    def get(self, rid: str) -> dict | None:
        return next((r for r in self.records() if self.rid(r) == rid), None)

    def full_text(self, rid: str) -> str:
        """Everything a claim about this record can be checked against: its text and every part."""
        rec = self.get(rid)
        return "" if rec is None else " ".join([self.text_of(rec)] + self.parts(rec))

    def lookup(self, task: str | None = None, n: int = 3, filter: str | None = None, max_chars: int = 400) -> list[dict[str, Any]]:
        out = []
        for rec in self.records():
            if task and self.spec.task_field and rec.get(self.spec.task_field) != task:
                continue
            text = self.text_of(rec)
            if filter and filter.lower() not in (self.rid(rec) + " " + text).lower():
                continue
            parts = self.parts(rec)
            out.append({"id": self.rid(rec), "task": rec.get(self.spec.task_field, "") if self.spec.task_field else "", "instruction": text[:max_chars],
                        "n_parts": len(parts), "parts": [{"n": i + 1, "text": p[:220]} for i, p in enumerate(parts)]})
            if len(out) >= max(1, min(n, 10)):
                break
        return out

    def tasks(self) -> list[str]:
        f = self.spec.task_field
        return sorted({str(r.get(f)) for r in self.records() if r.get(f)}) if f else []


_cache: dict[str, Dataset] = {}


def active() -> Dataset | None:
    """The dataset of the current paper profile, or None."""
    spec = profile_mod.current().dataset
    if spec is None:
        return None
    key = f"{spec.name}:{spec.path}"
    if key not in _cache:
        _cache[key] = Dataset(spec)
    return _cache[key]


def tool() -> Callable | None:
    """The PydanticAI tool `dataset_lookup` for the current profile, or None when the paper has no dataset."""
    ds = active()
    if ds is None:
        return None
    tasks = ", ".join(ds.tasks()) or "none"

    def dataset_lookup(task: str = "", n: int = 2, filter: str = "") -> str:
        """Look up real records of the released dataset (and their parts, one per turn). Returns JSON: [{id, task, instruction, n_parts, parts[]}].
        Args: task: optional group, one of the groups listed in the description; n: how many records (max 10); filter: optional substring of the id or text."""
        return json.dumps(ds.lookup(task or None, n, filter or None), ensure_ascii=False, indent=1)

    dataset_lookup.__doc__ = (dataset_lookup.__doc__ or "") + f" Groups: {tasks}. Each record: {ds.spec.description}"
    return dataset_lookup
