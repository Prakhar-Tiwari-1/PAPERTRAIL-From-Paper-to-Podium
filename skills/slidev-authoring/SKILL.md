---
name: slidev-authoring
description: How to write the deck as Slidev markdown using only the project's theme layouts.
stages: [author, reviser, oneshot]
---
Output one Slidev markdown file. Slides are separated by `---`; each slide starts with a frontmatter block and ends with its speaker notes:

```
---
layout: claim-figure
---
# A full-sentence claim as the title

<img src="/figures/fig3.svg" />
<SourceCaption>Smith et al., 2024, Fig. 3</SourceCaption>
One short sentence saying what to look at.

<!--
Speaker notes, in an HTML comment at the end of the slide.
-->
```

## Layouts (only these)
- `title`: first slide. Write only `# Title` and one subtitle line; the theme adds photo, citation, presenters, course, date.
- `claim-figure`: title + one large paper figure + caption + one sentence. For a wide figure.
- `claim-split`: title + `::left::` visual (figure, diagram or table) + `::right::` two or three short takeaways as a bullet list. For narrow or tall figures and for any slide that would otherwise be a short list.
- `claim-two-figures`: two figures side by side (`::left::`, `::right::`).
- `claim-table`: title + markdown table excerpt (3 to 6 rows, at most 6 columns) + caption `Smith et al., 2024, Table N` (use the paper's own citation, given to you) + one sentence on what to read off it.
- `claim-diagram`: title + one Mermaid diagram (see skill diagram-style).
- `claim-example`: a worked example as a chat: `<Turn who="user">...</Turn>` / `<Turn who="assistant">...</Turn>`, from the example named in the difficulty map (a real record or one printed in the paper). Use it only for a real exchange. Never turn counts, a study design or a list of facts into an invented question-and-answer chat: use `claim-table` (rows and columns) for that.
- `claim-number`: `<BigNumber>39%</BigNumber>` plus one or two context lines.
- `claim-bullets`: at most 4 short bullets; at most two such slides in the main deck.
- `claim-quiz`: the quiz slide. Write only its `# title` and its notes; the pipeline inserts the questions and answers.
- `workflow`: the last main slide. Write only `# Tools & Workflow` and its notes; the pipeline generates the body.
- `section`: only the `# Backup` divider.

## Rules
- Every figure, diagram and table has `<SourceCaption>`. Table cells are copied exactly from the table given to you.
- Fill the slide: the visual is large, the lower third is never empty. A narrow figure goes into `claim-split`.
- No inline `style=`, custom CSS, emoji, background images, or layouts not listed. Fragments only as a two-step `<v-click>` reveal.
- 13 to 16 main slides, then `# Backup`, then exactly 3 backup slides, each with a visual.
- 50 to 70 visible words per slide, never above 70. Numbers come only from the digest, tables or artifacts you were given.
