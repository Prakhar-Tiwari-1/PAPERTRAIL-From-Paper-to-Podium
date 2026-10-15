"""mermaid_check(src): parse Mermaid and return errors so the author fixes them before rendering (SPEC §6)."""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FENCE = re.compile(r"```mermaid\s*\n(.*?)```", re.S)


def extract_mermaid(slides_md: str) -> list[tuple[int, str]]:
    """[(line_number_of_fence, source)] for every ```mermaid block."""
    out = []
    for m in FENCE.finditer(slides_md):
        out.append((slides_md.count("\n", 0, m.start()) + 1, m.group(1)))
    return out


def check_sources(sources: list[str], deck_dir: Path | None = None, timeout: int = 90) -> list[dict]:
    """Returns [{ok, error}] per source. If the checker cannot run, ok is None (unchecked), never silently True."""
    if not sources:
        return []
    deck = Path(deck_dir or ROOT / "deck")
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "in.json"
        f.write_text(json.dumps(sources), encoding="utf-8")
        try:
            p = subprocess.run(["node", str(ROOT / "tools" / "mermaid_check.mjs"), "--deck", str(deck), "--in", str(f)],
                               capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
            if p.returncode != 0:
                raise RuntimeError(p.stderr[-300:])
            return json.loads(p.stdout.strip().splitlines()[-1])
        except Exception as e:  # node/browser missing, timeout...
            return [{"ok": None, "error": f"mermaid_check could not run: {e}"} for _ in sources]


def mermaid_problems(slides_md: str, deck_dir: Path | None = None) -> list[str]:
    blocks = extract_mermaid(slides_md)
    res = check_sources([s for _, s in blocks], deck_dir)
    return [f"mermaid block at line {line}: {r['error']}" for (line, _), r in zip(blocks, res) if r["ok"] is False]
