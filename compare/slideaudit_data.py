"""SlideAudit sample for the vision-critic check (SPEC §5.2, §17). Dataset: github.com/zhuohaouw/SlideAudit, CC BY 4.0
(Zhang et al., UIST 2025; attribution required, we only use it for evaluation and do not commit it: data/slideaudit/ is gitignored).

Label rule (assumption to verify, noted in config/model_selection.md): a category is a positive label for a slide when the dataset's
annotation has `response: true` (the aggregated annotator answer).
"""
from __future__ import annotations

import json
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
RAW = "https://raw.githubusercontent.com/zhuohaouw/SlideAudit/main/data"
DATA = ROOT / "data" / "slideaudit"
SAMPLE = ROOT / "compare" / "slideaudit_sample.json"

# the 19 categories evaluated in the paper, with the dataset's spelling
CANON = [
    "Poor Visual Hierarchy", "Cluttered Layout", "Unbalanced Space Distribution", "Content Alignment Issues",
    "Content Overflow/Cut-off", "Occluded Content", "Illegible Typeface Selection or Usage", "Improper Font Sizing",
    "Excessive Text Volume", "Improper Text Styling", "Improper Line/Character Spacing", "Poor Text Hierarchy",
    "Insufficient Color Contrast for Readability", "Excessive or Inconsistent Color Usage",
    "Inappropriate or Mismatched Color Combinations", "Irrelevant Visual Content", "Poor Image Quality/Editing",
    "Improper Image Sizing", "Inconsistent Visual Style Usage",
]
# names used in prompts/vision_critic.md (the paper's wording) -> dataset spelling
ALIASES = {
    "Unbalanced Space Distribution or Gapping": "Unbalanced Space Distribution",
    "Object Alignment Issues": "Content Alignment Issues",
}


def canon_name(name: str) -> str | None:
    n = ALIASES.get(name.strip(), name.strip())
    return n if n in CANON else None


def _get(client: httpx.Client, path: str) -> bytes:
    r = client.get(f"{RAW}/{path}", timeout=60)
    r.raise_for_status()
    return r.content


def load_all_annotations(n: int = 2400, workers: int = 16) -> dict[int, list[str]]:
    """slide number -> list of positive canonical categories. Cached in data/slideaudit/annotations.json."""
    cache = DATA / "annotations.json"
    DATA.mkdir(parents=True, exist_ok=True)
    if cache.exists():
        return {int(k): v for k, v in json.loads(cache.read_text(encoding="utf-8")).items()}
    with httpx.Client(follow_redirects=True) as c:
        def one(i: int):
            d = json.loads(_get(c, f"annotations/slide_{i:04d}.json"))
            return i, [a["design_deficiency"] for a in d["annotations"] if a.get("response") and a["design_deficiency"] in CANON]

        with ThreadPoolExecutor(workers) as ex:
            res = dict(ex.map(one, range(1, n + 1)))
    cache.write_text(json.dumps(res), encoding="utf-8")
    return res


def stratified_sample(labels: dict[int, list[str]], n: int = 50, seed: int = 7) -> list[int]:
    """About a third each with 0-1, 2-3 and 4+ flaws (as in the paper)."""
    bins = {"0-1": [], "2-3": [], "4+": []}
    for i, cats in labels.items():
        k = len(cats)
        bins["0-1" if k <= 1 else "2-3" if k <= 3 else "4+"].append(i)
    rng = random.Random(seed)
    per = [n // 3 + (1 if j < n % 3 else 0) for j in range(3)]
    out = []
    for (name, ids), take in zip(bins.items(), per):
        out += rng.sample(sorted(ids), min(take, len(ids)))
    return sorted(out)


def build_sample(n: int = 50) -> list[dict]:
    """Download images + element descriptions for the sample; write compare/slideaudit_sample.json (ids and labels only)."""
    labels = load_all_annotations()
    ids = stratified_sample(labels, n)
    (DATA / "images").mkdir(parents=True, exist_ok=True)
    (DATA / "descriptions").mkdir(parents=True, exist_ok=True)
    with httpx.Client(follow_redirects=True) as c:
        for i in ids:
            img = DATA / "images" / f"slide_{i:04d}.png"
            if not img.exists():
                img.write_bytes(_get(c, f"images/slide_{i:04d}.png"))
            desc = DATA / "descriptions" / f"slide_{i:04d}.json"
            if not desc.exists():
                desc.write_bytes(_get(c, f"descriptions/slide_{i:04d}.json"))
    sample = [{"id": i, "labels": labels[i]} for i in ids]
    SAMPLE.write_text(json.dumps({"source": "github.com/zhuohaouw/SlideAudit (CC BY 4.0)", "slides": sample}, indent=1), encoding="utf-8")
    return sample


def elements_for(i: int) -> list[dict]:
    """Element list in our critic format: id, type, bbox [x, y, w, h] normalised, text_excerpt."""
    d = json.loads((DATA / "descriptions" / f"slide_{i:04d}.json").read_text(encoding="utf-8"))
    out = []
    for k, e in enumerate(d.get("elements", []), start=1):
        n = e.get("positionAndSize", {}).get("normalized")
        if not n:
            continue
        out.append({"id": k, "type": e.get("type", "ELEMENT").lower(), "bbox": [n["x"], n["y"], n["width"], n["height"]],
                    "text_excerpt": (e.get("textContent") or "").strip().replace("\n", " ")[:60]})
    return out
