# Image credits

| File | What | Author | License | Source |
|---|---|---|---|---|
| `Ecole-polytechnique-logo.jpg` | University logo (footer) | École polytechnique | Provided by the course team | |
| `ecole_polytechnique_background.jpg` | Title-page background | Supplied by the course team | not stated | |
| `campus-palaiseau.jpg` (alternative, unused unless selected in `deck/footer.json`) | Title-page background (campus aerial view) | Jérémy Barande | CC BY-SA 3.0 | https://commons.wikimedia.org/wiki/File:Campus_Ecole_polytechnique_de_palaiseau.jpg |
| `Armes_de_l'École_polytechnique.jpg` | Faint watermark on content slides (the school's coat of arms) | École polytechnique X | CC BY-SA 4.0 | https://commons.wikimedia.org/wiki/File:Armes_de_l%27%C3%A9cole_polytechnique.jpg |

The campus photo is darkened and resized by `src/papertrail/tools/footer.py`; the coat of arms is turned into a faint navy watermark. Both are therefore adaptations, shared under the same CC BY-SA terms. The title slide no longer carries a credit line (removed at the owner's request on 2026-10-15; `deck/footer.json` field `image_credit` is `null`, set it to a string to show one again). The attribution above stays in this repository.
