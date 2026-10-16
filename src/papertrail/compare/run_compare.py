"""Pipeline comparison (SPEC §11): `--config oneshot` vs `--config full`, same judge, scored BEFORE human edits.

    python -m papertrail.compare.run_compare --full runs/<ts> [--paper 2505.06120] [--dev]

Runs the one-shot baseline into runs/<ts>-oneshot (reusing the full run's paper, digest and checklist so both decks face the same
checklist), then writes compare/results.json and compare/summary.md. Limitation, stated in the summary: an LLM judging LLM output, n = 1 deck per config.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from dotenv import load_dotenv

from papertrail.report import trace_page

from papertrail.paths import ROOT, results_dir
REUSE = ["paper.md", "tables.json", "refs.json", "ingested.json", "digest.json", "difficulty_map.json", "checklist.json", "source.pdf"]
OVERFLOW_CATS = {"overflow", "outside_safe_area", "Content Overflow/Cut-off"}


def summarize(run_dir: Path) -> dict:
    jr = json.loads((run_dir / "judge_report.json").read_text(encoding="utf-8"))
    qa = json.loads((run_dir / "qa.json").read_text(encoding="utf-8"))
    t = trace_page.totals(run_dir)
    last = qa["rounds"][-1]["issues"]
    first = qa["rounds"][0]["issues"]
    return {
        "run": run_dir.name,
        "total": jr["total"],
        "by_dimension": jr["scores"],
        "hard_fail": jr["hard_fail"],
        "f_failures": [i["id"] for i in jr["items"] if i["id"] in ("F1", "F2") and not i["pass"]],
        "overflow_issues_final": sum(1 for i in last if i["category"] in OVERFLOW_CATS),
        "high_issues_final": qa["final_high"],
        "issues_round_1": len(first),
        "issues_final": len(last),
        "rounds": qa["rounds_run"],
        "cost_usd": t["cost_usd"],
        "seconds": t["seconds"],
        "model_calls": t["calls"],
        "judge_disagreements": jr["disagreements"],
    }


def compare(full_dir: Path, oneshot_dir: Path) -> dict:
    res = {"full": summarize(full_dir), "oneshot": summarize(oneshot_dir)}
    agree = full_dir / "judge_agreement.json"
    if agree.exists():
        res["second_judge_agreement_full"] = json.loads(agree.read_text(encoding="utf-8"))
    res["limitations"] = "an LLM judging LLM output; n = 1 deck per config; the judge is a different vendor from the author but not human"
    return res


def write_summary(res: dict) -> None:
    f, o = res["full"], res["oneshot"]
    dims = list(f["by_dimension"])
    rows = [("Judge total (/100)", f"{o['total']:.0f}", f"{f['total']:.0f}")]
    rows += [(f"  {d}", f"{o['by_dimension'][d]:.0f}", f"{f['by_dimension'][d]:.0f}") for d in dims]
    rows += [("F1/F2 failures", ", ".join(o["f_failures"]) or "none", ", ".join(f["f_failures"]) or "none"),
             ("Overflow issues (final)", o["overflow_issues_final"], f["overflow_issues_final"]),
             ("High QA issues (final)", o["high_issues_final"], f["high_issues_final"]),
             ("Critic issues, round 1 -> final", f"{o['issues_round_1']} -> {o['issues_final']}", f"{f['issues_round_1']} -> {f['issues_final']}"),
             ("Cost (USD)", f"{o['cost_usd']:.2f}", f"{f['cost_usd']:.2f}"),
             ("Wall clock (s)", o["seconds"], f["seconds"]), ("Model calls", o["model_calls"], f["model_calls"])]
    body = "\n".join(f"| {a} | {b} | {c} |" for a, b, c in rows)
    (results_dir("compare", ROOT) / "summary.md").write_text(
        f"# One-shot vs. full pipeline\n\n| | one-shot | full |\n|---|---|---|\n{body}\n\nLimitations: {res['limitations']}.\n", encoding="utf-8")
    (results_dir("compare", ROOT) / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", required=True, help="a finished `--config full` run directory (with judge_report.json)")
    ap.add_argument("--paper", default="2505.06120")
    ap.add_argument("--dev", action="store_true")
    ap.add_argument("--oneshot-dir", default=None, help="reuse an existing oneshot run instead of running it")
    a = ap.parse_args()
    load_dotenv(ROOT / ".env")
    full = Path(a.full)
    one = Path(a.oneshot_dir) if a.oneshot_dir else full.with_name(full.name + "-oneshot")
    if not (one / "judge_report.json").exists():
        import pipeline

        one.mkdir(parents=True, exist_ok=True)
        for name in REUSE:
            if (full / name).exists():
                shutil.copy(full / name, one / name)
        if (full / "figures").exists() and not (one / "figures").exists():
            shutil.copytree(full / "figures", one / "figures")
        argv = ["--config", "oneshot", "--paper", a.paper, "--run-dir", str(one), "--from-stage", "1"] + (["--dev"] if a.dev else [])
        if pipeline.main(argv) != 0:
            return 1
    res = compare(full, one)
    write_summary(res)
    print((ROOT / "results" / "compare" / "summary.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
