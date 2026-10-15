# Reference slides

Put example slides you like in `references/slides/`. The pipeline studies them, writes a short style brief for the author, and at the end
compares our deck with them on the same features. They are never copied: the brief carries design moves, not content, and a near-copy guard
flags any of our slides that looks like one of them.

**What to add**
- Screenshots of single slides (png, jpg, webp): 4 to 10 is plenty. A mix is best: a title slide, a results slide, a diagram, a table, a slide with a big number.
- Or a whole deck as a PDF (5 pages per file are sampled). A .pptx works only if LibreOffice is installed; otherwise export it to PDF first.
- Choose slides whose visual quality you want to reach (how they use space, visuals, hierarchy, colour). The topic does not matter.

**What happens**
1. `style` reads the images (one cheap Gemini Flash call, about $0.02) and writes `runs/<ts>/style_brief.json`: 6 to 10 transferable principles and
   a checkable quality bar.
2. The author and the per-slide reviser get the brief as guidance.
3. `style_compare` scores the references and our final deck from 1 to 5 on each quality-bar feature and writes `style_comparison.md`
   (also in `final/`), plus a list of our slides that fall below the references. Informational: it never edits the deck.

Use another folder with `python pipeline.py ... --refs path/to/folder`. The folder is ignored by git, so your examples stay on your machine.
