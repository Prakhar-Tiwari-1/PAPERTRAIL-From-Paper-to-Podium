"""Append-only trace of every LLM call and stage event -> runs/<ts>/trace.jsonl (SPEC §4.1)."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path


class Trace:
    def __init__(self, run_dir: Path):
        self.path = Path(run_dir) / "trace.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def log(self, **event) -> None:
        event.setdefault("ts", time.time())
        with self._lock, self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")

    def read(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]
