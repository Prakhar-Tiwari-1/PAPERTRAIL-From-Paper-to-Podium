# What changed between the model's deck and the presented deck

`model-generated/` is the deck at the end of the render loop. `final/` is what is presented. Everything below was done by hand after the pipeline run, at the owner's request. The judge scored only the model-generated version.

## Look (theme; commit `manual: deck look ...`)

- The small rule under every heading was removed.
- The gold accent became a brick red (`#B04A33`); the title-slide citation and tag colour changed with it.
- The crest credit line was removed from the title slide (the attribution stays in `media/ATTRIBUTION.md`).
- The title photo was replaced by a high-resolution photo, cut to 16:9 around a chosen focus, with a lighter shade.
- Diagrams are scaled to fit their card (the "cause unknown" diagram had overflowed it and was redrawn top-down).

## Content

- **Quiz (slide 14):** eight questions did not fit above the footer, so the quiz was cut to six (three concept, three what-if) and reworded in plainer language. Numbers written in a question now have to occur in the cited source, which removed the four waivers the first export needed.
- **Slide 9:** the invented User/Assistant chat about "25 independent labels" was replaced by a table of the annotation design.
- **Slides 16 to 19 (new):** the extra study (idea, replication, result by training stage, result across families and decoding fixes), inserted before Tools & Workflow. Data and charts: `extra-study/`.

## Consequences

- The deck has 20 main slides and about 21 minutes of speaker notes, above the pipeline's own limit of 16 main slides and 20 minutes.
- The judge report (`model-generated/judge_report.json`) predates all of this; its slide numbers and scores do not describe the presented deck.
