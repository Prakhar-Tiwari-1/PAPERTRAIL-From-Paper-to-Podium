---
theme: ./theme
title: papertrail demo deck
routerMode: hash
canvasWidth: 1280
aspectRatio: 16/9
fonts:
  provider: none
  sans: Inter
  mono: JetBrains Mono
layout: title
---

# LLMs Get Lost In Multi-Turn Conversation

Why today's language models lose the thread when instructions arrive piece by piece

<!--
Demo deck used to check the theme and the editable footer.
-->

---
layout: claim-figure
---

# Aptitude and unreliability separate peak skill from consistency

<img src="/figures/demo-fig5.svg" />

<SourceCaption>Laban et al., 2025, Fig. 5</SourceCaption>

<!--
Notes.
-->

---
layout: claim-example
---

# Sharding splits one instruction into one piece per turn

<Turn who="user">What is the total number of points Ara scored?</Turn>
<Turn who="assistant">Could you tell me how many games Ara played?</Turn>
<Turn who="user">She played 40 games and scored 21 points in each.</Turn>

<SourceCaption>Laban et al., 2025, Appendix J</SourceCaption>

<!--
Notes.
-->

---
layout: claim-table
---

# Every model drops sharply when the instruction arrives in pieces

| Model | Fully specified | Sharded | Drop |
|---|---|---|---|
| GPT-4.1 | 90.0 | 61.8 | -29 |
| Gemini 2.5 Pro | 87.3 | 59.4 | -28 |
| Average | 85.0 | 52.0 | -33 |

<SourceCaption>Laban et al., 2025, Table 1 (illustrative values)</SourceCaption>

<!--
Notes.
-->

---
layout: claim-bullets
---

# Three failure behaviours explain most of the drop

- Models answer before they have all the details
- They stick to their first wrong attempt
- Their answers grow longer with every turn

<!--
Notes.
-->

---
layout: section
---

# Backup

<!--
Notes.
-->
