"""trace.html (one card per stage) and pipeline.mmd (Mermaid diagram labelled with real models, calls and cost) (SPEC §4.1, §12).

The trace page is the demo for the professor; pipeline.mmd is the source of the Tools & Workflow slide.
"""
from __future__ import annotations

import html
import json
from collections import defaultdict
from pathlib import Path

STAGE_ORDER = ["ingest", "digest", "difficulty", "prior_work", "plan", "analyze", "author", "render_loop",
               "factcheck", "judge", "export", "oneshot"]
OUTPUTS = {"ingest": "paper.md", "digest": "digest.json", "difficulty": "difficulty_map.json", "prior_work": "prior_work.json",
           "plan": "plan.json", "analyze": "artifacts/analysis_notes.md", "author": "deck/slides.md", "render_loop": "qa.json",
           "factcheck": "factcheck.json", "judge": "judge_report.json", "oneshot": "deck/slides.md"}

# diagram nodes group stages (<= 8 nodes, left to right; skill diagram-style)
GROUPS = [
    ("Ingest", ["ingest"]),
    ("Understand", ["digest", "difficulty", "prior_work", "plan"]),
    ("Analyze", ["analyze"]),
    ("Author", ["author"]),
    ("Critic loop", ["render_loop"]),
    ("Fact-check", ["factcheck"]),
    ("Judge", ["judge"]),
    ("Export", ["export"]),
]


def read_trace(run_dir: Path) -> list[dict]:
    f = run_dir / "trace.jsonl"
    return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()] if f.exists() else []


def stage_stats(events: list[dict]) -> dict[str, dict]:
    st: dict[str, dict] = defaultdict(lambda: {"calls": 0, "cached": 0, "cost": 0.0, "in": 0, "out": 0, "seconds": 0.0,
                                               "models": defaultdict(int), "errors": 0, "fallbacks": 0})
    for e in events:
        s = st[e.get("stage", "")]
        if e.get("event") == "stage_end":
            s["seconds"] += e.get("seconds", 0)
        elif "model" in e and e.get("event") is None:
            if e.get("error"):
                s["errors"] += 1
                continue
            s["calls"] += 1
            s["cached"] += bool(e.get("cached"))
            s["cost"] += e.get("cost", 0) or 0
            s["in"] += e.get("in_tokens", 0) or 0
            s["out"] += e.get("out_tokens", 0) or 0
            s["models"][e["model"]] += 1
            s["fallbacks"] += bool(e.get("fallback_used"))
    return st


def short_model(m: str) -> str:
    return m.split("/")[-1].replace(":free", " (free)")


def build_mermaid(run_dir: Path, compact: bool = False) -> str:
    """compact=True: one dominant model and the call count per node, short enough for a 1280 px slide."""
    st = stage_stats(read_trace(run_dir))
    lines = ["flowchart LR", "  classDef base fill:#FAFAF7,stroke:#1F2328,color:#1F2328",
             "  classDef accent fill:#0B6E99,stroke:#0B6E99,color:#FFFFFF"]
    prev = None
    for i, (label, stages) in enumerate(GROUPS):
        calls = sum(st[s]["calls"] - st[s]["cached"] for s in stages if s in st)  # real model calls: cache hits cost nothing and are not counted
        cost = sum(st[s]["cost"] for s in stages if s in st)
        models = {}
        for s in stages:
            for m, n in (st[s]["models"] if s in st else {}).items():
                models[m] = models.get(m, 0) + n
        top = sorted(models, key=models.get, reverse=True)[: 1 if compact else 2]
        mtxt = ", ".join(short_model(m).replace("-preview", "") for m in top) or "no model"
        extra = (f"<br/>{calls} calls" if compact else f"<br/>{calls} calls, ${cost:.2f}") if calls else ""
        nid = f"n{i}"
        lines.append(f'  {nid}["{label}<br/>{mtxt}{extra}"]')
        lines.append(f"  class {nid} {'accent' if label == 'Critic loop' else 'base'}")
        if prev:
            lines.append(f"  {prev} --> {nid}")
        prev = nid
    return "\n".join(lines) + "\n"


def totals(run_dir: Path) -> dict:
    events = read_trace(run_dir)
    st = stage_stats(events)
    calls = sum(s["calls"] - s["cached"] for s in st.values())
    cost_json = run_dir / "cost.json"
    cost = json.loads(cost_json.read_text(encoding="utf-8"))["run_usd"] if cost_json.exists() else sum(s["cost"] for s in st.values())
    seconds = sum(s["seconds"] for s in st.values())
    out = {"calls": calls, "cost_usd": round(cost, 4), "seconds": round(seconds)}
    qa = run_dir / "qa.json"
    if qa.exists():
        q = json.loads(qa.read_text(encoding="utf-8"))
        out["issues_round_1"] = q["rounds"][0]["n_issues"]
        out["issues_final"] = q["rounds"][-1]["n_issues"]
        out["high_final"] = q["final_high"]
        out["rounds"] = q["rounds_run"]
    jr = run_dir / "judge_report.json"
    if jr.exists():
        out["judge_total"] = json.loads(jr.read_text(encoding="utf-8"))["total"]
    return out


def _preview(run_dir: Path, stage: str) -> str:
    rel = OUTPUTS.get(stage)
    if not rel or not (run_dir / rel).exists():
        return ""
    txt = (run_dir / rel).read_text(encoding="utf-8", errors="replace")
    return html.escape(txt[:1400] + ("\n..." if len(txt) > 1400 else ""))


def build_html(run_dir: Path) -> str:
    events = read_trace(run_dir)
    st = stage_stats(events)
    qa = json.loads((run_dir / "qa.json").read_text(encoding="utf-8")) if (run_dir / "qa.json").exists() else None
    tot = totals(run_dir)
    cards = []
    for name in [s for s in STAGE_ORDER if s in st]:
        s = st[name]
        models = ", ".join(f"{html.escape(short_model(m))} ×{n}" for m, n in s["models"].items()) or "no model (code only)"
        extra = ""
        if name == "render_loop" and qa:
            rows = "".join(f"<tr><td>{r['round']}</td><td>{r['n_issues']}</td><td>{r['n_high']}</td><td>{html.escape(json.dumps(r['by_source']))}</td></tr>" for r in qa["rounds"])
            extra = f"<table><tr><th>round</th><th>issues</th><th>high</th><th>by source</th></tr>{rows}</table>"
        cards.append(f"""<section class="card"><h2>{html.escape(name)}</h2>
<p class="meta">{models} · {s['calls']} calls ({s['cached']} cached) · {s['in']:,} in / {s['out']:,} out tokens · ${s['cost']:.4f} · {s['seconds']:.0f}s
{f" · {s['errors']} errors, {s['fallbacks']} fallbacks" if s['errors'] or s['fallbacks'] else ""}</p>{extra}
<details><summary>output preview</summary><pre>{_preview(run_dir, name)}</pre></details></section>""")
    mmd = html.escape(build_mermaid(run_dir))
    top = " · ".join(f"{k.replace('_', ' ')}: {v}" for k, v in tot.items())
    return f"""<!doctype html><meta charset="utf-8"><title>papertrail trace: {html.escape(run_dir.name)}</title>
<style>body{{font:15px/1.4 system-ui,sans-serif;max-width:980px;margin:32px auto;padding:0 16px;color:#1F2328;background:#FAFAF7}}
.card{{border:1px solid #D9D9D2;padding:12px 16px;margin:12px 0;background:#fff}}h1{{font-size:26px}}h2{{margin:0 0 4px;font-size:18px}}
.meta{{color:#5B6470;margin:0 0 8px}}pre{{white-space:pre-wrap;background:#f3f3ee;padding:8px;overflow:auto}}table{{border-collapse:collapse}}
td,th{{border:1px solid #D9D9D2;padding:2px 8px;text-align:left}}</style>
<h1>papertrail run {html.escape(run_dir.name)}</h1><p class="meta">{html.escape(top)}</p>
<h2>Pipeline</h2><pre class="mermaid">{mmd}</pre>
{''.join(cards)}
<script type="module">import m from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';m.initialize({{startOnLoad:true,theme:'neutral'}});</script>"""


def write(run_dir: Path, out_dir: Path | None = None) -> tuple[Path, Path]:
    out_dir = out_dir or run_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "trace.html").write_text(build_html(run_dir), encoding="utf-8")
    (out_dir / "pipeline.mmd").write_text(build_mermaid(run_dir), encoding="utf-8")
    return out_dir / "trace.html", out_dir / "pipeline.mmd"


if __name__ == "__main__":
    import sys

    print(write(Path(sys.argv[1])))
