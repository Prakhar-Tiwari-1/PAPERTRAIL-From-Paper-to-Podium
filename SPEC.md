# SPEC: papertrail — From Paper to Podium

*An agent harness that understands a paper before it presents it. Agentic slide generation inspired by DeepPresenter and SlideAudit.*
Repo: https://github.com/Prakhar-Tiwari-1/PAPERTRAIL-From-Paper-to-Podium

Version 2.2 · 2026-10-12 · **This is the only spec.**
Build: Mon–Tue 2026-10-12/13 (core) + Oct 14–15 (stretch) + Oct 16–18 (rehearsal) · Talk: Mon 2026-10-19, 25 min (20 talk + 5 Q&A)

---

## 0. Start here (for a new session)

**What this project is.** A university course requires presenting a research paper with slides that are AI-generated with only light manual editing, ending in a slide about the tools and workflow used. Bonus points come from (A) building our own agent harness, skills and workflow, with one stage on a locally deployed model, and (B) analysis beyond the paper. We are building **papertrail** (tagline "From Paper to Podium"): a Python pipeline that reads the paper, works out what is hard to understand and how best to explain it, plans and writes a Slidev deck, renders it, critiques the rendered slides with a vision model and a "confused student" model, revises, fact-checks numbers with a local model, and scores the result with a judge from a different vendor. The pipeline's own trace is shown to the professor.

**Decisions already made (don't reopen them without the user):**
- **Paper presented:** *LLMs Get Lost In Multi-Turn Conversation* (arXiv:2505.06120).
- **Harness:** our own Python state machine (`pipeline.py`); **PydanticAI only as the typed LLM-call layer**; all models through **OpenRouter**, plus **Ollama** for the local stage.
- **Revision loop:** modelled on **DeepPresenter** (render → vision critique → revise), extended with a student critic.
- **Vision critic:** built from **SlideAudit** (arXiv:2508.03630; PDF in the repo root as `2508.03630v1.pdf`): its taxonomy prompt, element-ID references and fix-plan output (§4, §7.7).
- **Models:** Claude Sonnet 5.5 writes (difficulty map, plan, author). DeepSeek and free open-weight models do cheap text work. Gemini does vision and judging. A local 3–4B model does fact extraction (the user's GPU has 4 GB VRAM).
- **Deck:** **Slidev**; **13–16 main slides** (one of them the quiz slide) + **exactly 3 backup slides** (changed 2026-10-12 from 12–18 + 3–5: a 20-minute talk needs fewer, stronger slides); Tools & Workflow is the final main slide. **Every slide except the title slide carries a visual from the paper** (figure, table excerpt, diagram, worked example or big number); at most two main slides are bullets only; **visible text 50–70 words per slide, never above 70** (changed from 60).
- **Paper-independent (2026-10-15):** the pipeline works for any paper. *LLMs Get Lost In Multi-Turn Conversation* was a TEST paper; everything specific to it lives in `papers/2505.06120.yaml` (optional per-paper profile, `common/profile.py`). A paper without a profile uses `papers/default.yaml` (all empty). Citations come from the arXiv metadata (`tools/arxiv_meta.py`).
- **Added 2026-10-15:** (1) speaker notes fill **15 to 20 minutes** (2,100 to 2,900 words at 140 wpm); (2) **reference slides**: example slides the owner likes go in `references/slides/`; stages `style` and `style_compare` turn them into a style brief for the author and a feature comparison at the end, with a near-copy guard (never a copy); (3) the **empty-space check** (`sparse_slide`) sends slides that leave a hole of 100 px or more, or use under 40% of the content area, back for a visual, not for more text; (4) **one quiz slide** (layout `claim-quiz`, stage `quiz`): six questions on what the talk taught (3 concept, 3 what-if; changed from 7 to 8 on 2026-10-15 because eight did not fit above the footer), answers below, grounded in the paper and fact-checked, and any number written in a question must occur in its cited source; (5) render-loop revisions are **per slide** (role `reviser`), not whole-deck rewrites, and vision-critic claims about measurable things are checked against the DOM before they count (`qa/triage.py`); (6) prompts are compacted (`paper_llm.md`, minified JSON) and kept within length limits (`tools/prompt_audit.py`, `tests/test_prompts.py`).
- **Look (added 2026-10-12):** navy from the university logo plus a brick-red highlight (replaced the Okabe-Ito orange on 2026-10-15; no heading rule, no crest credit line on the title slide), flat colour only; title page with the campus photo under dark shading, the paper citation, the three presenters (Prakhar Tiwari, Karl Zeeny, Adrian Garcia), course and date; faint crest watermark bottom right on content slides; editable footer (logo, course code and name, page number) from `deck/footer.json`. Course: CSC_53432_EP - Large Language Models.
- **Writing quality (added 2026-10-12):** `qa/slop_check.py` scans slides AND speaker notes for AI-sounding phrasing; high-severity hits go back to the author.
- **Budget:** **≈ €10 total**, enforced in code at $10. Free and DeepSeek models are preferred wherever they pass the §5.2 check. The user may pay for a better judge later.
- **Environment:** Windows 11 + WSL2, Python 3.11+, Node 20+.

**Current status (2026-10-12):** spec approved. No code is written yet. The repo contains this spec, the SlideAudit PDF, `CLAUDE.md` (session rules), `Tasks.md` (progress tracker, organised by build phase), `README.md`, `.gitignore`, `.env.example` and a local `.env` with empty keys. Git repo initialised on `main` with remote `origin` = github.com/Prakhar-Tiwari-1/PAPERTRAIL-From-Paper-to-Podium (only README.md committed so far). **Never push without the user's explicit permission.**

**Next steps:**
1. Commit the spec and project files (with the user's OK).
2. Write an implementation plan from this spec (task by task, following the §14 order and the minimum viable version first).
3. Build.

The items in §17 must be checked during setup, before the code relies on them: model slugs and prices, DeepSeek free availability, the SlideAudit license, WSL.

**How to read this spec:**
- §1–3: goals and constraints.
- §4–6: harness, models, tools.
- §7: each stage's inputs, outputs and rules (the contracts between stages).
- §8–9: skills and design system.
- §10: rubric.
- §11: analysis beyond the paper.
- §13: repository layout.
- §14: build order.
- §15: acceptance criteria (the definition of done).

## 1. Goal

A pipeline that runs on your own machine and turns one research paper into a professional conference-style Slidev deck of **12–14 main slides** (plus 3 backup). The deck does more than summarise. It finds what is hard to understand in the paper and picks the best way to explain each hard part: a worked example from real data, an analogy, a diagram, a graph, or a comparison with prior work.

Requirements:
1. Slides generated by AI with only light manual editing (course requirement). Every manual edit is its own git commit.
2. The final main slide describes the tools and workflow (course requirement).
3. **Bonus A:** our own agent harness (orchestrator, skills, tools, critic loop) and one stage running on a local model.
4. **Bonus B:** analysis beyond the paper (re-plot plus a small replication) and a quantified comparison of the pipeline against a one-shot baseline.
5. The pipeline itself is shown to the professor: every stage's output can be inspected, and each run produces a trace page and a pipeline diagram labelled with real models, call counts and cost.

Non-goals: a general product, a web UI, robustness across arbitrary papers, video or speech generation.

## 2. Paper

**LLMs Get Lost In Multi-Turn Conversation** (Laban, Hayashi, Zhou, Neville), ICLR 2026 Outstanding Paper, arXiv:2505.06120.
- Code and data: `microsoft/lost_in_conversation` (MIT); `data/sharded_instructions_600.json`; also on Hugging Face.
- Headline: about a 39% average performance drop for sharded (multi-turn) instructions vs. fully specified ones, across six tasks and 200k+ simulated conversations.
- A critique to address: the award committee noted the models tested are dated.
- Fallback paper: Gated Attention for LLMs (NeurIPS 2025 Best Paper), `qiuzh20/gated_attention`.

## 3. Constraints

| Constraint | Value |
|---|---|
| Budget | **≈ €10 total** (≈ $10 cap in code to leave margin for fees). Can be raised later for a better judge or author. |
| Model access | OpenRouter, single key. Claude, Gemini, DeepSeek, plus free (`:free`) open-weight models wherever they match paid quality on a small check (§5.2). No Opus-tier models. |
| Local GPU | 4 GB VRAM → one quantized 3–4B model via Ollama, used only for fact extraction. CPU fallback is fine for this. |
| OS | Windows 11 + WSL2 (for the sandbox and any evaluator that needs Linux). Python 3.11+, Node 20+. |
| Security | Paper text and Semantic Scholar results are untrusted data. Only the analyst has a code tool, sandboxed with no secrets. No OpenClaw. |
| Manual editing | Allowed, minimal, each edit one `manual:` git commit, counted on the workflow slide. |

## 4. Harness architecture (Bonus A)

**Decision: our own orchestrator, with PydanticAI as the LLM-call layer.** The workflow, the critic loop, skills, tools, budget and tracing are our code. PydanticAI is used the way `requests` is used for HTTP: typed structured outputs, retries and tool-call loops against OpenRouter. It does not decide what happens next.

**Prior art we copy and adapt:** DeepPresenter's loop (plan → render → vision-model critique of the rendered images → revise). We rebuild it around Slidev and add a second critic, a "confused student" (§7.7), which checks whether the explanation works and not only whether the layout does.

**Prior art for the vision critic:** SlideAudit (Zhang et al., UIST 2025, arXiv:2508.03630). We adopt:
- its 19-category taxonomy of slide design flaws, with calibration notes, as the critic's prompt;
- the image plus structured element list as the critic's input;
- the structured fix-plan output.

We do not adopt LLM bounding boxes (IoU 0.248 in the paper) or computed signals fed to the model (saliency maps etc.), which made their results worse. Their evidence for these choices:
- macro F1 rose from 0.48–0.53 with no taxonomy to 0.59–0.66 with the full taxonomy;
- false positives fell from 34.6% to 9.6%;
- fix plans that could actually be implemented rose from 27.7% to 63.9%.

```
                  ┌─────────────── pipeline.py (state machine, our code) ───────────────┐
                  │ stages · resume · budget guard · trace · skills loader · tool registry │
                  └──────────────┬───────────────────────────────┬───────────────────────┘
                                 │                               │
                      common/llm.py (PydanticAI agents)   tools/ (our code)
                      routing from models.yaml            python_exec · render · dataset ·
                      cache · cost · fallback             scholar · mermaid_check · overflow
                                 │
                            OpenRouter  ·  Ollama (local)
```

### 4.1 Components

| Component | Responsibility |
|---|---|
| `pipeline.py` | CLI `--config {oneshot,full} --paper {PDF path | arXiv ID} [--from-stage N] [--only STAGE] [--dev]`. Each stage reads and writes files in `runs/<ts>/`, can run alone, and can resume. |
| `common/llm.py` | Builds a PydanticAI agent for a role from `config/models.yaml` (model, fallback model, temperature, max_tokens, skills). Every call is cached on disk, keyed by `(model, prompt_sha256, params, repeat_idx)`. **`repeat_idx` must be in the key** so repeated judge runs are real. Cost comes from OpenRouter's returned usage cost, with a YAML price estimate as fallback. Appends to `trace.jsonl`. |
| `common/budget.py` | **Before** each call: estimate worst-case cost (input tokens + `max_tokens` × output price); refuse if it would pass the cap. **After** each call: add the actual cost. Caps in `config/budget.yaml`: per run $2.00, total $10.00. |
| Fallback | A free model returning 429/5xx or invalid output twice → retry once on the role's paid fallback; logged in the trace. |
| `common/schemas.py` | Pydantic models for every stage output (§7). Schemas are the contracts between stages. |
| `common/skills.py` | Loads `skills/<name>/SKILL.md` (frontmatter: `name`, `description`, `stages`) and adds the relevant skills to a stage's system prompt. |
| `tools/` | Python functions registered as PydanticAI tools for the roles allowed to use them (§6). |
| `report/trace_page.py` | Builds `runs/<ts>/trace.html`: one card per stage (inputs, outputs, model, tokens, cost, time, critic issues per round), plus `pipeline.mmd`, a Mermaid diagram of the run labelled with real numbers. The demo for the professor, and the source of the workflow slide. |

## 5. Models

### 5.1 Role routing (`config/models.yaml`; no slug hard-coded in stage code)

Slugs and prices must be confirmed on openrouter.ai at build time. Prices per 1M tokens, input/output.

**Model families in use:** Anthropic (Claude) for writing; Google (Gemini) for vision and judging; **DeepSeek** for cheap text work; other free open-weight models where they win §5.2; one local model. DeepSeek is text-only, so it is never used for roles that must see images. Its chat model is the default cheap workhorse, and its reasoning model is used where step-by-step checking helps. Prefer the `:free` version when available; the paid version is still very cheap.

| Role | Final runs | Dev runs (`--dev`) | Fallback | Why |
|---|---|---|---|---|
| Digest (long-context reading) | DeepSeek chat (free if available) or best free open model with ≥128k context | same | Claude Haiku 5.5 | bulk reading; cheap models are good at it |
| Difficulty map, Planner, Author | Claude Sonnet 5.5 (≈ $2 / $10) | DeepSeek chat or Claude Haiku 5.5 | Claude Haiku 5.5 | quality of explanation and writing matters most here |
| Prior-work selector | DeepSeek chat (free) | same | Claude Haiku 5.5 | short, simple selection |
| Analyst (Python tool loop) | DeepSeek chat (tool calling) or Claude Haiku 5.5, whichever wins §5.2 | DeepSeek chat | Claude Haiku 5.5 | code generation with a tool; cheap is fine |
| Vision critic | winner of the SlideAudit check (§5.2): Gemini 3 Flash (≈ $0.50 / $3) or a free vision model | free vision model | Gemini 3 Flash | must see PNGs; chosen by measured F1 |
| Student critic | DeepSeek chat (free) | same | another free open model | **different vendor from the author**, so it doesn't share the author's blind spots |
| Fact extractor | **local** Qwen/Gemma-class 3–4B (Q4) via Ollama | same | DeepSeek chat | Bonus A local stage; easy task |
| Checklist generation (judge input) | DeepSeek reasoning model | same | Gemini 3 Flash | step-by-step reading of the paper into binary items; cheap |
| Judge (primary) | Gemini 3.1 Pro (≈ $2 / $12), final decks only | Gemini 3 Flash | — | cross-vendor from the Claude author |
| Judge (second, optional) | DeepSeek reasoning model | — | — | a third vendor at very low cost; gives judge agreement for the oneshot vs. full comparison. Can be upgraded later (e.g. GPT-5.5). |

Rules:
- The author (Anthropic) and the primary judge (Google) must come from different vendors.
- The student critic must come from a different vendor than the author.
- Exact DeepSeek slugs (e.g. `deepseek/deepseek-chat-…`, `deepseek/deepseek-r1-…`, and their `:free` versions) are confirmed on openrouter.ai at build time and live only in `models.yaml`.

### 5.2 Choosing free models (30 min, during setup)

For each cheap-model role (DeepSeek or other free models), run the role's prompt on 3 fixed inputs with the cheap candidate and with the paid fallback. A free model is accepted if a quick side-by-side review shows no loss in correctness. Results go in `config/model_selection.md`, which feeds one line on the workflow slide.

**Vision critic: chosen by measured F1 on SlideAudit** (`compare/critic_eval.py`):
- Data: a stratified sample of 50 slides from the SlideAudit dataset (github.com/zhuohaouw/SlideAudit), split as the paper does: about a third each with 0–1, 2–3 and 4+ flaws. Human labels are those with majority agreement (2 of 3 annotators).
- Grid: {Gemini 3 Flash, best free vision model} × {no-taxonomy prompt, full-taxonomy prompt}, image + element list where the dataset provides elements, otherwise image only.
- Metric: macro precision, recall and F1 over the paper's 19 evaluated categories (§7.7), as in the paper. Our `slop_pattern` category is excluded from scoring.
- Cost: ≤ $1. The highest-F1 configuration becomes the vision critic.
- The result is reported next to the paper's best (GPT-4o, 0.655) and becomes a small result beyond the paper (§11). Older models were tested in the paper, so the comparison is indicative, not like-for-like.

### 5.3 Estimated spend

| Item | Estimate |
|---|---|
| Dev runs (free models + Haiku), many | ≈ $0.50 |
| Full run on Sonnet (difficulty map, plan, author, ≤3 revisions) | ≈ $1.00–1.50 each × 3 = ≈ $4 |
| Vision critic (≈16 PNGs × 3 rounds × runs, + 1 deck-level call per round) | ≈ $0.50 |
| SlideAudit critic check (50 slides × 4 configs) | ≤ $1 |
| Judge (Gemini Pro, one call per rubric dimension × 2 repeats; 2 final decks) | ≈ $2 |
| DeepSeek roles (digest, prior work, student critic, analyst, checklist, second judge) | ≈ $0.50 (≈ $0 where the `:free` version works) |
| One-shot baseline + Experiment A (free/cheap models) | ≈ $1–2 |
| **Total** | **≈ $9–10**, at the $10 cap. If it gets tight, Experiment A is cut first. |

## 6. Tools

Only the roles listed may call a tool. The planner, author and critics have **no** tools that execute anything.

| Tool | Used by | What it does | Limits |
|---|---|---|---|
| `python_exec(code)` | Analyst | Runs Python to compute numbers and make plots from CSV/JSON data | Runs in WSL under `unshare -rn` (no network) with a stripped environment (no API keys), cwd = `runs/<ts>/artifacts`, 60 s timeout, writes only under `artifacts/`. If WSL is unavailable: a Windows subprocess with stripped env + timeout + a `sitecustomize` that disables sockets. This is weaker isolation, stated honestly in the README. |
| `dataset_lookup(task, n, filter)` | Difficulty map, Analyst | Returns real instructions and their shards from `sharded_instructions_600.json`, used for worked examples | read-only |
| `scholar_search(query)` / `scholar_paper(id)` | Prior-work selector | Free Semantic Scholar API: references, citations, abstracts | cached to disk; results treated as untrusted data; max 20 calls/run |
| `render(deck)` | Render loop (orchestrator, not a model) | `slidev build` + `slidev export --format png` and `pdf` | — |
| `mermaid_check(src)` | Author (validation tool) | Parses Mermaid with `@mermaid-js/mermaid-cli` and returns errors so the author fixes them before rendering | read-only |
| `overflow_check(build)` | Render loop | Playwright checks on the built SPA (§7.7), including the WCAG 2.1 contrast ratio for every text element (≥ 4.5:1 body, ≥ 3:1 for text ≥ 24 px) | — |
| `element_map(build, slide)` | Render loop | From the Slidev DOM, emits `elements.json` per slide (`{id, type ∈ [title, text, list, figure, diagram, table, caption, code], bbox (0–1 normalised), font_px, color, bg_color, text_excerpt, source_line}`) and an **annotated PNG** with a numbered box drawn around each element | `source_line` maps each element back to its line in `slides.md` |

**When a Python graph is made (and when not).** A plot is made only when the plan asks for one, for a stated purpose:
1. **Re-plot** of a paper figure from released data (house style, side by side with the original).
2. **Explanatory graph** for a hard concept, where a picture of data explains better than words. Example: the scores of 10 simulated runs of the same instruction, with aptitude (90th percentile) and unreliability (90th − 10th percentile gap) drawn on it.
3. **Our results**: the replication (§11) and the pipeline comparison chart.

Process flows, condition setups and conversation structures are **Mermaid diagrams**, not Python plots. Anything else gets no graphic.

## 7. Stages

Each stage writes its output into `runs/<ts>/` and validates it against its schema before the next stage starts.

### 7.0 Ingest (no model)
- Input: arXiv ID or PDF. Prefer the arXiv LaTeX source: figures come as separate PDFs (→ SVG via PyMuPDF), and tables are parsed from LaTeX. Otherwise PyMuPDF text extraction with figures cropped at 300 dpi.
- Output: `paper.md` (sections, `[p.N]` page markers), `figures/`, `tables.json`, `refs.json` (bibliography entries).
- Accept: every figure and table referenced in the text is present; section headings are kept.

### 7.1 Digest
- Output `digest.json`: `problem`, `contributions[]`, `method_summary`, `claims[] {text, anchor ("p.X" / "Table Y" / "Fig. Z"), numbers[]}`, `terms[] {term, definition, anchor}`, `results[]`, `limitations[]` (stated by the authors plus the "dated models" critique).
- Rule: every claim has an anchor. Anything the model can't anchor is dropped, not guessed.

### 7.2 Difficulty map (the core of "understanding the paper")
- Input: `digest.json`, `paper.md`, skills `paper-comprehension`, `explanation-devices`, tool `dataset_lookup`.
- Output `difficulty_map.json`, one entry per hard concept:
  `{concept, why_hard (jargon | counter-intuitive | multi-step | metric definition | needs prior knowledge), prerequisites[], misconception_to_avoid, device ∈ [worked_example, analogy, diagram, graph, prior_work_contrast], device_material, anchor}`
  - `device_material` is concrete: for `worked_example`, an actual instruction ID from the dataset with its shards shown turn by turn; for `analogy`, the mapping and **where the analogy breaks**; for `diagram`, a node/edge sketch; for `graph`, the data source and what the reader should see.
- Candidate concepts for this paper (the stage must confirm them against the text, not assume them): sharding an instruction; the five simulation conditions (FULL, CONCAT, SHARDED, RECAP, SNOWBALL) and what each one isolates; the simulated user and how answers are classified and graded; aptitude vs. unreliability; why the drop counts as "lost" and not just "worse"; the failure behaviours the authors identify; why lowering temperature does not fix it.
- Also outputs `audience_model`: what a classmate with general ML knowledge already knows vs. what must be taught.

### 7.3 Prior work
- Input: `refs.json`, `digest.json`, tool `scholar_search`.
- Output `prior_work.json`: 3–5 works `{title, year, relation (builds-on | contrasts | follow-up), one-line point, used_for (motivation | contrast slide | Q&A backup)}`. Each must appear in the paper's references or be a verifiable citing paper with its Semantic Scholar ID.

### 7.4 Plan
- Input: digest, difficulty map, prior work, skills `paper-comprehension`, `slide-design`.
- Output `plan.json`: `story_arc`, `slides[] {id, title (full-sentence claim), purpose, key_points[] (≤4), device (from difficulty map, or "none"), figure_ref | plot_request | diagram_request | null, anchors[], minutes}`, `backup_slides[]` (3–5), `analysis_requests[]`.
- Rules:
  - 12–18 main slides; minutes total 19–20; no slide over 2 minutes.
  - Every hard concept in the difficulty map is assigned to a slide, or explicitly deferred to backup with a reason.
  - Required slides: title; motivation (preferably opening with a worked example of a model getting lost); setup and conditions; metrics; headline result; failure behaviours; prior-work positioning; limitations incl. the dated-models critique; our analysis; takeaway; **Tools & Workflow as the final main slide**.

### 7.5 Analyze
- Input: `plan.analysis_requests`, released data, `tables.json`, skill `figure-replot`, tools `python_exec`, `dataset_lookup`.
- Output: `artifacts/*.csv` (data behind every plot), `artifacts/*.svg`, `artifacts/analysis_notes.md`.
- Rule: no number typed by hand; every plotted value is read from a file. One shared matplotlib style file.

### 7.6 Author
- Input: plan, artifacts, figures, skills `slide-design`, `slidev-authoring`, `diagram-style`, `speaker-notes`, tool `mermaid_check`.
- Output: `deck/slides.md`; speaker notes on every slide (total 2,400–2,900 words ≈ 19–20 min at ~140 wpm); `deck.json` mapping every number and claim on each slide to an anchor or artifact CSV.
- Rules: only theme layouts; split slides instead of shrinking text; Mermaid must pass `mermaid_check`.

### 7.7 Render loop (DeepPresenter-style, two critics)
Each round:
1. `render` → `runs/<ts>/render/round_k/*.png` + PDF.
2. **Automatic checks** (`qa/overflow_check.mjs`, Playwright, measured at the 1280×720 canvas):
   - overflow (`scrollHeight > clientHeight`);
   - font below 16 px;
   - element outside the 64 px safe area;
   - more than 60 words or more than 4 bullets;
   - image scaled above 1.5× its native size;
   - figure without a source caption;
   - WCAG contrast below threshold;
   - banned patterns (regex list from the `slide-design` skill).

   These are computed facts. They go straight to the author as issues and are **not** fed to the vision critic as hints (SlideAudit found that feeding computed signals to the model increased false positives).
3. **Vision critic, per slide** (prompt `prompts/vision_critic.md`, adapted from SlideAudit Appendix B.2):
   - **Input:** the annotated PNG (numbered element boxes) + `elements.json` + the full taxonomy below with a definition and calibration note per category.
   - **Instructions taken from the paper:**
     - judge visual properties (size, weight, colour, alignment) **from the image**; the element list is only for naming elements;
     - do not flag an issue just because a property is missing from the list;
     - do not force-find issues; a well-designed slide returns `[]`.
   - **Output** (strict JSON array, SlideAudit fix-plan format extended with severity and element IDs): `{slide, category, element_ids[], issue, problem_description, fix_steps[], expected_improvement, severity ∈ [low, high]}`. No praise, no content changes, no coordinates.
   - **Taxonomy:** the 19 SlideAudit categories evaluated in the paper (the same set as the §5.2 check), plus one category of ours. Animation categories are left out because the deck uses almost no animation; cross-slide categories are covered in step 4.
     - *Composition & layout:* lack of visual hierarchy; cluttered layout; unbalanced space or margin usage; misaligned elements; content overflow or truncation; occluded content.
     - *Typography:* illegible typeface; inappropriate font sizing; excessive text density; inconsistent or distracting text styling; improper line or character spacing; lack of text hierarchy.
     - *Colour:* insufficient contrast; overuse of or inconsistent colour; poor colour combinations.
     - *Imagery:* irrelevant or off-topic visuals; low-quality or distorted images; improper image scaling or size; inconsistent visual style.
     - *Our extension:* `slop_pattern` (any banned pattern from `slide-design` that the regex missed).
   - **Calibration notes** are copied from the paper, e.g. "lack of visual hierarchy: not common, do not be strict"; "excessive text density: distinguish from cluttered layout". Each category's note sits next to its definition in `prompts/vision_critic.md`.
4. **Vision critic, deck level** (one call per round): a contact sheet of all slide PNGs (a 4×5 grid) → the same output format, restricted to the SlideAudit cross-slide categories the paper left out of its evaluation: inconsistent layout across slides, and content logical flow issues. Inconsistent visual style is checked again here across slides. "Lack of navigation" is skipped because the deck uses section slides instead.
5. **Student critic**: sees **only** slide text and notes (not the paper), with a persona "ML master's student who hasn't read this paper" → `{slide, confusion, undefined_term | missing_step | unclear_figure | forward_reference, severity, question_they_would_ask}`. Questions it would ask also seed the backup slides and Q&A prep.
6. **Author revises** using the automatic findings and both critiques. Each vision issue's `element_ids` are resolved to `source_line`s in `slides.md` via `elements.json`, so the author gets "lines 112–118: element 7 overflows; fix steps: …" instead of a vague description.
   - **High severity:** fixed automatically.
   - **Low severity:** fixed only if the fix doesn't break another rule; otherwise logged for the human step.
   - Human annotators in SlideAudit agreed only weakly (Fleiss' κ = 0.26), so low-severity design judgments are treated as advice, not requirements.
- Stop when there are zero high-severity issues of any kind, or after **3 rounds**.
- Output `qa.json`: issues per round by source (automatic / vision per-slide / vision deck / student) and by category. Used for the "critic loop works" chart.

### 7.8 Fact-check (local model)
- Step 1: a regex pulls every number, percentage and model or dataset name from `slides.md` and the notes.
- Step 2: the **local model** pairs each item with the claim it supports → `{slide, value, claim}` (JSON-schema structured output via Ollama).
- Step 3: Python checks each value **against the source cited for it in `deck.json`** (paper section, table or artifact CSV): exact match, or equal after rounding. Not a search of the whole paper, because small numbers would then match by accident.
- Output `factcheck.json` `{n_extracted, n_matched, unmatched[]}`. Unmatched items block export unless listed in `waivers.json` with a reason.
- Evaluate the local extractor against 30 hand-labelled numbers (precision/recall) for the workflow slide.

### 7.9 Judge
- `judges/checklist_gen.py`: paper-specific binary items (one per contribution, condition, main result, limitation, hard concept) merged with the static rubric (§10).
- `judges/score.py`: **one call per rubric dimension** (keeps cost low), temperature 0, strict JSON per item `{item_id, pass, evidence_slide, evidence_paper_quote, issue, suggested_fix}`. Two repeats (distinct `repeat_idx`); disagreements are flagged. Primary judge: Gemini 3.1 Pro (Gemini 3 Flash in dev). Second judge (optional, cheap): the DeepSeek reasoning model, on the final oneshot and full decks, to report how often the two judges agree.
- Bias controls: atomic items; a verbatim paper quote is required for any faithfulness pass; generator identity removed from inputs.
- Output `judge_report.json`: per-item results, dimension and total scores, hard-fail flag.
- The judge's feedback reaches the deck **only through the human step** (§7.10), and the pipeline comparison is scored **before** human edits. The judge never grades a deck it has steered.

### 7.10 Human + export
- Review `judge_report.json`; record accept/reject/modify per fix in `human_review.json`. Accepted fixes go back to the author (preferred) or are applied by hand as `manual:` commits.
- Export: `final/slides.pdf` (presenting copy), `final/slides-editable.pptx` (backup; fonts named, not embedded), `final/trace.html`, `final/pipeline.mmd`.

## 8. Skills (`skills/<name>/SKILL.md`)

Only the skills the stages need. Each one is short, specific and testable.

| Skill | Loaded by | Content |
|---|---|---|
| `paper-comprehension` | Digest, Difficulty map, Planner | How to read a paper for teaching: separate claims from evidence; find prerequisite gaps, jargon, metric definitions and counter-intuitive results; write an audience model; anchor everything; never fill a gap with invention. |
| `explanation-devices` | Difficulty map, Author | When to use which device. Worked example: for procedures and data transformations, always taken from real data. Analogy: for intuition only, must state where it breaks, never used for a number. Diagram: for structure and flow. Graph: for distributions and comparisons. Prior-work contrast: for "why is this new". One device per concept, no stacking. |
| `slide-design` (anti-slop) | Planner, Author, Vision critic, automatic checks | **Assertion–evidence structure:** the title is a full-sentence claim, and the body is the evidence (figure, diagram, example) rather than a bullet list. One idea per slide; ≤4 bullets of ≤12 words; ≤60 words; real figures with source captions; whitespace over decoration; varied layouts chosen to fit the content. **Banned:** emoji; icons as decoration; gradients, glows, drop shadows; stock images; three-card feature grids; titles like "Introduction", "Overview", "Key Takeaways", "Conclusion"; filler words and phrases ("delve", "unlock", "revolutionize", "game-changer", "in today's fast-paced", "seamless", "robust" used as praise); rhetorical-question titles; every slide built from bullets; bold scattered through sentences; dashes used as decoration. The banned word list is also a regex in `overflow_check.mjs`. **Each rule is tied to a SlideAudit category and the Gestalt principle it protects**, so the critic and the author use the same names. For example: ≤60 words → excessive text density (Proximity); one accent colour → overuse of colour (Similarity); 64 px margins → unbalanced space (Symmetry); grid alignment → misaligned elements (Continuity); claim title + one evidence block → visual hierarchy (Figure–Ground); no decorative icons → irrelevant visuals (Common Fate). The table lives in the skill. |
| `slidev-authoring` | Author | The theme's layouts and when to use each; image sizing; source-caption component; Mermaid embedding; notes syntax; fragments sparingly (at most a two-step reveal); what not to use. |
| `diagram-style` | Author | Mermaid conventions: ≤8 nodes, left-to-right flow, short labels, theme variables matching the deck tokens, one highlighted path in the accent colour, no decorative shapes. |
| `figure-replot` | Analyst | Shared matplotlib style: Okabe-Ito palette; labels on the lines instead of legends; tick labels ≥16 px at slide size; no grid clutter; SVG output; CSV written before every plot; caption string returned with the plot. |
| `speaker-notes` | Author | Spoken, not written, style; 120–180 words per slide, scaled to its minutes; one transition sentence into the next slide; numbers said the way they appear on the slide. |

Critic and judge prompts live in `prompts/` (not skills), because each is used by a single role. `prompts/vision_critic.md` holds the SlideAudit taxonomy (definitions + calibration notes) and cites the paper. `prompts/vision_critic_zeroshot.md` is the no-taxonomy version, kept only for the §5.2 comparison.

## 9. Design system (`deck/theme/` + `slide-design` skill)

- 16:9, 1280×720 logical px; 64 px outer margin; 12-column grid, 24 px gutters; 8 px spacing unit.
- Inter (or Source Sans 3) for text, JetBrains Mono for code. Title 40/600, subtitle 28, body 24, caption/source 16 (never smaller). Line height 1.3. Left-aligned.
- Text #1F2328 on #FAFAF7; one accent colour; Okabe-Ito for data. No gradients, glows, emoji, stock icons or decorative shapes.
- Layouts (the only ones allowed): `title`, `claim-figure` (title + one large figure + caption), `claim-two-figures` (side by side, e.g. paper vs. our re-plot), `claim-diagram`, `claim-example` (a worked example rendered as a chat transcript, turn by turn), `claim-bullets` (used sparingly), `claim-number` (one big number + context line), `section`, `workflow`.
- Every figure carries a source caption: "Laban et al., 2025, Fig. N" or "Our analysis, artifacts/X.csv".
- 12–18 main slides + 3–5 backup slides. The final main slide is Tools & Workflow.

## 10. Rubric (100 points, binary items with evidence)

| Dimension | Item | Pts |
|---|---|---|
| Faithfulness (25) | F1 every number matches the paper or an artifact (number + page/table/CSV listed) | 10 |
| | F2 no claim absent from or contradicting the paper | 10 |
| | F3 figures reproduced or re-plotted without distortion | 5 |
| Explanation (20) | E1 every hard concept in the checklist is explained before it is used | 8 |
| | E2 each explanation device is appropriate and correct (an analogy states its limits; examples come from real data) | 6 |
| | E3 metrics (aptitude, unreliability) can be understood from the slides alone | 6 |
| Coverage (20) | C1 problem and motivation | 3 |
| | C2 each stated contribution | 6 |
| | C3 all five conditions and the key design choices | 4 |
| | C4 headline result with number | 3 |
| | C5 limitations incl. the dated-models critique; prior work positioned | 4 |
| Narrative & timing (15) | N1 titles alone tell the story | 5 |
| | N2 logical order, no undefined forward references | 4 |
| | N3 12–18 main slides, notes 2,400–2,900 words, no slide over 2 min | 3 |
| | N4 clear takeaway | 3 |
| Design (10) | D1 density rules met and no banned patterns | 4 |
| | D2 consistent style; no overflow or misalignment (from `qa.json`) | 3 |
| | D3 figures readable at projection size | 3 |
| Beyond the paper (10) | B1 own analysis slide with a reproducible artifact | 5 |
| | B2 Tools & Workflow slide accurate and complete | 5 |

Hard gate: any F1 or F2 failure fails the deck until fixed.

## 11. Beyond the paper

**B-core (must): re-plot.** The analyst re-plots one paper figure from the released data; the slide shows the paper figure and our version side by side (`claim-two-figures`).

**B-core (must): explanatory graph.** The aptitude/unreliability illustration (§6) built from real per-run scores in the released data.

**B-core (must): validating the vision critic on SlideAudit.** The §5.2 check doubles as a small replication of a second paper:
- a 2×2 table of critic model × prompt (no taxonomy vs. full taxonomy), giving macro P/R/F1 on 50 human-labelled slides, next to the paper's Table 1 values;
- presented on a backup slide, with one line on the Tools & Workflow slide ("vision critic F1 = X on SlideAudit sample; paper's best 0.655");
- limitations stated: n = 50, newer models than the paper's, low agreement between the paper's human annotators (κ = 0.26).

**Experiment A (stretch, cap $2): are newer models still lost?**
- Use `microsoft/lost_in_conversation`; patch it minimally to accept an OpenRouter base URL if needed, recorded in `experiments/lost_in_conv/PATCHES.md`.
- Settings FULL vs. SHARDED; 2 tasks with deterministic graders (e.g. math and database; confirm the evaluators run, in WSL if needed); 10 instructions × 5 runs each, so unreliability can be computed; tested model: a DeepSeek chat model (cheap, recent; a natural answer to the "dated models" critique) or Gemini 3 Flash; user simulator and answer classifier: a DeepSeek chat model.
- Output: `results/*.csv`, a plot via the analyst, and a table of the paper's numbers next to ours. Presented as a small test whose outcome we didn't know in advance, with its sample size stated.

**Pipeline comparison (must):** `--config oneshot` (one Sonnet prompt: paper → Slidev deck) vs. `--config full`, both judged before human edits, 2 repeats each, by the same judge. Report total and per-dimension scores, F1 failures, overflow count, cost and time. Also report critic issues per round from `qa.json`. State the limitation: an LLM judging LLM output, n = 1 deck per config.

## 12. Tools & Workflow slide

- `pipeline.mmd` rendered as a diagram, with the model at each stage (generated from the run, not hand-drawn).
- Three to five numbers: total cost, model calls, wall-clock time, critic issues in round 1 vs. the final round, oneshot vs. full score, vision-critic F1 on SlideAudit, manual commits.
- Harness in one line: own orchestrator + skills + tools + DeepPresenter-style two-critic loop with a SlideAudit-taxonomy vision critic; PydanticAI for typed calls; local 3–4B fact-checker (precision/recall).
- Repo URL + QR code.
- Detail (rejected alternatives such as OpenClaw and Paper2Slides, model-selection results, sandbox) goes on a backup slide so the main slide stays within the density rules.

## 13. Repository layout

```
papertrail/   (GitHub: PAPERTRAIL-From-Paper-to-Podium)
├── README.md                     # one-command reproduction, results, cost
├── pyproject.toml   .env.example (OPENROUTER_API_KEY=)
├── config/{models.yaml, budget.yaml, rubric.yaml, model_selection.md}
├── pipeline.py
├── common/{llm.py, budget.py, schemas.py, skills.py, trace.py}
├── stages/{ingest,digest,difficulty,prior_work,plan,analyze,author,render_loop,factcheck,judge,export}.py
├── tools/{python_exec.py, dataset.py, scholar.py, render.py, mermaid_check.py}
├── skills/{paper-comprehension,explanation-devices,slide-design,slidev-authoring,diagram-style,figure-replot,speaker-notes}/SKILL.md
├── prompts/{vision_critic.md, vision_critic_zeroshot.md, vision_critic_deck.md, student_critic.md, judge_dimension.md, oneshot.md}
├── judges/{checklist_gen.py, score.py}
├── local/ollama_client.py
├── report/trace_page.py
├── qa/{overflow_check.mjs, element_map.mjs, contact_sheet.py}
├── deck/{package.json, theme/{tokens.css, layouts/*.vue, components/SourceCaption.vue}, slides.md}
├── experiments/lost_in_conv/{runner.py, PATCHES.md, results/, plot.py}
├── compare/{run_compare.py, critic_eval.py, slideaudit_sample.json, summary.md}
├── data/slideaudit/              # downloaded sample only (not committed if the license forbids it)
└── runs/<ts>/{paper.md, digest.json, difficulty_map.json, prior_work.json, plan.json, artifacts/, deck.json,
              render/, qa.json, factcheck.json, judge_report.json, human_review.json, trace.jsonl, cost.json, trace.html, final/}
```

## 14. Plan

**Mon 2026-10-12: sign up for the slot today (deadline).**

**Day 1, Mon Oct 12 (core):**

| Time | Task | Done when |
|---|---|---|
| Block 1 (1 h) | Repo, git init, `.env`, OpenRouter credit limit; `ollama pull` a 3–4B model; confirm slugs; Slidev project + theme skeleton | `slidev export` renders a dummy deck |
| Block 2 (1 h) | `common/` (llm, budget, cache with repeat_idx, trace, skills loader, schemas) | a test call is traced and costed |
| Block 3 (1 h) | Ingest + Digest; free-model selection check (§5.2) | `digest.json` valid with anchors |
| Block 4 (1.5 h) | Difficulty map (+ `dataset_lookup`), prior work (+ `scholar`), plan | `plan.json` covers every hard concept |
| Block 5 (1.5 h) | Author + skills (`slide-design`, `slidev-authoring`, `diagram-style`, `speaker-notes`) + `mermaid_check` → deck v0 | `slides.pdf` renders |
| Block 6 (2 h) | Render loop: `element_map` + automatic checks (incl. contrast) + per-slide and deck-level vision critic (taxonomy prompt) + student critic | `qa.json` shows issues falling across rounds |

**Day 2, Tue Oct 13:** Analyze (`python_exec` sandbox, `figure-replot`): re-plot + explanatory graph; SlideAudit critic check (§5.2) → choose the critic; judge + one Sonnet full run; trace page, workflow slide, README.
**Wed–Thu (Oct 14–15):** local fact-checker + 30-label evaluation; oneshot vs. full comparison; human review with `manual:` commits; Experiment A if budget and time allow.
**Fri–Sun (Oct 16–18):** freeze the deck; rehearse twice (one timed, with Q&A from the student critic's questions).

**Minimum viable version** (if time runs short): ingest → digest → difficulty map → plan → author → render loop (automatic checks + vision critic) → judge → human edits, plus trace page and workflow slide, plus the oneshot vs. full comparison.

## 15. Acceptance criteria

1. `python pipeline.py --config full --paper <arXiv ID or PDF>` produces `final/slides.pdf` with 12–18 main slides, notes on every slide, and the Tools & Workflow slide last, with no manual steps except §7.10.
2. Every concept in `difficulty_map.json` is explained on a slide (or deferred to backup with a reason), and the final round of the student critic has no high-severity confusions.
3. Zero high-severity QA issues in the final round; no overflow; no text under 16 px; no banned patterns.
4. Zero unmatched numbers in `factcheck.json`, or each one waived with a reason.
5. Judge total ≥ 85/100 with no F1/F2 failures.
6. Oneshot vs. full comparison table complete with cost and time; the SlideAudit critic table (2×2, macro P/R/F1) complete.
7. Total spend ≤ $10; `cost.json` accounts for every call.
8. A clean clone plus the README reproduces the deck.

## 16. Risks

| Risk | Mitigation |
|---|---|
| Free models rate-limited or weaker | §5.2 check; automatic paid fallback per role; response cache |
| Hallucinated numbers | Anchors in digest and `deck.json`; analyst never types numbers; anchor-scoped fact-check; F1 hard gate |
| Generic, "AI-looking" slides | `slide-design` skill with banned list enforced by regex and the vision critic; assertion–evidence layouts only |
| Explanations that don't land | Difficulty map + student critic loop; rubric dimension E |
| Vision critic flags problems on fine slides, causing needless revisions | SlideAudit taxonomy + calibration notes + "return [] if none"; only high severity is fixed automatically; critic chosen by measured F1 |
| Critic issues can't be traced back to the markdown | Element IDs on the annotated PNG → `source_line` in `elements.json` |
| Wrong or invented prior work | Restricted to paper references or Semantic Scholar IDs that can be checked |
| Judge leniency or bias | Cross-vendor; atomic items; required quotes; two real repeats; judge kept out of the loop; second judge possible later |
| Prompt injection via PDF or Scholar text | Treated as data; only the analyst executes code, sandboxed without secrets |
| 4 GB GPU too slow | 3–4B Q4 model; CPU fallback is acceptable for extraction; free API fallback stated on the slide |
| Slidev export quirks | PDF is the presenting copy; pptx only a backup |
| Running out of time today | MVP cut line (§14); stretch work moves to Mon–Thu |

## 17. To verify during setup

- OpenRouter slugs and prices: Sonnet 5.5, Haiku 5.5, Gemini 3 Flash, Gemini 3.1 Pro; current DeepSeek chat and reasoning models (and whether `:free` versions exist, their context length and tool-calling support); current free models with tool calling, vision and ≥128k context.
- OpenRouter free-model daily limits for this account, and whether usage cost is returned per response.
- WSL available for `unshare -rn`; `lost_in_conversation` evaluators for the chosen tasks run there.
- Semantic Scholar API works without a key at our call volume.
- Whether the released data includes per-run scores (needed for the explanatory graph); otherwise use our Experiment A runs or a paper table.
- SlideAudit dataset (github.com/zhuohaouw/SlideAudit): license, download format, whether per-annotator labels and element lists are included, and how its category names map to the 19 used in §7.7.
