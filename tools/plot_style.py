"""Shared matplotlib style for every plot (skill figure-replot). Okabe-Ito palette, SVG, big ticks, no grid."""
from __future__ import annotations

OKABE_ITO = ["#0072B2", "#B04A33", "#009E73", "#6A4C93", "#CC79A7", "#56B4E9", "#7A7A7A", "#000000"]
TEXT = "#1F2328"
BG = "#FAFAF7"


def apply_style() -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from cycler import cycler

    plt.rcParams.update(
        {
            "figure.figsize": (12, 6.5),
            "figure.dpi": 100,
            "figure.facecolor": BG,
            "axes.facecolor": BG,
            "savefig.facecolor": BG,
            "svg.fonttype": "none",
            "font.family": "sans-serif",
            "font.sans-serif": ["Inter", "Source Sans 3", "DejaVu Sans"],
            "font.size": 18,
            "axes.titlesize": 20,
            "axes.labelsize": 18,
            "xtick.labelsize": 16,
            "ytick.labelsize": 16,
            "text.color": TEXT,
            "axes.labelcolor": TEXT,
            "xtick.color": TEXT,
            "ytick.color": TEXT,
            "axes.edgecolor": TEXT,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": False,
            "axes.prop_cycle": cycler(color=OKABE_ITO),
            "lines.linewidth": 3,
            "legend.frameon": False,
        }
    )
