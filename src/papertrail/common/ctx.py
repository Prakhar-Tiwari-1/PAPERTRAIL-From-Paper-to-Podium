"""Run context passed to every stage: `run(ctx)` (CLAUDE.md: each stage exposes one run entry point)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from papertrail.common.llm import Harness

T = TypeVar("T", bound=BaseModel)
from papertrail.paths import ROOT


@dataclass
class RunCtx:
    run_dir: Path
    paper: str                      # arXiv ID or path to a PDF
    config: str                     # "full" | "oneshot"
    h: Harness
    dev: bool = False
    max_rounds: int = 3
    extra: dict[str, Any] = field(default_factory=dict)

    # -- paths
    def p(self, *parts: str) -> Path:
        path = self.run_dir.joinpath(*parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    # -- typed json io (stage outputs are validated against schemas, SPEC §7)
    def save(self, name: str, obj: BaseModel | dict | list) -> Path:
        path = self.p(name)
        if isinstance(obj, BaseModel):
            path.write_text(obj.model_dump_json(indent=2, by_alias=False), encoding="utf-8")
        else:
            path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def load(self, name: str, model: type[T]) -> T:
        return model.model_validate_json(self.p(name).read_text(encoding="utf-8"))

    def load_json(self, name: str) -> Any:
        return json.loads(self.p(name).read_text(encoding="utf-8"))

    def exists(self, name: str) -> bool:
        return self.run_dir.joinpath(name).exists()

    def text(self, name: str) -> str:
        return self.p(name).read_text(encoding="utf-8")


def compact_json(obj, drop: tuple[str, ...] = ()) -> str:
    """Minified JSON for prompts (no indentation, no spaces); optionally drop fields the receiving model does not need."""
    import json as _json

    def walk(o):
        if isinstance(o, dict):
            return {k: walk(v) for k, v in o.items() if k not in drop}
        if isinstance(o, list):
            return [walk(v) for v in o]
        return o

    return _json.dumps(walk(obj), ensure_ascii=False, separators=(",", ":"))
