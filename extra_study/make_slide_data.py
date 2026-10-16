"""Turn the Kaggle run of the extra study (notebook + log) into slide data: CSVs and SVG charts in a run's artifacts/ folder.

No number is typed here. Everything is parsed from the notebook's printed tables (the .log), the notebook's config cell, and the
paper's own Table 6 (runs/<ts>/tables.json). The slides cite the CSVs ("Our analysis, artifacts/extra_*.csv").

    python extra_study/make_slide_data.py --run runs/20261015-155838
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.plot_style import OKABE_ITO, apply_style  # noqa: E402

MAIN = ["OLMo base", "OLMo SFT", "OLMo DPO", "OLMo final", "Qwen base", "Qwen inst", "SmolLM base", "SmolLM inst"]
FIXES = ["Final, T=1.5", "Final, min-p", "Final, list x5"]
JOB = {"OLMo base": "olmo_base", "OLMo SFT": "olmo_sft", "OLMo DPO": "olmo_dpo", "OLMo final": "olmo_final", "Qwen base": "qwen_base",
       "Qwen inst": "qwen_inst", "SmolLM base": "smol_base", "SmolLM inst": "smol_inst", "Final, T=1.5": "olmo_final_t15",
       "Final, min-p": "olmo_final_minp", "Final, list x5": "olmo_final_list"}
FAMILY = {"OLMo": "OLMo 2 1B", "Qwen": "Qwen2.5 1.5B", "SmolLM": "SmolLM2 1.7B"}
FAM_COLOR = {"OLMo 2 1B": OKABE_ITO[0], "Qwen2.5 1.5B": OKABE_ITO[1], "SmolLM2 1.7B": OKABE_ITO[2]}
NAVY, GREY, LIGHT = "#063A59", "#7A7A7A", "#56B4E9"
NUM = r"[+-]?\d+(?:\.\d+)?|NaN"


def load_log(path: Path) -> str:
    return "".join(e["data"] for e in json.loads(path.read_text(encoding="utf-8")) if e["stream_name"] == "stdout")


def first(pattern: str, text: str, flags: int = re.M) -> re.Match:
    m = re.search(pattern, text, flags)
    if not m:
        raise SystemExit(f"not found in the log: {pattern!r}")
    return m


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print("wrote", path.name, f"({len(rows)} rows)")


def num(s: str) -> float | None:
    return None if s == "NaN" else float(s)


# ---------------------------------------------------------------- parse
def parse_summary(log: str) -> dict[str, dict]:
    out = {}
    for label in MAIN + FIXES:
        m = first(rf"^{re.escape(label)}\s+({NUM})\s+({NUM})\s+({NUM})\s+({NUM})\s+({NUM})\s+({NUM})\s+({NUM})\s*$", log)
        words, full, w64, mpnet, jac = (num(m.group(i)) for i in range(1, 6))
        out[label] = dict(words=words, sim_full=full, sim_64w=w64, sim_mpnet_64w=mpnet, trigram_jaccard=jac)
    return out


def parse_check(log: str) -> dict[str, dict]:
    out = {}
    for label, job in JOB.items():
        m = first(rf"^{job}\s+(\d+)\s+(\d+)\s+({NUM})\s+({NUM})\s+({NUM})\s+\w+\s+\w+\s*$", log)
        out[label] = dict(responses=int(m.group(2)), empty_pct=float(m.group(4)), capped_pct=float(m.group(5)))
    return out


def parse_hist(log: str) -> dict[str, list[float]]:
    return {label: [float(x) for x in first(rf"^{re.escape(label)}\s+((?:\d+\.\d+\s+){{9}}\d+\.\d+)\s*$", log).group(1).split()] for label in MAIN}


def parse_diffs(log: str) -> list[dict]:
    rows = []
    for m in re.finditer(r"^((?:OLMo 2|Qwen2\.5|SmolLM2): [\w-]+ - [\w-]+)\s+(.+)$", log, re.M):
        pairs = re.findall(r"([+-]\d+\.\d+) ± (\d+\.\d+)", m.group(2))
        if len(pairs) == 4:
            rows.append(dict(comparison=m.group(1), d_full=float(pairs[0][0]), ci_full=float(pairs[0][1]), d_64w=float(pairs[1][0]), ci_64w=float(pairs[1][1]),
                             d_mpnet=float(pairs[2][0]), ci_mpnet=float(pairs[2][1]), d_jaccard=float(pairs[3][0]), ci_jaccard=float(pairs[3][1])))
    seen, uniq = set(), []
    for r in rows:  # the log prints the table twice
        if r["comparison"] not in seen:
            seen.add(r["comparison"])
            uniq.append(r)
    return uniq


def parse_cross(log: str) -> list[dict]:
    rows, seen = [], set()
    for m in re.finditer(r"^\s*((?:OLMo 2|Qwen2\.5) - (?:Qwen2\.5|SmolLM2))\s+(base|post-trained)\s+(\d\.\d+)\s+(\d\.\d+)\s*$", log, re.M):
        key = (m.group(1), m.group(2))
        if key not in seen:
            seen.add(key)
            rows.append(dict(pair=m.group(1), stage=m.group(2), raw=float(m.group(3)), normalized=float(m.group(4))))
    return rows


def parse_fix_table(log: str) -> list[dict]:
    rows, seen = [], set()
    for m in re.finditer(r"^\s*(Base T=1\.0|Final T=1\.0|Final T=1\.5|Final min-p|Final list x5)\s+(\d\.\d+)\s+(\d\.\d+)\s+(\S+)\s*$", log, re.M):
        if m.group(1) not in seen:
            seen.add(m.group(1))
            rows.append(dict(setting=m.group(1), sim_64w=float(m.group(2)), ci=float(m.group(3))))
    return rows


def parse_config(nb_path: Path) -> dict:
    nb = json.loads(nb_path.read_text(encoding="utf-8"))
    src = next("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code" and "N_SAMPLES" in "".join(c["source"]))
    get = lambda k: re.search(rf"^{k}\s*=\s*(.+)$", src, re.M).group(1).strip().strip('"')  # noqa: E731
    ci_level = re.search(r"(\d+)% CI", "".join("".join(c["source"]) for c in nb["cells"]))
    return dict(ci_level_pct=ci_level.group(1) if ci_level else "", samples_per_prompt=get("N_SAMPLES"), top_p=get("TOP_P"), temperature=get("TEMPERATURE"), max_new_tokens_chat=get("CHAT_MAX_TOKENS"),
                max_new_tokens_base=get("BASE_MAX_TOKENS"), truncate_words=get("TRUNC_WORDS"), embedding_main=get("EMB_MAIN"), embedding_second=get("EMB_SECOND"))


def paper_row(tables_json: Path, model: str) -> list[float]:
    """The paper's Table 6 row for one model, bins from 0.0-0.1 up to 0.9-1.0 (the paper prints them from 0.9-1.0 down)."""
    t = next(x for x in json.loads(tables_json.read_text(encoding="utf-8")) if x["id"] == "Table 6")
    names, vals = t["rows"][1][0].split(), t["rows"][1][1].split()
    i = names.index(model)
    return [float(v) for v in vals[i * 10:(i + 1) * 10]][::-1]


# ---------------------------------------------------------------- charts
def style_axes(ax) -> None:
    ax.spines["left"].set_color("#C9D2D9")
    ax.spines["bottom"].set_color("#C9D2D9")
    ax.tick_params(colors="#1F2328")


def chart_design(path: Path) -> None:
    """The study design as a diagram: OLMo at every training stage, and base -> instruct for the other two families, in aligned columns."""
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

    apply_style()
    fig, ax = plt.subplots(figsize=(12, 4.6))
    ax.set_xlim(0, 12.2)
    ax.set_ylim(0, 4.6)
    ax.axis("off")
    xs = [3.9, 6.2, 8.5, 10.8]                     # column centres: base, SFT, DPO, final
    w, h = 1.9, 0.95

    def node(x, y, text, fill, edge, color):
        ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.02,rounding_size=0.45", facecolor=fill, edgecolor=edge, linewidth=2))
        ax.text(x, y, text, ha="center", va="center", fontsize=15, color=color, linespacing=1.15)

    def arrow(x0, x1, y, label=None):
        ax.add_patch(FancyArrowPatch((x0 + w / 2 + 0.06, y), (x1 - w / 2 - 0.06, y), arrowstyle="-|>", mutation_scale=22, color=TEXT_COLOR, linewidth=2))
        if label:
            ax.text((x0 + x1) / 2, y + 0.32, label, ha="center", va="bottom", fontsize=14, color="#4A5866")

    TEXT_COLOR = "#1F2328"
    rows = [(3.55, "OLMo 2 1B", FAM_COLOR["OLMo 2 1B"]), (2.05, "Qwen2.5 1.5B", FAM_COLOR["Qwen2.5 1.5B"]), (0.55, "SmolLM2 1.7B", FAM_COLOR["SmolLM2 1.7B"])]
    for y, name, c in rows:
        ax.text(0.15, y, name, ha="left", va="center", fontsize=16, fontweight="bold", color=c)
        node(xs[0], y, "Base", "#0072B2", "#0072B2", "white")
    for i, (a, b, t) in enumerate(zip(xs[:3], xs[1:], ["SFT\nsupervised", "DPO\npreferences", "Final\nRL step"])):
        node(b, rows[0][0], t, "#FAFAF7", TEXT_COLOR, TEXT_COLOR)
        arrow(a, b, rows[0][0])
    for y, _, _ in rows[1:]:
        node(xs[3], y, "Instruct", "#FAFAF7", TEXT_COLOR, TEXT_COLOR)
        arrow(xs[0], xs[3], y, "post-training (all steps)")
    ax.text(xs[0], 4.35, "pretraining", ha="center", fontsize=14, color="#4A5866")
    ax.text((xs[1] + xs[3]) / 2, 4.35, "post-training", ha="center", fontsize=14, color="#4A5866")
    ax.plot([xs[0] - 0.9, xs[0] + 0.9], [4.2, 4.2], color="#0072B2", linewidth=3)
    ax.plot([xs[1] - 0.9, xs[3] + 0.9], [4.2, 4.2], color=TEXT_COLOR, linewidth=3)
    fig.savefig(path, format="svg", bbox_inches="tight")
    plt.close(fig)


def chart_replication(path: Path, paper: list[float], ours: list[float], paper_mean: float, ours_mean: float) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    apply_style()
    fig, ax = plt.subplots(figsize=(6.6, 4.4))
    x = np.arange(10)
    ax.bar(x - 0.2, paper, 0.4, color=GREY, label="Paper (OpenAI embeddings)")
    ax.bar(x + 0.2, ours, 0.4, color=OKABE_ITO[0], label="Ours (open embeddings)")
    ax.set_xticks(x, [f"{i / 10:.1f}" for i in range(10)])
    ax.set_xlabel("similarity of one prompt's 50 responses (bin start)", fontsize=13)
    ax.set_ylabel("% of prompts", fontsize=14)
    ax.tick_params(labelsize=13)
    ax.legend(loc="upper left", fontsize=13)
    style_axes(ax)
    fig.tight_layout()
    fig.savefig(path, format="svg")
    plt.close(fig)


def chart_stages(path: Path, S: dict, D: dict) -> None:
    import matplotlib.pyplot as plt

    apply_style()
    fig, ax = plt.subplots(figsize=(6.6, 4.6))
    stages = ["Base", "SFT", "DPO", "Final"]
    olmo = [S[k]["sim_full"] for k in ("OLMo base", "OLMo SFT", "OLMo DPO", "OLMo final")]
    ax.plot(range(4), olmo, color=FAM_COLOR["OLMo 2 1B"], marker="o", markersize=9, label="OLMo 2 1B (every stage)")
    for fam, b, f in (("Qwen2.5 1.5B", "Qwen base", "Qwen inst"), ("SmolLM2 1.7B", "SmolLM base", "SmolLM inst")):
        ax.plot([0, 3], [S[b]["sim_full"], S[f]["sim_full"]], color=FAM_COLOR[fam], marker="s" if "Qwen" in fam else "^", markersize=9, linestyle="--", label=f"{fam} (base, instruct)")
    for i, key in enumerate(("OLMo: SFT - base", "OLMo: DPO - SFT", "OLMo: final - DPO")):
        d = D[key]["d_full"]
        ax.annotate(f"{d:+.2f}", ((i + i + 1) / 2, (olmo[i] + olmo[i + 1]) / 2), xytext=(0, -26 if i == 0 else 14), textcoords="offset points", ha="center",
                    fontsize=15, color=NAVY, fontweight="bold")
    ax.set_xticks(range(4), stages)
    ax.set_xlim(-0.3, 3.3)
    ax.set_ylim(0.35, 0.85)
    ax.set_ylabel("similarity of responses to one prompt", fontsize=14)
    ax.tick_params(labelsize=14)
    ax.legend(loc="lower right", fontsize=12)
    style_axes(ax)
    fig.tight_layout()
    fig.savefig(path, format="svg")
    plt.close(fig)


def chart_cross(path: Path, rows: list[dict]) -> None:
    import matplotlib.pyplot as plt

    apply_style()
    fig, ax = plt.subplots(figsize=(5.6, 4.4))
    pairs = list(dict.fromkeys(r["pair"] for r in rows))
    get = lambda p, s: next(r["raw"] for r in rows if r["pair"] == p and r["stage"] == s)  # noqa: E731
    for i, p in enumerate(pairs):
        lo, hi = get(p, "base"), get(p, "post-trained")
        ax.plot([i, i], [lo, hi], color="#C9D2D9", linewidth=4, zorder=1)
        ax.scatter([i], [lo], s=190, color=LIGHT, zorder=2, label="base models" if i == 0 else None)
        ax.scatter([i], [hi], s=190, color=NAVY, zorder=2, label="post-trained models" if i == 0 else None)
        ax.text(i + 0.12, lo, f"{lo:.2f}", va="center", fontsize=14)
        ax.text(i + 0.12, hi, f"{hi:.2f}", va="center", fontsize=14)
    ax.set_xticks(range(len(pairs)), [p.replace(" - ", "\nvs ") for p in pairs])
    ax.set_xlim(-0.5, len(pairs) - 0.4)
    ax.set_ylim(0.3, 0.85)
    ax.set_ylabel("similarity between two families", fontsize=14)
    ax.tick_params(labelsize=13)
    ax.legend(loc="upper left", fontsize=13)
    style_axes(ax)
    fig.tight_layout()
    fig.savefig(path, format="svg")
    plt.close(fig)


def chart_decoding(path: Path, rows: list[dict]) -> None:
    import matplotlib.pyplot as plt

    apply_style()
    fig, ax = plt.subplots(figsize=(5.6, 4.4))
    names = {"Base T=1.0": "Base, T=1.0", "Final T=1.0": "Final, T=1.0", "Final T=1.5": "Final, T=1.5", "Final min-p": "Final, min-p", "Final list x5": "Final, 5 answers\nper call"}
    colors = {"Base T=1.0": GREY, "Final T=1.0": NAVY, "Final T=1.5": OKABE_ITO[1], "Final min-p": OKABE_ITO[0], "Final list x5": OKABE_ITO[0]}
    ys = list(range(len(rows)))[::-1]
    for y, r in zip(ys, rows):
        ax.barh(y, r["sim_64w"], xerr=r["ci"], color=colors[r["setting"]], height=0.62, ecolor="#1F2328", capsize=4)
        ax.text(r["sim_64w"] + r["ci"] + 0.012, y, f"{r['sim_64w']:.2f}", va="center", fontsize=14)
    ax.set_yticks(ys, [names[r["setting"]] for r in rows])
    ax.set_xlim(0, 0.95)
    ax.set_xlabel("similarity (lower = more diverse)", fontsize=14)
    ax.tick_params(labelsize=13)
    style_axes(ax)
    fig.tight_layout()
    fig.savefig(path, format="svg")
    plt.close(fig)


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="run directory (reads tables.json, writes artifacts/)")
    ap.add_argument("--log", default=str(Path(__file__).parent / "notebook5cc2be13a5.log"))
    ap.add_argument("--notebook", default=str(Path(__file__).parent / "notebook5cc2be13a5.ipynb"))
    a = ap.parse_args()
    run = Path(a.run)
    out = run / "artifacts"
    out.mkdir(exist_ok=True)

    log = load_log(Path(a.log))
    S, C, H = parse_summary(log), parse_check(log), parse_hist(log)
    diffs = {d["comparison"].replace("OLMo 2", "OLMo"): d for d in parse_diffs(log)}
    cross, fixes = parse_cross(log), parse_fix_table(log)
    random_sim = float(first(r"random-pair similarity here: (\d\.\d+)", log).group(1))
    cfg = parse_config(Path(a.notebook))
    n_prompts = int(first(r"^(\d+) prompts \|", log).group(1))
    gpu = first(r"(Tesla T4)", log).group(1)

    write_csv(out / "extra_setup.csv", ["parameter", "value"], [["prompts", n_prompts], *[[k, v] for k, v in cfg.items()], ["models_compared", len(MAIN)], ["model_families", len(FAMILY)], ["olmo_stages", 4], ["gpu", gpu],
                                                                  ["random_pair_similarity_ours", random_sim]])

    paper = paper_row(run / "tables.json", "Qwen/Qwen2.5-1.5B-Instruct")
    ours = H["Qwen inst"]
    mid = [i / 10 + 0.05 for i in range(10)]
    paper_mean = sum(m * p for m, p in zip(mid, paper)) / 100
    ours_mean = S["Qwen inst"]["sim_full"]
    write_csv(out / "extra_replication.csv", ["bin", "paper_pct", "ours_pct"], [[f"{i / 10:.1f}-{(i + 1) / 10:.1f}", paper[i], ours[i]] for i in range(10)])
    write_csv(out / "extra_replication_summary.csv", ["metric", "paper", "ours"],
              [["mean_similarity", round(paper_mean, 2), round(ours_mean, 2)], ["share_of_prompts_at_0.7_to_0.9_pct", paper[7] + paper[8], ours[7] + ours[8]]])

    write_csv(out / "extra_stages.csv", ["model", "family", "stage", "sim_full", "sim_64w", "sim_mpnet_64w", "trigram_jaccard", "avg_words", "capped_pct"],
              [[l, FAMILY[l.split()[0]], l.split()[1] if l.split()[1] in ("base", "SFT", "DPO", "final", "inst") else "", S[l]["sim_full"], S[l]["sim_64w"], S[l]["sim_mpnet_64w"],
                S[l]["trigram_jaccard"], S[l]["words"], C[l]["capped_pct"]] for l in MAIN])
    write_csv(out / "extra_stage_changes.csv", ["comparison", "d_full", "ci_full", "d_64w", "ci_64w", "d_mpnet", "ci_mpnet", "d_jaccard", "ci_jaccard"],
              [[k, *[d[c] for c in ("d_full", "ci_full", "d_64w", "ci_64w", "d_mpnet", "ci_mpnet", "d_jaccard", "ci_jaccard")]] for k, d in diffs.items()])
    write_csv(out / "extra_cross_family.csv", ["pair", "stage", "raw", "normalized"], [[r["pair"], r["stage"], r["raw"], r["normalized"]] for r in cross])

    fix_label = {"Base T=1.0": "OLMo base", "Final T=1.0": "OLMo final", "Final T=1.5": "Final, T=1.5", "Final min-p": "Final, min-p", "Final list x5": "Final, list x5"}
    write_csv(out / "extra_decoding.csv", ["setting", "sim_64w", "ci_95", "avg_words", "capped_pct"],
              [[r["setting"], r["sim_64w"], r["ci"], S[fix_label[r["setting"]]]["words"], C[fix_label[r["setting"]]]["capped_pct"]] for r in fixes])

    chart_design(out / "extra_design.svg")
    chart_replication(out / "extra_replication.svg", paper, ours, paper_mean, ours_mean)
    chart_stages(out / "extra_stages.svg", S, diffs)
    chart_cross(out / "extra_cross_family.svg", cross)
    chart_decoding(out / "extra_decoding.svg", fixes)
    print("charts written to", out)


if __name__ == "__main__":
    main()
