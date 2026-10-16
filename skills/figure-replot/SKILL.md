---
name: figure-replot
description: Shared matplotlib style and rules for plots made by the analyst.
stages: [analyze]
---
- **No number typed by hand.** Every plotted value is read from a file (CSV/JSON in `artifacts/` or the released data). Write the CSV *before* plotting.
- Use `from papertrail.tools.plot_style import apply_style, OKABE_ITO`; call `apply_style()` first. Do not set colours or fonts yourself.
- Palette: Okabe-Ito. Label lines directly instead of using legends. No grid clutter. Tick labels at least 16 px at slide size (figure size 12x6.5 in at 100 dpi).
- Output SVG (`artifacts/<name>.svg`) and the CSV (`artifacts/<name>.csv`). Return a caption string such as "Our analysis, artifacts/<name>.csv".
- Plots are made only when the plan asks for one: a re-plot of a paper figure, an explanatory graph for a hard concept, or our own results. Anything else gets no graphic.
- The code runs in a sandbox with no network; the working directory is the artifacts folder.
