"""7.5 Analyze: the analyst turns plan.analysis_requests into CSV + SVG artifacts via the sandboxed python_exec tool.

No number is typed by hand: every plotted value is read from a file (tables.json copy, the paper profile's released dataset, or a CSV the code wrote).
A request the analyst cannot fulfil is recorded as failed in analysis_notes.md; the author is told which artifacts really exist.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from pydantic import BaseModel

from papertrail.common.ctx import RunCtx
from papertrail.common.profile import cite_short, current
from papertrail.common.schemas import AnalysisRequest, Plan
from papertrail.tools import dataset as dataset_tool
from papertrail.tools.python_exec import make_tool


class AnalysisResult(BaseModel):
    ok: bool
    csv_files: list[str] = []
    svg_file: str = ""
    caption: str = ""
    notes: str = ""


PROMPT = """You are the analyst. Produce ONE analysis artifact for the request below by writing and running Python with the `run_python` tool.

Request ({kind}): {description}
Data source named by the plan: {data_source}

Environment:
- The working directory is the artifacts folder. `tables.json` (the paper's parsed tables: a list of {{id, caption, rows}}; header cells can be blank, so
  read the caption and the first rows before you assume which column is which) is in it. {data_note}
- Use `from papertrail.tools.plot_style import apply_style, OKABE_ITO; apply_style()` for every plot (12x6.5 in, SVG, labels on lines, at most 8 series).
- NO number may be typed by hand. Read every value from a file, write the data behind the plot to a CSV BEFORE plotting, then plot from that CSV.
- If the request needs data that does not exist, do not invent it: say so and return ok=false.
- Name outputs `{id}.csv` and `{id}.svg`.

When done, return JSON: {{"ok": bool, "csv_files": ["{id}.csv"], "svg_file": "{id}.svg", "caption": "Our analysis, artifacts/{id}.csv" (or "Re-plot of {cite}, Table N; data: artifacts/{id}.csv"), "notes": "what the figure shows in one or two sentences, with the values you read"}}.
"""


def data_note() -> str:
    ds = dataset_tool.active()
    hint = current().analysis_hints
    if ds is None:
        return "There is no other dataset: use the paper's tables." + (f" {hint}" if hint else "")
    return f"The released dataset is at: {ds.path} ({ds.spec.description})." + (f" {hint}" if hint else "")


def _check(art: Path, req: AnalysisRequest, res: AnalysisResult) -> list[str]:
    errs = []
    if not res.ok:
        return errs
    for f in res.csv_files:
        p = art / f
        if not p.exists() or p.stat().st_size == 0:
            errs.append(f"{f} missing or empty")
    svg = art / res.svg_file
    if not res.svg_file or not svg.exists() or svg.stat().st_size < 200:
        errs.append(f"{res.svg_file or 'svg'} missing or empty")
    if not res.csv_files:
        errs.append("no CSV with the data behind the plot")
    return errs


def run(ctx: RunCtx) -> None:
    plan = ctx.load("plan.json", Plan)
    art = ctx.p("artifacts", ".keep").parent
    shutil.copy(ctx.p("tables.json"), art / "tables.json")
    tool = make_tool(art)
    lines = ["# Analysis notes", ""]
    done: list[dict] = []
    ds = dataset_tool.active()
    if ds is not None:
        ds.records()  # make sure the dataset file exists locally before the sandbox reads it
    note, cite = data_note(), cite_short(ctx.run_dir)
    for req in plan.analysis_requests:
        prompt = PROMPT.format(kind=req.kind, description=req.description, data_source=req.data_source, data_note=note, cite=cite, id=req.id)
        try:
            res = ctx.h.call("analyst", prompt, output_type=AnalysisResult, tools=[tool], max_tool_calls=8)
            errs = _check(art, req, res)
            if errs:
                res = AnalysisResult(ok=False, notes="; ".join(errs))
        except Exception as e:  # keep going: one failed analysis must not stop the run
            res = AnalysisResult(ok=False, notes=f"analyst failed: {e!r}"[:300])
        done.append({"id": req.id, **res.model_dump()})
        lines.append(f"## {req.id} ({req.kind}): {'OK' if res.ok else 'FAILED'}")
        lines.append(f"- request: {req.description}")
        if res.ok:
            lines += [f"- files: {', '.join(res.csv_files + [res.svg_file])}", f"- caption: {res.caption}"]
        lines += [f"- notes: {res.notes}", ""]
    if not plan.analysis_requests:
        lines.append("No analysis requests in the plan.")
    ctx.save("artifacts/analysis_index.json", done)
    ctx.p("artifacts", "analysis_notes.md").write_text("\n".join(lines), encoding="utf-8")
