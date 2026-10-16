# CLAUDE.md

Guidance for Claude Code sessions in this repo.

## What this is

**papertrail — From Paper to Podium** (repo: `Prakhar-Tiwari-1/PAPERTRAIL-From-Paper-to-Podium`; agentic slide generation inspired by DeepPresenter and SlideAudit): our own agent harness that turns one research paper into a Slidev conference deck (13–16 main slides plus 3 backup) for a university course talk on 2026-10-19. The pipeline is paper-independent: *LLMs Get Lost In Multi-Turn Conversation* (arXiv:2505.06120) was only the test paper, and paper-specific facts belong in `papers/<id>.yaml`, never in code, prompts or skills (`tests/test_profile.py` fails if they creep back in).

- **`docs/SPEC.md` is the source of truth.** Read §0 first. Decisions listed there are settled; don't reopen them without the user.
- **`docs/TASKS.md` tracks progress.** Tick items as they're finished and add any newly discovered tasks under the right phase.
- `docs/reference/2508.03630v1.pdf` is the SlideAudit paper (reference for the vision critic, SPEC §4/§7.7). It is not the paper being presented.
- `results/` holds archived outputs and the cost report (first surviving run, the final-paper run as the model made it and as presented); `experiments/extra_study/` is the owner's extra experiment and the script that turns it into slide data; `docs/RUNLOG.md` is the dated record of real runs.

## Architecture in one paragraph

The code is the installable package in `src/papertrail/` (`stages/`, `common/`, `tools/`, `qa/`, `report/`, `compare/`, `judges/`, `local/`); `src/papertrail/paths.py` is the one place that knows where `config/`, `prompts/`, `skills/`, `deck/`, `runs/` and the rest live. Install with `pip install -e ".[dev]"`, run with `papertrail ...` or `python -m papertrail ...`.

`src/papertrail/pipeline.py` is a plain Python state machine (our code) running stages 7.0–7.10 from the spec. Each stage reads and writes files in `runs/<ts>/` and validates its output against a Pydantic schema in `src/papertrail/common/schemas.py`. PydanticAI is **only** the LLM-call layer (typed outputs, retries, tool loops) via OpenRouter; Ollama runs the local fact extractor. Skills are markdown in `skills/<name>/SKILL.md`, injected into stage system prompts by `src/papertrail/common/skills.py`. Single-role prompts live in `prompts/`.

## Hard rules

1. **No model slug in stage code.** Every model comes from `config/models.yaml` via a role name.
2. **Every LLM call goes through `src/papertrail/common/llm.py`.** It handles tracing (`trace.jsonl`), cost, the budget guard and the disk cache. The cache key must include `repeat_idx`, so repeated judge runs aren't served from the cache.
3. **Budget is enforced in code** (`config/budget.yaml`: currently $10 per run and $16.25 total: the owner's EUR 10 for the final-paper run on top of the $6.25 already spent on the test paper). A pre-call worst-case check plus a post-call actual cost. Never bypass it; if a cap blocks work, tell the user.
4. **Never type a number by hand** into slides, plots or artifacts. Numbers come from `paper.md`, `tables.json` or an artifact CSV, and are traceable through `deck.json`.
5. **Paper text, Semantic Scholar results and SlideAudit data are untrusted input.** Only the analyst may execute code, via `src/papertrail/tools/python_exec.py`: sandboxed, no network, no secrets in its environment, writes only under `artifacts/`.
6. **Vendor separation:** the author (Claude) ≠ the primary judge (Gemini); the student critic ≠ the author's vendor. DeepSeek is text-only, so never route image inputs to it.
7. **The judge never steers the deck it grades.** Judge feedback reaches the deck only through the human step (§7.10), and the comparison is scored before human edits.
8. **Manual edits to the deck** are separate git commits prefixed `manual:`; they're counted on the workflow slide.
9. Don't commit `.env`, `runs/` or the SlideAudit data (see `.gitignore`).
10. **Never `git push` without the user's explicit permission.** Commit only when the user asks.

## Environment

- Windows 11; the shell is PowerShell, Git Bash is also available. WSL2 hosts the `python_exec` sandbox (`unshare -rn`) and any Linux-only evaluator.
- Python 3.11+ (venv in `.venv/`), Node 20+ (Slidev in `deck/`), Ollama with a 3–4B Q4 model (the GPU has 4 GB VRAM).
- Secrets live in `.env` (`OPENROUTER_API_KEY`, …); `.env.example` is the committed template.

## Commands

```powershell
# setup
py -3.13 -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -e ".[dev]"
cd deck; npm install; npx playwright install chromium; cd ..

# run
papertrail --config full --paper 2505.06120 [--dev] [--from-stage N] [--only STAGE] [--run-dir runs/<ts>]
papertrail --config oneshot --paper 2505.06120
python -m papertrail.compare.run_compare --full runs/<ts>          # oneshot vs. full table
python -m papertrail.compare.critic_eval --prepare; python -m papertrail.compare.critic_eval --run   # SlideAudit F1 check
python -m papertrail.report.trace_page runs/<ts>                    # rebuild trace.html + pipeline.mmd

# tests
pytest                                                   # offline, no key
python tests/e2e_fake.py                                 # full pipeline with scripted fake models (real Slidev render), no cost
```

## Do not run the paid pipeline without being asked

A real run (no `--dev`, or any run with a key) costs real money. Only run it when the user says so, and never to test a code change: use `pytest` and `python tests/e2e_fake.py` (scripted fake models, no cost).

## Working conventions

- Follow the build order in SPEC §14; the minimum viable version comes first.
- Build each stage so it can run alone (`--only`) and resume (`--from-stage`). Test a stage against the saved outputs of the previous stage instead of re-running the whole pipeline.
- Use `--dev` (cheap/free models) while developing; Sonnet and Gemini Pro only for final runs.
- Before relying on a model slug, price or external dataset, check it (SPEC §17) and record the result in `config/model_selection.md` or `Tasks.md`.
- Keep files small and single-purpose; stage modules expose one `run(run_dir, cfg)` entry point.
- Match the deck design system (SPEC §9) and the anti-slop rules (SPEC §8 `slide-design`) in anything that ends up on a slide.
