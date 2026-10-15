# papertrail Implementation Plan

> **For agentic workers:** use superpowers:executing-plans (inline) or superpowers:subagent-driven-development. Steps use `- [ ]` checkboxes. This plan is condensed: code lives in the repo, not in the plan; each task names its files, interfaces and the test that proves it.

**Goal:** Build the papertrail pipeline: paper (arXiv ID/PDF) → Slidev deck with a two-critic render loop, fact-check, and cross-vendor judge.

**Architecture:** `pipeline.py` is a plain state machine over stage modules (`stages/*.py`, each exposing `run(run_dir, cfg)`). `common/llm.py` wraps PydanticAI (`OpenRouterModel`) with cache, budget guard, trace and fallback. Contracts between stages are Pydantic schemas in `common/schemas.py`.

**Tech Stack:** Python 3.13 (venv `.venv`), pydantic-ai-slim 2.55, PyMuPDF, httpx, matplotlib/pandas, pytest; Node + Slidev + Playwright for rendering/QA; Ollama (local fact extractor).

**Spec:** `SPEC.md` (v2.2). Rules: `CLAUDE.md`.

## Global Constraints

- No model slug in stage code; roles resolve via `config/models.yaml` (CLAUDE.md rule 1).
- Every LLM call goes through `common/llm.py`; cache key includes `repeat_idx`.
- Budget: $2.00 per run, $10.00 total, checked before (worst case) and after (actual) each call.
- DeepSeek is text-only: never send images to it. Author vendor (Anthropic) ≠ primary judge (Google) ≠ student critic vendor.
- Only the analyst runs code, via `tools/python_exec.py` (no network, stripped env, writes only under `artifacts/`).
- 12–18 main slides, 3–5 backup, Tools & Workflow is the last main slide.
- Never commit `.env`, `runs/`, SlideAudit data. Never push without permission; commit only when asked.

## Review Focus

- Missing/empty `OPENROUTER_API_KEY` → clear error before any network call (test in Task 2).
- Free model returns 429/invalid JSON twice → single paid-fallback retry, logged (test in Task 2).
- Budget cap hit mid-run → stage aborts, partial outputs kept, run resumable (test in Task 2/3).
- Paper has no LaTeX source / figure without caption → PDF fallback, no crash (Task 4).
- Claim without an anchor from the model → dropped, not kept (Task 5).

## File Map

| Area | Files |
|---|---|
| Config | `pyproject.toml`, `config/{models,budget,rubric}.yaml`, `config/model_selection.md` |
| Core | `common/{schemas,llm,budget,trace,skills}.py`, `pipeline.py` |
| Stages | `stages/{ingest,digest,difficulty,prior_work,plan,analyze,author,render_loop,factcheck,judge,export}.py` |
| Tools | `tools/{dataset,scholar,python_exec,render,mermaid_check}.py` |
| Skills/prompts | `skills/*/SKILL.md` (7), `prompts/*.md` (6) |
| QA | `qa/{overflow_check.mjs,element_map.mjs,contact_sheet.py}` |
| Judge/report | `judges/{checklist_gen,score}.py`, `report/trace_page.py`, `local/ollama_client.py` |
| Deck | `deck/{package.json,slides.md,theme/...}` |
| Compare | `compare/{run_compare,critic_eval}.py` |
| Tests | `tests/test_*.py` |

## Tasks

### Task 1: Scaffold + config
Files: `pyproject.toml`, `config/*.yaml`, `common/__init__.py`. Deliverable: `pip install -e ".[dev]"` works; `models.yaml` has every role of SPEC §5.1 with `model`, `fallback`, `temperature`, `max_tokens`, `skills`, `vision`, prices; slugs flagged `verify: true` until checked against openrouter.ai (SPEC §17).
- [ ] Write files; [ ] `pytest` collects (0 tests ok); [ ] checkpoint.

### Task 2: Harness core (`common/`)
Interfaces — Produces: `load_models() -> dict[str, RoleConfig]`; `Budget(run_dir).check(est_usd)`/`.add(actual_usd)` raising `BudgetExceeded`; `Trace(run_dir).log(event: dict)`; `Skills.for_stage(stage) -> str`; `call_role(role, prompt, *, output_type, run_dir, repeat_idx=0, images=None, tools=()) -> T`.
- [ ] Tests first (`tests/test_budget.py`, `tests/test_llm_cache.py`): cache key differs by `repeat_idx`; over-cap call refused before network; missing key errors; fallback fires after two failures (PydanticAI `TestModel`/`FunctionModel`, no network).
- [ ] Implement; [ ] run tests green.

### Task 3: Pipeline CLI
`pipeline.py --config {oneshot,full} --paper X [--from-stage N] [--only STAGE] [--dev]`; stage registry ordered per §7; creates `runs/<ts>/`; resume by skipping stages whose output validates. Test: registry order; `--only` runs one stage; `--from-stage` skips earlier.

### Task 4: Ingest (7.0) — no model
arXiv source download (tarball → LaTeX tables, figure PDFs → SVG) with PyMuPDF PDF fallback → `paper.md` with `[p.N]`, `figures/`, `tables.json`, `refs.json`. Test on a tiny synthetic PDF built in the test.

### Task 5: Digest (7.1) + skill `paper-comprehension`
`digest.json`; post-validation drops claims lacking anchor. Test: stubbed model returning an unanchored claim → dropped.

### Task 6: Difficulty map (7.2), prior work (7.3), plan (7.4)
Tools `dataset_lookup`, `scholar_*`. Plan validator enforces 12–18 slides, minutes 19–20, ≤2 min/slide, required slides, every concept assigned, Tools & Workflow last. Tests on the validator with good/bad plans.

### Task 7: Author (7.6) + skills + `mermaid_check` + deck scaffold
Slidev theme per §9; author writes `deck/slides.md`, `deck.json`; notes word count check 2,400–2,900. Test: `deck.json` coverage checker.

### Task 8: Render loop (7.7)
`tools/render.py`, `qa/element_map.mjs`, `qa/overflow_check.mjs`, `qa/contact_sheet.py`, prompts for vision/deck/student critic; loop with stop rule (0 high or 3 rounds) → `qa.json`. Test: loop logic with stubbed critics (issues fall → stops; cap at 3).

### Task 9: Analyze (7.5) + `python_exec` sandbox
Windows fallback sandbox (WSL has no usable distro on this machine). Test: network blocked, env stripped, write outside `artifacts/` refused.

### Task 10: Fact-check (7.8), Judge (7.9), Export (7.10), trace page
Test: anchor-scoped numeric matching (exact / rounded / mismatch); judge uses distinct `repeat_idx`.

### Task 11: Compare + critic eval + oneshot + README
`compare/run_compare.py`, `compare/critic_eval.py` (macro P/R/F1), `prompts/oneshot.md`. Test: metric function on a toy confusion set.

## Self-review
Spec coverage: §4→T2/3, §6→T6/7/8/9, §7.0–7.10→T4–T10, §8/§9→T5–T8, §10→`rubric.yaml`+T10, §11→T9/T11, §12→T10 (trace page), §13 layout matches File Map. Experiment A (§11 stretch) intentionally deferred.
