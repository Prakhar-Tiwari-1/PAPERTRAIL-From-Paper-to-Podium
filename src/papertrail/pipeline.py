"""papertrail pipeline: a plain state machine over stage modules (SPEC §4).

    papertrail --config full --paper 2505.06120 [--dev] [--from-stage N] [--only STAGE] [--run-dir DIR]

Each stage reads and writes files in runs/<ts>/, can run alone (--only) and can resume (--from-stage).
"""
from __future__ import annotations

import argparse
import importlib
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
HARNESS_FACTORY = None  # tests set this to inject a fake-model Harness

# (name, module, produces) in execution order. `produces` is the file whose presence/validity marks it done.
STAGES = [
    ("ingest", "papertrail.stages.ingest", "paper.md"),
    ("digest", "papertrail.stages.digest", "digest.json"),
    ("difficulty", "papertrail.stages.difficulty", "difficulty_map.json"),
    ("prior_work", "papertrail.stages.prior_work", "prior_work.json"),
    ("plan", "papertrail.stages.plan", "plan.json"),
    ("analyze", "papertrail.stages.analyze", "artifacts/analysis_notes.md"),
    ("quiz", "papertrail.stages.quiz", "quiz.json"),
    ("style", "papertrail.stages.style", "style_brief.json"),
    ("author", "papertrail.stages.author", "deck/slides.md"),
    ("render_loop", "papertrail.stages.render_loop", "qa.json"),
    ("factcheck", "papertrail.stages.factcheck", "factcheck.json"),
    ("judge", "papertrail.stages.judge", "judge_report.json"),
    ("style_compare", "papertrail.stages.style_compare", "style_comparison.json"),
    ("export", "papertrail.stages.export", "final/slides.pdf"),
]
ONESHOT_STAGES = [
    ("ingest", "papertrail.stages.ingest", "paper.md"),
    ("oneshot", "papertrail.stages.oneshot", "deck/slides.md"),
    ("render_loop", "papertrail.stages.render_loop", "qa.json"),
    ("judge", "papertrail.stages.judge", "judge_report.json"),
]


def stage_list(config: str) -> list[tuple[str, str, str]]:
    if config == "oneshot":
        return ONESHOT_STAGES
    if config == "full":
        return STAGES
    raise SystemExit(f"unknown --config {config!r} (use full or oneshot)")


def select_stages(config: str, from_stage: int | None, only: str | None) -> list[tuple[str, str, str]]:
    stages = stage_list(config)
    names = [s[0] for s in stages]
    if only:
        if only not in names:
            raise SystemExit(f"--only {only!r} is not a stage of config {config!r}: {names}")
        return [stages[names.index(only)]]
    if from_stage is not None:
        if not 0 <= from_stage < len(stages):
            raise SystemExit(f"--from-stage must be 0..{len(stages) - 1} (0 = {names[0]})")
        return stages[from_stage:]
    return stages


def latest_run() -> Path | None:
    if not RUNS.exists():
        return None
    runs = sorted(p for p in RUNS.iterdir() if p.is_dir() and not p.name.startswith("_"))
    return runs[-1] if runs else None


def make_ctx(args, run_dir: Path):
    from papertrail.common.ctx import RunCtx
    from papertrail.common.llm import Harness

    h = (HARNESS_FACTORY or Harness)(run_dir, dev=args.dev)
    return RunCtx(run_dir=run_dir, paper=args.paper, config=args.config, h=h, dev=args.dev)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="papertrail", description=__doc__)
    ap.add_argument("--config", choices=["full", "oneshot"], default="full")
    ap.add_argument("--paper", required=True, help="arXiv ID (e.g. 2505.06120) or path to a PDF")
    ap.add_argument("--dev", action="store_true", help="use dev_model (cheap/free) for every role")
    ap.add_argument("--from-stage", type=int, default=None, help="index of the first stage to run (needs an existing run)")
    ap.add_argument("--only", default=None, help="run a single stage by name (uses the latest run unless --run-dir)")
    ap.add_argument("--run-dir", default=None, help="reuse this run directory (resume)")
    ap.add_argument("--profile", default=None, help="paper profile file (default: papers/<arxiv-id>.yaml if it exists); see papers/default.yaml")
    ap.add_argument("--refs", default=None, help="folder with example slides you like (default: references/slides); see references/README.md")
    ap.add_argument("--rounds", type=int, default=3, help="critique+revise rounds in the render loop; stops early at zero high-severity issues (a final verifying critique always follows)")
    args = ap.parse_args(argv)

    load_dotenv(ROOT / ".env")
    stages = select_stages(args.config, args.from_stage, args.only)

    if args.run_dir:
        run_dir = Path(args.run_dir)
    elif args.only or args.from_stage:
        run_dir = latest_run()
        if run_dir is None:
            raise SystemExit("no previous run to resume; run the full pipeline first")
    else:
        run_dir = RUNS / datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    # Paper profile (optional, papers/<id>.yaml): everything specific to this paper. Without one the pipeline is fully generic.
    from papertrail.common import profile as profile_mod

    paper_id = args.paper.strip() if re.match(r"^\d{4}\.\d{4,5}(v\d+)?$", args.paper.strip()) else Path(args.paper).stem
    profile_mod.set_current(profile_mod.load_profile(re.sub(r"v\d+$", "", paper_id), args.profile))

    ctx = make_ctx(args, run_dir)
    ctx.max_rounds = args.rounds
    ctx.extra["refs"] = args.refs
    p = profile_mod.current()
    print(f"run dir: {run_dir}  config={args.config} dev={args.dev}  profile={p.paper_id}"
          + (f" (dataset: {p.dataset.name})" if p.dataset else " (no dataset)"))

    for name, module, produces in stages:
        ctx.h.stage = name
        t0 = time.time()
        print(f"[{name}] ...", flush=True)
        ctx.h.trace.log(stage=name, event="stage_start")
        try:
            importlib.import_module(module).run(ctx)
        except Exception as e:  # keep partial outputs; the run is resumable with --from-stage
            ctx.h.trace.log(stage=name, event="stage_error", error=repr(e)[:500])
            print(f"[{name}] FAILED: {e}", file=sys.stderr)
            print(f"resume with: papertrail --config {args.config} --paper {args.paper} "
                  f"--run-dir {run_dir} --only {name}", file=sys.stderr)
            return 1
        dt = time.time() - t0
        ctx.h.trace.log(stage=name, event="stage_end", seconds=round(dt, 2), output=produces)
        print(f"[{name}] done in {dt:.1f}s  (spent ${ctx.h.budget.run_spent:.4f})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
