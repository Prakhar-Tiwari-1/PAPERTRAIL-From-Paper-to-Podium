"""One-shot baseline (SPEC §11): one Sonnet prompt, paper -> Slidev deck. No plan, no critics, no repair loop."""
from __future__ import annotations

from pathlib import Path

from common.ctx import RunCtx
from common.repair import fill, load_prompt
from common.schemas import AuthorOutput
from stages.author import write_deck
from tools.render import prepare_deck_dir


def run(ctx: RunCtx) -> None:
    info = ctx.load_json("ingested.json")
    figures = ", ".join(f"/figures/{Path(f['path']).name} ({f['id']}: {f['caption'][:60]})" for f in info["figures"]) or "none"
    prompt = fill(load_prompt("oneshot.md"), figures=figures, paper=ctx.text("paper.md"))
    out = ctx.h.call("oneshot", prompt, output_type=AuthorOutput)
    write_deck(ctx, out)
    prepare_deck_dir(ctx.run_dir)
