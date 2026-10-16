# Results

Outputs worth keeping from real runs (`runs/` itself is gitignored). Costs are in [COSTS.md](COSTS.md), computed from the ledger ([cost_ledger.jsonl](cost_ledger.jsonl)).

**Total spent on paid model calls: $9.93.**

| Run | Paper | Models | Judge score (Gemini) | Numbers fact-checked | Cost |
|---|---|---|---|---|---|
| `20261012-112632` (first attempt) | 2505.06120 (test paper) | cheapest `--dev` models | not kept | not kept | $1.51 |
| `20261012-181956` | 2505.06120 (test paper) | Claude author, Gemini judge | 95/100, hard fail: False | 68 of 68 matched | $4.73 |
| `20261015-155838` | 2510.22954 (final paper) | Claude author, Gemini judge | 64/100, hard fail: True | 112 of 112 matched | $3.69 |

## What is kept

- `test-paper-2505.06120/`: the **earliest surviving output**. The very first run (`20261012-112632`, 23 pages, flat look, cheapest models) was deleted at the owner's request on 2026-10-12; [docs/RUNLOG.md](../docs/RUNLOG.md) keeps its history and the ledger keeps its cost. This folder is the next run, on the same paper: the deck as exported (`final/`), the judge report and the fact-check. The PPTX (image-based, 6 MB) is not kept.
- `final-paper-2510.22954/model-generated/`: the final-paper deck **as the model made it**, at the end of the render loop (round 5), before the fact-check stage and before any human edit. `slides.md` is the source; `slides.pdf` is rebuilt from that round's slide images. The judge report scored this version (faithfulness 5, explanation 20, coverage 20, narrative 12, design 7, beyond 0; total 64, hard fail because faithfulness items F1 and F2 had no verbatim quote).
- `final-paper-2510.22954/final/`: the deck **as presented**: PDF, the PPTX (every slide is a picture; only the speaker notes are text), source, speaker script, trace page. What changed from the model's version is listed in [EDITS.md](final-paper-2510.22954/EDITS.md).
- `final-paper-2510.22954/extra-study/`: data and charts of the extra study (CSVs and SVGs produced by [`extra_study/make_slide_data.py`](../extra_study/make_slide_data.py)), which the four extra slides cite.

The judge scored only the model-generated version. The edits and the four extra slides were made by hand afterwards, so the score does not describe the presented deck.
