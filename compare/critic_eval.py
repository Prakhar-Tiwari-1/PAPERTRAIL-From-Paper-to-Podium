"""Choose the vision critic by measured F1 on a SlideAudit sample (SPEC §5.2, §11).

Grid: {Gemini 3 Flash, best free vision model} x {no-taxonomy prompt, full-taxonomy prompt}; 50 slides (cost <= $1).
Input per slide: image (+ our numbered element boxes when the dataset has elements) + element list. Metric: macro P/R/F1 over the paper's
19 categories. The paper's best (GPT-4o, 0.655) is reported next to ours; the models differ, so the comparison is indicative only.

    python -m compare.critic_eval --prepare            # download the 50-slide sample (CC BY 4.0)
    python -m compare.critic_eval --run [--n 50]       # run the 2x2 grid -> compare/critic_results.json + critic_results.md
"""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

from common.ctx import ROOT
from common.llm import Harness, RoleConfig
from common.repair import fill, load_prompt
from common.schemas import VisionReport
from compare import slideaudit_data as sa
from compare.metrics import macro_prf
from qa.contact_sheet import annotate

PAPER_BEST = {"model": "GPT-4o (SlideAudit paper, full taxonomy)", "macro_f1": 0.655}
MODELS = {"gemini-3-flash": "google/gemini-3-flash-preview", "free-vision": "google/gemma-4-31b-it:free"}
PROMPTS = {"no-taxonomy": "vision_critic_zeroshot.md", "full-taxonomy": "vision_critic.md"}


class Mapping(BaseModel):
    mapped: list[str]


MAP_PROMPT = """Map each AI-identified slide-design issue below to the BEST matching category from this list, or drop it if none fits.
Categories: {cats}
Issues (category as named by the AI | description):
{issues}
Return JSON {{"mapped": [<category names from the list, one per issue that fits, no duplicates>]}}."""


def predicted_categories(h: Harness, report: VisionReport, taxonomy: bool) -> set[str]:
    if taxonomy:  # category names come from our prompt: deterministic mapping
        return {c for c in (sa.canon_name(i.category) for i in report.issues) if c}
    if not report.issues:
        return set()
    rows = "\n".join(f"- {i.category} | {i.issue}" for i in report.issues)
    m = h.call("category_mapper", MAP_PROMPT.format(cats=json.dumps(sa.CANON), issues=rows), output_type=Mapping)
    return {c for c in m.mapped if c in sa.CANON}


def run_grid(n: int = 50, repeat_budget_usd: float = 1.0) -> dict:
    sample = json.loads(sa.SAMPLE.read_text(encoding="utf-8"))["slides"][:n]
    run_dir = ROOT / "runs" / "_critic_eval"
    h = Harness(run_dir)
    h.budget.caps = {**h.budget.caps, "per_run_usd": repeat_budget_usd}
    results = {}
    with tempfile.TemporaryDirectory() as td:
        for mname, slug in MODELS.items():
            h.roles[f"eval_{mname}"] = RoleConfig(f"eval_{mname}", slug, slug, "google/gemini-3-flash-preview", 0.0, 4000, [], True)
            h.prices.setdefault(slug, (0.0, 0.0) if slug.endswith(":free") else (0.5, 3.0))
            for pname, pfile in PROMPTS.items():
                template = load_prompt(pfile)
                truth, pred = [], []
                for s in sample:
                    els = sa.elements_for(s["id"])
                    png = Path(td) / f"{s['id']}_{mname}.png"
                    ann = annotate(sa.DATA / "images" / f"slide_{s['id']:04d}.png", els, png)
                    names = "\n".join(f"{e['id']}: {e['type']} \"{e['text_excerpt'][:40]}\"" for e in els)
                    rep = h.call(f"eval_{mname}", fill(template, slide_no=s["id"], elements=names), output_type=VisionReport,
                                 images=[ann.read_bytes()])
                    truth.append(set(s["labels"]))
                    pred.append(predicted_categories(h, rep, taxonomy=(pname == "full-taxonomy")))
                m = macro_prf(truth, pred, sa.CANON)
                results[f"{mname} | {pname}"] = {k: m[k] for k in ("macro_precision", "macro_recall", "macro_f1")}
    best_key = max(results, key=lambda k: results[k]["macro_f1"])
    out = {"n_slides": len(sample), "grid": results, "best": {"config": best_key, **results[best_key]}, "paper_best": PAPER_BEST,
           "limitations": "n=50; newer models than the paper's; human annotators agreed only weakly in the paper (Fleiss kappa 0.26); "
                          "positive label = annotation `response: true` (assumption)"}
    (ROOT / "compare" / "critic_results.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    rows = "\n".join(f"| {k} | {v['macro_precision']:.3f} | {v['macro_recall']:.3f} | {v['macro_f1']:.3f} |" for k, v in results.items())
    (ROOT / "compare" / "critic_results.md").write_text(
        f"# Vision critic on SlideAudit ({len(sample)} slides)\n\n| config | macro P | macro R | macro F1 |\n|---|---|---|---|\n{rows}\n\n"
        f"Best: **{best_key}** (F1 {out['best']['macro_f1']:.3f}). Paper's best: {PAPER_BEST['model']} F1 {PAPER_BEST['macro_f1']}.\n\n"
        f"Limitations: {out['limitations']}\n", encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prepare", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--n", type=int, default=50)
    a = ap.parse_args()
    load_dotenv(ROOT / ".env")
    if a.prepare:
        s = sa.build_sample(a.n)
        print(f"sample of {len(s)} slides written to {sa.SAMPLE}")
    if a.run:
        print(json.dumps(run_grid(a.n), indent=1))


if __name__ == "__main__":
    main()
