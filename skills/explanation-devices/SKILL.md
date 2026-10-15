---
name: explanation-devices
description: When to use which explanation device for a hard concept.
stages: [difficulty, author]
---
Choose exactly one device per hard concept. Do not stack devices on one concept.

| Device | Use for | Rules |
|---|---|---|
| `worked_example` | procedures and data transformations | Always taken from real data (an actual instruction ID with its shards, turn by turn). Never invent an example. |
| `analogy` | intuition only | State the mapping AND where the analogy breaks. Never use an analogy to carry a number. |
| `diagram` | structure and flow | At most 8 nodes, left to right; sketch the nodes and edges in `device_material`. |
| `graph` | distributions and comparisons | Name the data source (file/table) and what the reader should see. Values come from files, never typed by hand. |
| `prior_work_contrast` | "why is this new" | Contrast with a work from the paper's references or a verifiable citing paper. |

`device_material` must be concrete enough that a slide author can use it without reading the paper again.
