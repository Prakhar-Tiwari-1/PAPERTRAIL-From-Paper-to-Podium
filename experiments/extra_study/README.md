# Extra study: where does the hivemind come from?

The paper (*Artificial Hivemind*, Jiang et al.) leaves open whether the cross-model similarity comes from pretraining or from post-training. This study measures response similarity at every training stage on small open models. It was run on Kaggle's free GPUs (2 x T4): no API keys, no cost.

| File | What it is |
|---|---|
| `notebook5cc2be13a5.ipynb` | The Kaggle notebook (code only; the saved copy has no outputs or figures). Replication of one row of the paper's Table 6, OLMo 2 1B at base, SFT, DPO and final, base vs instruct for Qwen2.5 1.5B and SmolLM2 1.7B, a second embedding model, a lexical metric, an LLM judge, and three decoding fixes. |
| `notebook5cc2be13a5.log` | The run log: the printed result tables. It is the data source of the slides. |
| `make_slide_data.py` | Parses the log, the notebook config and the paper's Table 6 into CSVs and SVG charts in a run's `artifacts/` folder. Nothing is typed by hand. |

```powershell
python experiments/extra_study/make_slide_data.py --run runs/<ts>     # writes runs/<ts>/artifacts/extra_*.csv and extra_*.svg
```

The deck cites these files ("Our analysis, artifacts/extra_*.csv"). A copy of the data and charts is in [`results/final-paper-2510.22954/extra-study/`](../results/final-paper-2510.22954/extra-study/).

## What the run found

- **Replication:** with an open embedding model (Qwen3-Embedding-0.6B) the similarity histogram of Qwen2.5-1.5B-Instruct has the same shape as the paper's Table 6 row (checked against the paper's table data).
- **By stage:** similarity rises from about 0.42 (OLMo 2 base) to about 0.77 (final); supervised fine-tuning adds most of it. Qwen2.5 and SmolLM2 jump the same way, and all three post-trained models end near 0.77.
- **Across families:** similarity between two families rises from about 0.5 for base models to about 0.73 for post-trained ones.
- **Decoding fixes:** temperature 1.5 lowers similarity to about the base level, but its answers average 761 words and 45% hit the token cap; min-p and asking for five answers in one call barely help.

## Caveats

- **The LLM judge failed** (both judge models, "judge: none"), so the planned check that base models do not look diverse merely by rambling was not done. The "valid share" columns in the log are meaningless (one to seven judged responses).
- A 64-word length control and a second embedding model (all-mpnet-base-v2) agree with the main measure in direction.
- The metaphor PCA of the original plan was not saved, so it is not on the slides.
