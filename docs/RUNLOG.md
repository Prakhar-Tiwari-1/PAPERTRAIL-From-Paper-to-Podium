# Run log

Dated record of real runs: what was run, what happened, what was changed because of it. Newest first. Spend is from `runs/_spend.jsonl` (OpenRouter's returned cost).

## 2026-10-15: improvements round (offline only, no paid run)

Requested: speaking time of at least 15 minutes, reference slides, fuller slides, tighter prompts, a quiz slide. Built and tested with scripted fake models only; the real spend is unchanged at $6.25. The owner asked NOT to run the full pipeline: the next presentation uses a different paper.

- Notes 2,100 to 2,900 words; 13 to 16 main slides (more room for explanation steps); quiz slide counted at 3 minutes.
- Reference slides: stages `style` and `style_compare`, `tools/references.py`, `references/` folder, near-copy guard.
- Empty space: a measured check (`qa/metrics.mjs`, `sparse_slide`), layouts that fill the slide (`claim-split`, bigger tables, bullets and numbers), author and planner rules, and the reviser told to add a visual instead of text.
- Prompts: compact data blocks (minified JSON, `paper_llm.md`, table excerpts), per-slide revision (a fraction of the output tokens and time of a whole-deck rewrite), skills rewritten and length-tested.
- Critic strictness: measurement cross-check, "contested" issues stop being retried, evidence required, intended design listed for the critic, hard cap on issues per slide.
- Quiz: `stage quiz`, `report/quiz_slide.py`, layout `claim-quiz`.
- Offline end-to-end run: the empty-space check sent 3 sparse slides to the reviser, triage demoted a false overflow claim, the quiz and style stages ran, all 92 tests pass.
- **Made paper-independent (same day):** the old paper was a test. Everything specific to it moved into an optional profile (`papers/2505.06120.yaml`; `papers/default.yaml` is the empty default): candidate concepts, extra required slides, known critiques, quiz hints, the released dataset and its worked-example tool, citation overrides. The plan's required slides, the rubric wording, the skills and every prompt are generic; citations are built from the arXiv metadata. `tests/test_profile.py` fails if a paper-specific word appears in code. The offline end-to-end run passes for a paper with no profile and for the old paper with its profile.

## 2026-10-12 (evening): quality pass before the final run

Triggered by review of the first deck: 23 pages, flat look, text-heavy slides, many bullet-only slides without visuals. Changes (all tested offline; no model run yet):

- Deck shape: 12-14 main slides + exactly 3 backup (about 17 pages). Every slide except the title carries a paper visual; at most two bullet-only main slides; 50-70 visible words (hard cap 70). Enforced at author time (`common/deckcheck.py`), in the render checks, and in the plan validator. New `claim-table` layout; the author gets paper tables as markdown excerpts.
- Theme: navy + orange palette, white figure cards, tinted panels, coloured chat bubbles, table styling, photo title page with presenters, faint crest watermark, editable footer (`deck/footer.json`).
- Writing quality: `qa/slop_check.py` + `qa/slop.json` scan slides and speaker notes (the DOM checks never saw notes); wired into author validation and the render loop. Skills `slide-design`, `slidev-authoring`, `speaker-notes` rewritten.
- Judge: new visual-appeal item D4 judged from the slide images (design is now D1 3, D2 2, D3 2, D4 3); faithfulness quotes must really occur in the paper; judge context is the digest plus only the cited paper pages (not the whole paper), with the shared context first for prefix caching.
- Context size: `paper_llm.md` (body without bibliography and figure-label junk, appendices cut to stubs) is what digest and difficulty read: 155k to 72k characters.
- Vision critic: Gemini 3 Flash for dev and final (the free Gemma hit 157 rate limits).
- Cleanup: the previous run directories were deleted at the owner's request (this log and `docs/` keep the history). The budget ledger `runs/_spend.jsonl` was kept so the $10 cap still counts what was spent.

## 2026-10-12 (later): one-loop run finished, export succeeded

Same run dir (`runs/20261012-112632`), render loop set to **one** critique+revise round. Output: `final/slides.pdf` (23 pages: 17 main + section + 5 backup), `final/slides-editable.pptx`, `final/trace.html`, `final/pipeline.mmd`. Spend in this dir: **$1.51** (includes the abandoned 4-round attempt, about $0.5).

- Render loop: high-severity issues 37 -> 29 after the one revision. After the fact-check fix pass, only 4 automatic issues remain, all on slide 2 (content 788 px tall in a 720 px slide: figure plus caption plus text overflow).
- Fact-check: 7 numbers were unverified; the one author fix pass resolved all 7, including replacing the invented "Ara" example with the real dataset instance `sharded-GSM8K/1246`. Final: 42 of 42 numbers match their cited source, 0 waived.
- Judge (Gemini 3 Flash, dev; 2 repeats): **87/100**, no hard fail. Faithfulness 25/25, explanation 20/20, coverage 20/20, narrative 15/15, design 7/10, beyond the paper 0/10. A cheap dev judge: indicative, not the final number.
- Remaining failures: B1 (no own-analysis slide with an artifact: both analyst attempts failed), B2 (the judge still compared the Tools & Workflow slide with the paper rather than with the pipeline, and read the slide's $1.15 as a claim about the paper's cost), D2 (slide 2 overflow).
- Fixes made during this stretch: the fact extractor degrades instead of failing a batch (one DeepSeek batch looped until its token limit); the judge re-asks for items it skipped; the workflow slide has a fixed claim title and counts only real (non-cached) calls; B2 gets pipeline facts.
- Next, in order of value: (1) an own-analysis artifact that needs no per-run scores (for example the distribution of shards per task from the released dataset), to earn B1; (2) slide 2 overflow; (3) make the judge's B2 reliable (or score B2 from run facts); (4) install Ollama; (5) the final run with the real models (Sonnet author, Gemini Pro judge).

## 2026-10-12: first real `--dev` run (cheapest models), paper 2505.06120

Run dir `runs/20261012-112632`. The same files as they were after the 4-round attempt are archived in `runs/20261012-112632-4round-attempt/` (gitignored, local only). Total spent in this dir so far: **$0.79** of the $10 cap.

Models (`--dev`): digest Haiku 5.5; difficulty, prior work, planner, analyst, student critic: DeepSeek V4 Flash; author Haiku 5.5; vision critic Gemma 4 31B (free), falling back to Gemini 3 Flash; checklist DeepSeek V4 Flash; judge Gemini 3 Flash; fact extractor: Ollama is not installed, so it fell back to DeepSeek V4 Flash.

| Stage | Result | Time | Notes |
|---|---|---|---|
| ingest | ok | 6 s | 36 pages, 7 figures. Only 3 of 9 tables were found at first (see Fixes). |
| digest | ok | 154 s | Free Nemotron used its whole 8,000-token limit on reasoning twice, then fell back to Haiku: 10 claims, 8 terms, $0.0075 |
| difficulty | failed, then ok | 11 min, then 53 s | Failed on an anchor like "Appendix F (p.22-24)" and on a 2.2M-token tool loop ($0.14). Fixed, rerun cost $0.009. |
| prior work | ok | 61 s | |
| plan | failed, then ok | 335 s | Failed on "minutes total 21.5" and a "title slide" keyword check. Fixed in code. |
| analyze | both analyses failed | 118 s | Request used Table 6 (not ingested); the second hit the tool-call cap. The deck used paper figures instead. |
| author | ok | 349 s | 17 main + 5 backup slides, 2,702 words of notes. $0.04 |
| render loop (4 rounds) | ran, weak convergence | 17.6 min | High-severity issues 37, 28, 29, 27. Persistent: "Unbalanced Space Distribution" (13 to 17 per round, likely partly false positives on deliberately sparse slides) and overflow/cut-off. 157 rate-limit errors from the free Gemma model, all handled by the paid fallback. |
| fact-check | 30 of 39 matched at first | 24 s | After the table fix, 6 unmatched: see below. |
| judge | 54/100, no hard fail | 168 s | Faithfulness 25/25. Judge also flagged slide 3's worked example ("Ara plays 40 games per year") as not from the dataset. |
| export | blocked, as designed | | 6 numbers unverified: "6 tasks" (paper says "six"), 40 (fabricated example), 2024 and 2026 (years), 0.5 and 0.0 (uncited temperatures) |

### What was changed because of this run

- Shared anchor validator (`common/anchors.py`): accepts "Fig. 4 (p.5)", "Appendix F (p.22-24)", "pp. 3-4".
- Tool loops are capped (`max_tool_calls`, default 4, analyst 8) and the pre-call budget estimate now scales with the cap. The dataset tool output is smaller and two real examples are put in the difficulty prompt up front.
- Plan: minutes are rescaled in code to 19.5 total (models are bad at arithmetic); the title slide is the first slide.
- Ingest: `wraptable` environments are parsed (3 tables became 9); tables are numbered from the PDF's own "Table N:" captions; heat-map cell colour codes are stripped (30.9, not DFE9F830.9).
- Fact-check: spelled-out numbers match digits ("six" = 6); unverified numbers now go back to the author for one fix before export blocks.
- Judge scoring: a parent item whose sub-checks were all answered is derived from them; a missing verdict is reported as "not judged" instead of silently failing.
- Dev digest model is Haiku 5.5 (the free Nemotron wasted 2.5 minutes and fell back anyway).
- Defaults: **one** critique-and-revise round in the render loop (`--rounds 1`), followed by one verifying critique; one fact-check revision.

### Open problems seen

- Fixing layout issues with a cheap author (rewriting the whole deck each round) does not converge well.
- The slide-3 worked example is invented. The difficulty map should force the dataset example into the slide; the author prompt asks for it but a cheap model ignored it.
- No explanatory graph: the released data has no per-run scores. The analyst failed twice on it.
- Ollama is not installed, so the local-model stage has not run locally.
