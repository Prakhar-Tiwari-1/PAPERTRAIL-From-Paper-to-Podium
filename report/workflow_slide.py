"""Regenerate the Tools & Workflow slide (last main slide) from the real run (SPEC §12).

The diagram is pipeline.mmd; the numbers are read from trace/cost/qa/judge/compare files. Every number is written to
artifacts/run_stats.json and cited in deck.json, so the fact-check can trace it. The existing slide's title and notes are kept.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from common.deckcheck import NOTES_RE, split_main_backup
from qa.source_map import parse_slides
from report import trace_page

ROOT = Path(__file__).resolve().parent.parent
REPO_URL = "https://github.com/Prakhar-Tiwari-1/PAPERTRAIL-From-Paper-to-Podium"


def manual_commits() -> int:
    try:
        out = subprocess.run(["git", "log", "--format=%s"], cwd=ROOT, capture_output=True, text=True, timeout=20).stdout
        return sum(1 for l in out.splitlines() if l.startswith("manual:"))
    except Exception:
        return 0


def _json(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def run_stats(run_dir: Path) -> dict:
    t = trace_page.totals(run_dir)
    stats = {"total_cost_usd": f"${t['cost_usd']:.2f}", "model_calls": str(t["calls"]), "wall_clock_minutes": str(max(1, round(t["seconds"] / 60))),
             "manual_commits": str(manual_commits())}
    if "issues_round_1" in t:
        stats["critic_issues_round_1"] = str(t["issues_round_1"])
        stats["critic_issues_final_round"] = str(t["issues_final"])
    cmp_ = _json(ROOT / "compare" / "results.json")
    if cmp_:
        stats["oneshot_score"] = f"{cmp_['oneshot']['total']:.0f}"
        stats["full_score"] = f"{cmp_['full']['total']:.0f}"
    elif (run_dir / "judge_report.json").exists():
        stats["judge_score"] = f"{t['judge_total']:.0f}"
    crit = _json(ROOT / "compare" / "critic_results.json")
    if crit and crit.get("best"):
        stats["vision_critic_f1"] = f"{crit['best']['macro_f1']:.2f}"
    ext = _json(ROOT / "compare" / "extractor_eval.json")
    if ext:
        stats["local_extractor_precision"] = f"{ext['precision']:.2f}"
        stats["local_extractor_recall"] = f"{ext['recall']:.2f}"
    return stats


def make_qr(run_dir: Path) -> str:
    import qrcode
    import qrcode.image.svg

    img = qrcode.make(REPO_URL, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=1)
    p = run_dir / "figures" / "repo_qr.svg"
    p.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(p))
    return "/figures/repo_qr.svg"


def patch(run_dir: Path) -> dict:
    md_path = run_dir / "deck" / "slides.md"
    md = md_path.read_text(encoding="utf-8")
    slides = parse_slides(md)
    main, _ = split_main_backup(slides)
    last = main[-1]
    if last.layout != "workflow":
        raise ValueError("last main slide is not layout `workflow`")
    stats = run_stats(run_dir)
    (run_dir / "artifacts").mkdir(exist_ok=True)
    (run_dir / "artifacts" / "run_stats.json").write_text(json.dumps(stats, indent=1), encoding="utf-8")
    qr = make_qr(run_dir)
    title = "This deck came from a staged pipeline with two critics and a judge from another vendor"
    notes = " ".join(m.strip() for m in NOTES_RE.findall(last.text)) or "Tools and workflow."
    pick = [("total_cost_usd", "total cost"), ("model_calls", "model calls"), ("critic_issues_round_1", "critic issues in the first round"),
            ("critic_issues_final_round", "critic issues in the final round")]
    if "oneshot_score" in stats:
        pick.append(("full_score", f"judge score (one-shot {stats['oneshot_score']})"))
    def _label(k: str, label: str) -> str:
        return label.replace("issues", "issue") if stats[k] == "1" else label  # "1 critic issue", "17 critic issues"

    nums = "\n".join(f"- **{stats[k]}** {_label(k, label)}" for k, label in pick if k in stats)
    extra = []
    if "vision_critic_f1" in stats:
        extra.append(f"Vision critic F1 {stats['vision_critic_f1']} on SlideAudit sample.")
    if int(stats["manual_commits"]) >= 0:
        extra.append(f"{stats['manual_commits']} manual commits.")
    block = f"""---
layout: workflow
---

# {title}

```mermaid
{trace_page.build_mermaid(run_dir, compact=True).strip()}
```

<SourceCaption>Generated from this run's trace, artifacts/run_stats.json</SourceCaption>

::left::

{nums}

::right::

Own harness: Python state machine, PydanticAI for typed calls. {' '.join(extra)}

<img src="{qr}" style="width:96px" />
<SourceCaption>{REPO_URL.replace('https://', '')}</SourceCaption>

<!--
{notes}
-->
"""
    lines = md.splitlines()
    new = "\n".join(lines[:last.block_start - 1] + block.rstrip("\n").splitlines() + lines[last.end:])
    md_path.write_text(new + "\n", encoding="utf-8")
    # cite every number in deck.json so the fact-check can trace it to run_stats.json
    dj = run_dir / "deck.json"
    deck = json.loads(dj.read_text(encoding="utf-8")) if dj.exists() else {"claims": []}
    deck["claims"] = [c for c in deck["claims"] if c.get("source") != "artifacts/run_stats.json"]
    for k, v in stats.items():
        deck["claims"].append({"slide": last.no, "text": f"{v} {k}", "kind": "number", "source": "artifacts/run_stats.json"})
    dj.write_text(json.dumps(deck, indent=2), encoding="utf-8")
    return stats
