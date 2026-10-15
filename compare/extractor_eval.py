"""Evaluate the local fact extractor against 30 hand-labelled numbers (SPEC §7.8): precision / recall for the workflow slide.

The labels are written by a person (not by a model): compare/factlabels.json =
  [{"slide_md": "<markdown of one slide>", "numbers": ["39%", "200,000", ...]}, ...]   # the numbers a careful reader would check
Run: python -m compare.extractor_eval [--template]   (--template writes factlabels.template.json from the current deck for you to correct)

The extractor under test = stage 1 regex + the local model's pairing; a number counts as 'found' if it appears in the pairs returned.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from common.ctx import ROOT, RunCtx
from common.llm import Harness
from common.schemas import NumberPairs
from qa.source_map import parse_slides
from stages import factcheck as fc


def evaluate(ctx: RunCtx, labels: list[dict]) -> dict:
    tp = fp = fn = 0
    for item in labels:
        slide = parse_slides(item["slide_md"])[0]
        found = fc.extract_numbers(slide)
        res = ctx.h.call("fact_extractor", fc.PROMPT.format(items=json.dumps(found, ensure_ascii=False)), output_type=NumberPairs)
        got = {p.value for p in res.pairs} & {f["value"] for f in found}
        want = set(item["numbers"])
        tp += len(got & want)
        fp += len(got - want)
        fn += len(want - got)
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": p, "recall": r, "tp": tp, "fp": fp, "fn": fn, "n_labelled": sum(len(i["numbers"]) for i in labels)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", default=None)
    ap.add_argument("--template", action="store_true")
    a = ap.parse_args()
    load_dotenv(ROOT / ".env")
    runs = sorted(p for p in (ROOT / "runs").iterdir() if p.is_dir() and not p.name.startswith("_"))
    run_dir = Path(a.run_dir) if a.run_dir else runs[-1]
    if a.template:
        slides = parse_slides((run_dir / "deck" / "slides.md").read_text(encoding="utf-8"))
        out = [{"slide_md": s.text, "numbers": [n["value"] for n in fc.extract_numbers(s)]} for s in slides if fc.extract_numbers(s)]
        (ROOT / "compare" / "factlabels.template.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
        print("wrote compare/factlabels.template.json: correct it by hand (remove wrong numbers, add missed ones), save as factlabels.json")
        return
    labels = json.loads((ROOT / "compare" / "factlabels.json").read_text(encoding="utf-8"))
    ctx = RunCtx(run_dir=run_dir, paper="", config="full", h=Harness(run_dir))
    res = evaluate(ctx, labels)
    (ROOT / "compare" / "extractor_eval.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(res)


if __name__ == "__main__":
    main()
