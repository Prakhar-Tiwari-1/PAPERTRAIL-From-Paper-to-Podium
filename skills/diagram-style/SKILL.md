---
name: diagram-style
description: Mermaid conventions and templates for slide diagrams.
stages: [author, reviser]
---
Use a diagram when the idea is a process, a comparison of conditions, or a conversation. It replaces a list of bullets.

- At most 8 nodes, flowing left to right (`flowchart LR`). Labels of at most 4 words, sentence case. Edge labels short.
- One highlighted path in the accent colour: `classDef accent fill:#0B6E99,stroke:#0B6E99,color:#FFFFFF` and `class A,B accent`; everything else
  `classDef base fill:#FAFAF7,stroke:#1F2328,color:#1F2328`.
- No decorative shapes, emoji, icons, or nesting deeper than one level. Validate with the mermaid_check tool.

Templates (adapt, keep them small):
```
flowchart LR
  A[Full instruction] --> B[Split into shards]
  B --> C[Reveal one per turn]
  C --> D[Model answers]
  D --> E[Grade the answer]
  class C,D accent
```
```
sequenceDiagram
  participant U as User
  participant M as Model
  U->>M: First piece of the task
  M-->>U: Early answer attempt
  U->>M: New detail
  M-->>U: Builds on its first answer
```
Pick the type that fits: `flowchart LR` for pipelines and conditions, `sequenceDiagram` for turns between user and model, `stateDiagram-v2` for what the
model does next. Process flows, condition setups and conversation structures are diagrams, not Python plots.
