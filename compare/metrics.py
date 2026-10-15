"""Macro precision / recall / F1 over categories, as in SlideAudit (SPEC §5.2). A category is 'predicted' for a slide when the
critic reports at least one issue of that category; 'true' when the human label is positive."""
from __future__ import annotations


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def macro_prf(truth: list[set[str]], pred: list[set[str]], categories: list[str]) -> dict:
    per, ps, rs, fs = {}, [], [], []
    for c in categories:
        tp = sum(1 for t, p in zip(truth, pred) if c in t and c in p)
        fp = sum(1 for t, p in zip(truth, pred) if c not in t and c in p)
        fn = sum(1 for t, p in zip(truth, pred) if c in t and c not in p)
        p, r, f = prf(tp, fp, fn)
        per[c] = {"tp": tp, "fp": fp, "fn": fn, "precision": p, "recall": r, "f1": f}
        ps.append(p), rs.append(r), fs.append(f)
    n = len(categories)
    return {"macro_precision": sum(ps) / n, "macro_recall": sum(rs) / n, "macro_f1": sum(fs) / n, "per_category": per}
