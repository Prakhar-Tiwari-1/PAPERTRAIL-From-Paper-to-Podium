"""Budget guard (SPEC §4.1, CLAUDE.md rule 3).

Before each call: estimate worst-case cost and refuse if it would pass a cap.
After each call: record the actual cost. Per-run spend lives in runs/<ts>/cost.json;
the all-runs total is an append-only ledger at runs/_spend.jsonl.
"""
from __future__ import annotations

import json
import threading
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


class BudgetExceeded(RuntimeError):
    pass


def load_caps(path: Path | None = None) -> dict:
    return yaml.safe_load((path or ROOT / "config" / "budget.yaml").read_text(encoding="utf-8"))


def estimate_cost(in_tokens: int, max_out_tokens: int, price: tuple[float, float]) -> float:
    """Worst case: all input tokens + max_tokens of output. price = USD per 1M [in, out]."""
    return (in_tokens * price[0] + max_out_tokens * price[1]) / 1_000_000


class Budget:
    def __init__(self, run_dir: Path, caps: dict | None = None, ledger: Path | None = None):
        self.run_dir = Path(run_dir)
        self.run_id = self.run_dir.name
        self.caps = caps or load_caps()
        self.ledger = ledger or (self.run_dir.parent / "_spend.jsonl")
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.by_model: dict[str, float] = defaultdict(float)
        self.by_role: dict[str, float] = defaultdict(float)
        self.calls = 0
        self.run_spent = 0.0
        for e in self._ledger_entries():  # resume: rebuild this run's totals from the ledger so cost.json stays complete
            if e["run"] == self.run_id:
                self.run_spent += e["usd"]
                self.calls += 1
                self.by_model[e.get("model", "")] += e["usd"]
                self.by_role[e.get("role", "")] += e["usd"]

    # -- reading
    def _ledger_entries(self) -> list[dict]:
        if not self.ledger.exists():
            return []
        out = []
        for line in self.ledger.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
        return out

    def _ledger_sum(self, run_id: str | None = None) -> float:
        return sum(e["usd"] for e in self._ledger_entries() if run_id is None or e["run"] == run_id)

    @property
    def total_spent(self) -> float:
        return self._ledger_sum()

    # -- guard
    def check(self, est_usd: float) -> None:
        margin = self.caps.get("estimate_margin", 1.0)
        est = est_usd * margin
        if self.run_spent + est > self.caps["per_run_usd"]:
            raise BudgetExceeded(
                f"per-run cap ${self.caps['per_run_usd']:.2f} would be passed "
                f"(spent ${self.run_spent:.4f} + worst-case ${est:.4f})"
            )
        if self.total_spent + est > self.caps["total_usd"]:
            raise BudgetExceeded(
                f"total cap ${self.caps['total_usd']:.2f} would be passed "
                f"(spent ${self.total_spent:.4f} + worst-case ${est:.4f})"
            )

    def add(self, usd: float, *, model: str = "", role: str = "") -> None:
        with self._lock:
            self.run_spent += usd
            self.calls += 1
            self.by_model[model] += usd
            self.by_role[role] += usd
            with self.ledger.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"run": self.run_id, "usd": usd, "model": model, "role": role}) + "\n")
            self._write_cost_json()

    def _write_cost_json(self) -> None:
        (self.run_dir / "cost.json").write_text(
            json.dumps(
                {
                    "run": self.run_id,
                    "run_usd": round(self.run_spent, 6),
                    "calls": self.calls,
                    "by_model": {k: round(v, 6) for k, v in self.by_model.items()},
                    "by_role": {k: round(v, 6) for k, v in self.by_role.items()},
                    "caps": self.caps,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
