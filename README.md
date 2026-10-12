# paper2deck

An agent harness that reads a research paper, works out what is hard to understand in it and how best to explain each part, and produces a conference-style Slidev deck. The rendered slides are critiqued by a vision model and a "confused student" model, the numbers are fact-checked by a local model, and the deck is scored by a judge from a different vendor.

Built for a course presentation of **LLMs Get Lost In Multi-Turn Conversation** (Laban et al., ICLR 2026 Outstanding Paper, arXiv:2505.06120).

> **Status:** in development. The full design is in [SPEC.md](SPEC.md); progress is in [Tasks.md](Tasks.md). Sections marked *(planned)* describe the intended result before it exists.

## How it works

```
paper (arXiv ID or PDF)
  → ingest        paper.md with page anchors, figures, tables, references
  → digest        contributions and claims, each anchored to a page/table/figure
  → difficulty    hard concepts + the best way to explain each
                  (worked example from real data, analogy, diagram, graph, prior work)
  → prior work    3–5 related works via Semantic Scholar
  → plan          12–18 slides, each title a full-sentence claim
  → analyze       re-plots and explanatory graphs from the released data (sandboxed Python)
  → author        Slidev markdown, Mermaid diagrams, speaker notes, claim→source map
  → render loop   render → automatic checks → vision critic (SlideAudit taxonomy)
                  + student critic → revise   (up to 3 rounds)
  → fact-check    local model extracts numbers; Python checks each against its cited source
  → judge         rubric scoring with verbatim paper quotes as evidence
  → human review  accepted fixes; every manual edit is its own git commit
  → export        slides.pdf, editable pptx, trace page
```

**Harness.** Our own Python state machine (`pipeline.py`) owns the stages, the critic loop, skills, tools, budget and tracing. PydanticAI is used only for typed LLM calls. Every stage writes inspectable files to `runs/<timestamp>/`, and each run produces `trace.html` showing what every stage did, which model ran it, and what it cost.

**Prior work we build on.** The revision loop follows DeepPresenter's render → critique → revise pattern. The vision critic uses the design-flaw taxonomy and evaluation method from SlideAudit (Zhang et al., UIST 2025).

**Models** (all through OpenRouter, roles set in `config/models.yaml`):

| Role | Model |
|---|---|
| Difficulty map, planning, authoring | Claude Sonnet 5.5 |
| Paper digest, prior work, student critic, analysis, checklist | DeepSeek and free open-weight models |
| Vision critic | Gemini 3 Flash or a free vision model, chosen by measured F1 on SlideAudit |
| Judge | Gemini 3.1 Pro (optional second judge: DeepSeek reasoning model) |
| Fact extraction | local 3–4B model via Ollama |

## Setup

Requirements: Python 3.11+, Node 20+, Ollama, an OpenRouter API key. On Windows, WSL2 is used for the code sandbox.

```powershell
git clone <repo-url>; cd Slide_maker
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
cd deck; npm install; cd ..
ollama pull <3-4B model from config/models.yaml>
copy .env.example .env   # then add OPENROUTER_API_KEY
```

## Usage *(planned)*

```powershell
# Full pipeline
python pipeline.py --config full --paper 2505.06120

# One-shot baseline for comparison
python pipeline.py --config oneshot --paper 2505.06120

# Cheap development run, a single stage, or resume from a stage
python pipeline.py --config full --paper 2505.06120 --dev
python pipeline.py --config full --paper 2505.06120 --only plan
python pipeline.py --config full --paper 2505.06120 --from-stage 6
```

Output: `runs/<timestamp>/final/slides.pdf`, plus `trace.html` and every intermediate file.

## Cost control

Budget caps are enforced in code (`config/budget.yaml`): $2 per run, $10 in total. Each call is checked before it is sent (worst case) and after (actual cost), and every response is cached on disk, so re-runs are free. `runs/<timestamp>/cost.json` accounts for every call.

## Results *(planned)*

- Oneshot vs. full pipeline: rubric scores, cost and time
- Vision-critic validation on SlideAudit: macro P/R/F1, with and without the taxonomy
- Critic issues per revision round
- Fact-check extractor precision/recall

## Repository layout

See [SPEC.md §13](SPEC.md). Key folders: `stages/` (one module per stage), `common/` (LLM layer, budget, schemas, trace), `tools/`, `skills/`, `prompts/`, `qa/`, `deck/` (Slidev project and theme), `compare/`, `runs/`.

## References

- Laban, Hayashi, Zhou, Neville. *LLMs Get Lost In Multi-Turn Conversation.* ICLR 2026. arXiv:2505.06120. Code and data: `microsoft/lost_in_conversation` (MIT).
- Zhang, Chen, Zhong, Wobbrock. *SlideAudit: A Dataset and Taxonomy for Automated Evaluation of Presentation Slides.* UIST 2025. arXiv:2508.03630.
- DeepPresenter (render → critique → revise loop for presentation generation).
