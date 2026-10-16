# papertrail — From Paper to Podium

*Agentic slide generation inspired by [DeepPresenter](#references) and [SlideAudit](https://arxiv.org/abs/2508.03630).*

An agent harness that reads a research paper, works out what is hard to understand in it and how best to explain each part, and produces a conference-style Slidev deck. The rendered slides are critiqued by a vision model and a "confused student" model, the numbers are fact-checked by a local model, and the deck is scored by a judge from a different vendor.

Built for a three-person course presentation (CSC_53432_EP, Large Language Models: 20 min talk + 5 min Q&A). The pipeline is **paper-independent**: give it any arXiv ID or PDF. `2505.06120` was only the test paper.

> **Status:** the pipeline is built and passes 114 offline tests and a full fake-model end-to-end run (real Slidev rendering, QA and export) for a paper with a profile and for an unknown paper without one. It has had real runs on the test paper and one on the final paper (arXiv:2510.22954); the decks, the judge reports and the cost are in [results/](results/README.md). The full design is in [SPEC.md](SPEC.md); progress is in [Tasks.md](Tasks.md); the dated record of real runs is [docs/RUNLOG.md](docs/RUNLOG.md). Sections marked *(planned)* describe results that do not exist yet.

## How it works

```
paper (arXiv ID or PDF)
  → ingest        paper.md with page anchors, figures, tables, references
  → digest        contributions and claims, each anchored to a page/table/figure
  → difficulty    hard concepts + the best way to explain each
                  (worked example from real data, analogy, diagram, graph, prior work)
  → prior work    3–5 related works via Semantic Scholar
  → plan          13–16 main slides (about 15+ minutes of speech), each title a full-sentence claim
  → analyze       re-plots and explanatory graphs from the paper's data (sandboxed Python)
  → quiz          6 questions with answers (3 concept, 3 what-if), one quiz slide
  → style         optional: design moves from your reference slides (never copied)
  → author        Slidev markdown, Mermaid diagrams, speaker notes, claim→source map
  → render loop   render → automatic checks (word count, empty space, overlap) → vision critic
                  (SlideAudit taxonomy) + student critic → per-slide revision (up to 3 rounds)
  → fact-check    local model extracts numbers; Python checks each against its cited source
  → judge         rubric scoring with verbatim paper quotes as evidence
  → style compare optional: our deck vs. your reference slides, same features
  → human review  accepted fixes; every manual edit is its own git commit
  → export        slides.pdf, editable pptx, speaker script, trace page
```

**Harness.** Our own Python state machine (`pipeline.py`) owns the stages, the critic loop, skills, tools, budget and tracing. PydanticAI is used only for typed LLM calls. Every stage writes inspectable files to `runs/<timestamp>/`, and each run produces `trace.html` showing what every stage did, which model ran it, and what it cost.

**Prior work we build on.** The revision loop follows DeepPresenter's render → critique → revise pattern. The vision critic uses the design-flaw taxonomy and evaluation method from SlideAudit (Zhang et al., UIST 2025).

**Models** (all through OpenRouter, roles set in `config/models.yaml`):

| Role | Model |
|---|---|
| Difficulty map, planning, authoring, per-slide revision | Claude Sonnet 5.5 |
| Paper digest, prior work, student critic, analysis, quiz, checklist | DeepSeek and free open-weight models |
| Vision critic, reference-style analysis | Gemini 3 Flash (confirm with `compare.critic_eval`) |
| Judge | Gemini 3.1 Pro (optional second judge: DeepSeek reasoning model) |
| Fact extraction | local 3–4B model via Ollama |

## Setup

Requirements: Python 3.11+, Node 20+, an OpenRouter API key, Ollama (for the local fact-check stage). WSL2 with a Linux distro is optional (see Sandbox).

```powershell
git clone https://github.com/Prakhar-Tiwari-1/PAPERTRAIL-From-Paper-to-Podium.git
cd PAPERTRAIL-From-Paper-to-Podium
py -3.13 -m venv .venv; .\.venv\Scripts\Activate.ps1      # any Python >= 3.11
pip install -e ".[dev]"
cd deck; npm install; npx playwright install chromium; cd ..
ollama pull qwen3:4b                                       # local fact extractor (slug in config/models.yaml)
copy .env.example .env                                     # then add OPENROUTER_API_KEY
pytest                                                     # offline tests, no key needed
```

### API keys

| Variable | Needed? | Where to get it |
|---|---|---|
| `OPENROUTER_API_KEY` | **Required** (all hosted models: Claude, Gemini, DeepSeek, free models) | https://openrouter.ai/keys. Add credit at https://openrouter.ai/credits (about $10) and set a credit limit on the key. |
| `SEMANTIC_SCHOLAR_API_KEY` | Optional (works without a key at our volume) | https://www.semanticscholar.org/product/api#api-key-form |
| `OLLAMA_HOST` / `OLLAMA_MODEL` | No key. Only if Ollama is not at `http://localhost:11434` | https://ollama.com/download |

No other keys are used. Slidev, Playwright, the Semantic Scholar API (keyless) and the SlideAudit and lost_in_conversation datasets are free and need no account.

## Usage

```powershell
# Full pipeline
python pipeline.py --config full --paper <arxiv-id, or the path to a PDF>

# One-shot baseline for comparison, then the comparison table
python pipeline.py --config oneshot --paper <arxiv-id>
python -m compare.run_compare --full runs/<full run dir>

# Cheap development run, a single stage, or resume from a stage
python pipeline.py --config full --paper <arxiv-id> --dev
python pipeline.py --config full --paper <arxiv-id> --only plan
python pipeline.py --config full --paper <arxiv-id> --run-dir runs/<ts> --from-stage 6

# Choose the vision critic by F1 on SlideAudit (50 slides, <= $1)
python -m compare.critic_eval --prepare
python -m compare.critic_eval --run

# Offline end-to-end run with scripted fake models (no key, no cost)
python tests/e2e_fake.py
```

Output: `runs/<timestamp>/final/slides.pdf`, plus the editable pptx, `speaker_script.md` (the words to say, per slide, with timings), `trace.html`, `pipeline.mmd` and every intermediate file. `--from-stage` and `--only` use the latest run unless `--run-dir` is given. Set `PAPERTRAIL_SECOND_JUDGE=1` to also score with the DeepSeek reasoning model and report judge agreement.

If numbers on the slides cannot be traced to their cited source, export stops. Fix the deck, or list the number in `runs/<ts>/waivers.json` as `[{"slide": 3, "value": "16", "reason": "..."}]`.

## Using another paper

The pipeline is paper-independent. Run it on any arXiv ID or PDF:

```powershell
python pipeline.py --config full --paper <arxiv-id, or the path to a PDF>
```

**Where does the paper go?** Easiest: pass the **arXiv ID**. The pipeline downloads the PDF and the LaTeX source (clean figures and tables) and the metadata (authors, year, venue) itself, so nothing needs to be placed in the folder. For a paper that is not on arXiv, put the PDF anywhere, for example `papers/my-paper.pdf` (PDFs in `papers/` are git-ignored), and pass its path: `--paper papers/my-paper.pdf`. The file name (without `.pdf`) becomes the paper id, so an optional profile for it is `papers/my-paper.yaml`. A PDF has no LaTeX source or metadata, so figures are cropped from the pages and the title-page citation needs `paper_citation` in a profile or in `deck/footer.json`.

Nothing else about the paper is needed in advance: the title-page citation and the caption citation are built from the arXiv metadata, the hard concepts are found by the difficulty stage, and the required slides are generic (motivation, method, result, prior work, limitations, our analysis, quiz, takeaway). If you know more, add an optional profile, `papers/<arxiv-id>.yaml` (copy `papers/default.yaml`): concepts you know are hard, extra required slides, critiques to put on the limitations slide, what-if directions for the quiz, a released dataset for worked examples, or a title-page citation override. `papers/2505.06120.yaml` is the profile of the test paper and shows every field.

## Reference slides (style examples)

Put slides you like in `references/slides/` (png, jpg, pdf). The pipeline studies them (`style`), gives the author a style brief, and at the end compares our deck with them on the same features (`style_compare`, also in `final/style_comparison.md`). They are never copied: the brief holds design moves only, and a near-copy guard flags any slide of ours that looks like one of them. See `references/README.md`.

## The quiz slide

One slide near the end asks six questions about the talk, three on concepts (left) and three what-ifs (right, such as "what if the temperature is zero?"), with the answers in a block below, revealed on click in the live talk and all visible in the PDF. The questions come from `stage quiz` and are checked against the paper like every other number.

## Footer, title page and watermark

Edit `deck/footer.json`: logo, course code and name, page number on or off, the layouts that hide the footer, presenter names, paper citation, date, the title-page photo and its shading (`title_shade`, 0 to 1), the watermark image and position (`right` or `center`), and the image credit line. Set an image field to `null` to switch it off. Images live in `media/` (credits in `media/ATTRIBUTION.md`). The pipeline applies the file to every run; for the dev deck run `python -m tools.footer`.

## Sandbox

Only the analyst runs code (`tools/python_exec.py`). With a WSL distro (`PAPERTRAIL_WSL_DISTRO`) it runs under `unshare -rn` (no network). Without one, it falls back to a Windows subprocess with a stripped environment (no API keys), cwd = `artifacts/`, a 60 s timeout, sockets disabled and writes restricted to `artifacts/` by a Python-level guard. **This fallback is weaker isolation than `unshare`**: it blocks the accidental and the obvious, not a determined attacker.

## Cost control

Budget caps are enforced in code (`config/budget.yaml`): $10 per run, $16.25 in total (the owner's EUR 10 for the final-paper run plus the $6.25 already spent), where the total counts everything ever spent (ledger `runs/_spend.jsonl`; $9.93 so far, broken down in [results/COSTS.md](results/COSTS.md)). Each call is checked before it is sent (worst case) and after (actual cost), and every response is cached on disk, so re-runs are free. `runs/<timestamp>/cost.json` accounts for every call. A full run with per-slide revision is estimated at about $2.5 to 3. The caps are the owner's decision: raise `total_usd` in `config/budget.yaml` before a run that needs more.

## Results

Full detail, files and costs: [results/README.md](results/README.md).

- **Test paper** (run `20261012-181956`, $4.73): judge score 95/100, no hard fail; all 68 numbers fact-checked.
- **Final paper** (run `20261015-155838`, $3.69): judge score 64/100 with a hard fail (faithfulness items F1 and F2 had no verbatim quote; no own-analysis slide with an artifact); all 112 numbers fact-checked. The presented deck was then edited by hand and extended with four slides from an extra study (listed in [results/final-paper-2510.22954/EDITS.md](results/final-paper-2510.22954/EDITS.md)), so that score does not describe it.
- **Extra study** ([extra_study/](extra_study/)): on small open models the response similarity rises from about 0.42 for a base model to about 0.77 after post-training, mostly at the first fine-tuning step; the LLM judge of that study failed, so base-model diversity may be inflated by off-task text.
- *(planned, not run)* Oneshot vs. full pipeline comparison; vision-critic validation on SlideAudit (macro P/R/F1); fact-check extractor precision/recall.

## Repository layout

See [SPEC.md §13](SPEC.md) for the design. In short:

```
pipeline.py          the state machine (stages in stages/, one module each)
stages/ common/      stage code; LLM layer, budget guard, schemas, trace
tools/ qa/ report/   helpers (render, plots, footer, cost report); slide checks; trace page, quiz and workflow slides
compare/ judges/     oneshot comparison and critic evaluation; rubric judge
skills/ prompts/     markdown instructions injected into stage prompts
config/              models, budget, rubric
deck/ media/         Slidev project and theme; images and their credits
papers/ references/  per-paper profiles (the paper PDFs are local); example slides (local)
extra_study/         the owner's extra experiment (Kaggle notebook, log) and the script that makes slide data from it
results/             archived outputs and costs of real runs (tracked)
docs/                run log, the SlideAudit paper, plans
tests/               offline tests and the fake-model end-to-end run
runs/                every run's working files (gitignored)
```

## References

- Test paper for development: Laban et al., *LLMs Get Lost In Multi-Turn Conversation*, arXiv:2505.06120 (profile in `papers/2505.06120.yaml`). The presented paper is chosen per run.
- Zhang, Chen, Zhong, Wobbrock. *SlideAudit: A Dataset and Taxonomy for Automated Evaluation of Presentation Slides.* UIST 2025. arXiv:2508.03630.
- DeepPresenter (render → critique → revise loop for presentation generation).
