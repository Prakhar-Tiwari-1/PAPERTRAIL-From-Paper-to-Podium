# Tasks

Progress tracker for **papertrail — From Paper to Podium**. Spec references are to `SPEC.md`. Tick `[x]` when done; add new tasks under the right phase.

**Deadlines:** slot sign-up **Mon 2026-10-12** · talk **Mon 2026-10-19**.
**MVP cut line:** ingest → digest → difficulty map → plan → author → render loop (automatic checks + vision critic) → judge → human edits, plus trace page, workflow slide and the oneshot vs. full comparison.

## Phase 0 — Admin and setup (Day 1, block 1)

- [ ] Sign up for the presentation slot (deadline today, Oct 12)
- [x] Create GitHub repo + `git init` (README committed)
- [ ] Commit spec, CLAUDE.md, Tasks.md, .gitignore, .env.example (push only with the user's permission)
- [ ] OpenRouter account: add credit, set a per-key credit limit (~$10), put the key in `.env`
- [x] Verify slugs and prices on openrouter.ai (§17): Sonnet 5.5, Haiku 5.5, Gemini 3 Flash, Gemini 3.1 Pro, DeepSeek chat + reasoning (`:free`?, context length, tool calling), a free vision model → `config/models.yaml`
- [ ] Check whether OpenRouter returns usage cost per response; check free-model daily limits
- [ ] Install Ollama; `ollama pull` a 3–4B Q4 model (Qwen/Gemma class); test JSON-schema output
- [ ] Check that WSL2 is available and `unshare -rn` works
- [x] Python venv + `pyproject.toml` (pydantic-ai, pydantic, pymupdf, httpx, pyyaml, matplotlib, pandas, pytest)
- [x] Slidev project in `deck/` + theme skeleton (tokens.css, layouts from §9, SourceCaption component)
- [x] Done when: `slidev export` renders a dummy deck to PDF and PNG

## Phase 1 — Harness core (Day 1, block 2)

- [x] `config/models.yaml` (role → model, fallback, temperature, max_tokens, skills, prices), `budget.yaml`, `rubric.yaml`
- [x] `common/schemas.py`: Pydantic models for every stage output (§7)
- [x] `common/llm.py`: PydanticAI agent per role via OpenRouter; disk cache keyed `(model, prompt_sha256, params, repeat_idx)`; fallback on 429/5xx/invalid output
- [x] `common/budget.py`: pre-call worst-case check + post-call actual cost; per-run and total caps
- [x] `common/trace.py`: `trace.jsonl` + `cost.json`
- [x] `common/skills.py`: load `skills/*/SKILL.md` by stage
- [x] `pipeline.py`: CLI (`--config`, `--paper`, `--from-stage`, `--only`, `--dev`), run directory, stage registry
- [x] Tests: cache key includes repeat_idx; budget guard blocks over-cap calls
- [x] Done when: a test call is traced and costed

## Phase 2 — Understanding the paper (Day 1, blocks 3–4)

- [x] 7.0 Ingest: arXiv source first (figures → SVG, LaTeX tables), PDF fallback → `paper.md` with `[p.N]` markers, `figures/`, `tables.json`, `refs.json`
- [x] Skill `paper-comprehension`
- [x] 7.1 Digest → `digest.json` (every claim anchored)
- [ ] §5.2 cheap-model check for the digest role (DeepSeek/free vs. Haiku, 3 inputs) → `config/model_selection.md`
- [x] Tool `dataset_lookup` (sharded_instructions_600.json)
- [x] Skill `explanation-devices`
- [x] 7.2 Difficulty map → `difficulty_map.json` + audience model
- [x] Tool `scholar_search` / `scholar_paper` (cached, ≤20 calls/run)
- [x] 7.3 Prior work → `prior_work.json`
- [x] Skill `slide-design` (anti-slop, with the SlideAudit/Gestalt mapping table)
- [x] 7.4 Plan → `plan.json` (12–18 slides, 19–20 min, every hard concept assigned)
- [ ] Done when: `plan.json` covers every hard concept

## Phase 3 — Authoring (Day 1, block 5)

- [x] Skills `slidev-authoring`, `diagram-style`, `speaker-notes`
- [x] Tool `mermaid_check` (mermaid-cli)
- [x] 7.6 Author → `deck/slides.md`, notes, `deck.json`
- [x] Tool `render` (slidev build + export png/pdf)
- [ ] Done when: deck v0 `slides.pdf` renders

## Phase 4 — Render loop (Day 1, block 6)

- [x] `qa/element_map.mjs`: `elements.json` per slide + annotated PNG with numbered boxes + `source_line`
- [x] `qa/overflow_check.mjs`: overflow, <16 px, safe area, words/bullets, image scaling, source caption, WCAG contrast, banned-pattern regex
- [x] `prompts/vision_critic.md` (19-category SlideAudit taxonomy + calibration notes, Appendix B.2) and `vision_critic_deck.md`
- [x] `qa/contact_sheet.py` (4×5 grid)
- [x] `prompts/student_critic.md`
- [x] 7.7 loop: render → checks → per-slide critic → deck critic → student critic → author revises (element_id → source_line); max 3 rounds → `qa.json`
- [ ] Done when: `qa.json` shows issues falling across rounds

## Phase 5 — Analysis, critic validation, judge (Day 2)

- [x] `tools/python_exec.py` sandbox (WSL `unshare -rn`, stripped env, 60 s, writes only to artifacts/); Windows fallback
- [x] Skill `figure-replot` + shared matplotlib style
- [x] 7.5 Analyze: re-plot of a paper figure + aptitude/unreliability explanatory graph (check per-run scores exist, §17)
- [ ] SlideAudit: check license and format (§17); build a 50-slide stratified sample
- [x] `prompts/vision_critic_zeroshot.md`; `compare/critic_eval.py` 2×2 grid → macro P/R/F1 → choose the vision critic
- [x] 7.9 `judges/checklist_gen.py` + `judges/score.py` (per dimension, 2 repeats, quotes required)
- [ ] First full Sonnet run
- [x] `report/trace_page.py` → `trace.html` + `pipeline.mmd`
- [ ] Tools & Workflow slide generated from the run
- [x] README: reproduction steps, results, cost

## Phase 6 — Stretch and comparison (Wed–Thu, Oct 14–15)

- [x] 7.8 Fact-check: regex + local model pairing + anchor-scoped matching → `factcheck.json`, `waivers.json`
- [ ] Hand-label 30 numbers; extractor precision/recall
- [x] `prompts/oneshot.md`; `compare/run_compare.py`: oneshot vs. full, 2 judge repeats (+ optional DeepSeek second judge) → `compare/summary.md` + chart slide
- [x] 7.10 Human review → `human_review.json`; fixes back through the author or as `manual:` commits
- [x] 7.10 Export: `final/slides.pdf`, `slides-editable.pptx`, `trace.html`, `pipeline.mmd`
- [ ] (Stretch) Experiment A: lost_in_conversation, FULL vs. SHARDED, 2 deterministic tasks, 10×5, DeepSeek or Gemini Flash; `PATCHES.md`; cap $2

## Phase 7 — Finish and rehearse (Fri–Sun, Oct 16–18)

- [ ] Check acceptance criteria §15 (1–8)
- [ ] Freeze the deck; final export
- [ ] Rehearsal 1 (timed, 20 min)
- [ ] Rehearsal 2 with Q&A, using the student critic's questions
- [ ] Clean-clone reproduction test following the README

## Spend log

| Date | What | $ | Running total |
|---|---|---|---|
| | | | |

## Notes / decisions during build

- 2026-10-12: first real `--dev` run done up to the judge (score 54/100, no hard fail, $0.79 spent). Full account, fixes and open problems: [docs/RUNLOG.md](docs/RUNLOG.md). Render loop is now **one** critique+revise round by default (`--rounds 1`).
- 2026-10-12: harness, all stages, QA scripts, judge, export, trace page, compare scripts and a fake-model end-to-end run are built and tested offline (`pytest`, `python tests/e2e_fake.py`). **Nothing has been run with real model keys yet**, so the boxes above that need a real model's behaviour (Digest quality, Difficulty map, "Done when" criteria that need `plan.json`/`qa.json` from real runs) are ticked for the code, not for the result. Re-check them after the first real `--dev` run.
- Still open: OpenRouter key + credit + key limit; `ollama pull qwen3:4b` (Ollama not installed); sign-up for the presentation slot; commit (nothing committed yet); §5.2 cheap-model checks and the SlideAudit F1 check need a key; 30 hand-labelled numbers for the extractor (`python -m compare.extractor_eval --template`); Experiment A not started.
- The released lost_in_conversation data has no per-run scores, so the aptitude/unreliability explanatory graph needs another data source (see `config/model_selection.md`).
- WSL has no usable distro (docker-desktop only): the sandbox uses the documented Windows fallback.
