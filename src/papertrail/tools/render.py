"""render(deck): slidev build + per-slide QA capture + PDF/PPTX export (SPEC §6). Not a model tool: the orchestrator calls it."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from papertrail.qa.source_map import parse_slides
from papertrail.tools import footer as footer_tool

from papertrail.paths import PKG, ROOT
DECK_SRC = ROOT / "deck"
NPX = "npx.cmd" if sys.platform == "win32" else "npx"


class RenderError(RuntimeError):
    pass


@dataclass
class Build:
    deck_dir: Path
    dist: Path
    n_slides: int


def prepare_deck_dir(run_dir: Path) -> Path:
    """runs/<ts>/deck/ = theme + package.json + figures + artifacts + node_modules junction. slides.md is written by the author."""
    d = run_dir / "deck"
    d.mkdir(parents=True, exist_ok=True)
    for name in ("package.json",):
        shutil.copy(DECK_SRC / name, d / name)
    if (d / "theme").exists():
        shutil.rmtree(d / "theme")
    shutil.copytree(DECK_SRC / "theme", d / "theme")
    pub = d / "public"
    pub.mkdir(exist_ok=True)
    for sub, src in (("figures", run_dir / "figures"), ("artifacts", run_dir / "artifacts")):
        dest = pub / sub
        if dest.exists():
            shutil.rmtree(dest)
        if src.exists():
            shutil.copytree(src, dest, ignore=shutil.ignore_patterns("_exec_*.py", ".mpl"))
    footer_tool.sync(d, run_dir=run_dir)  # editable footer: deck/footer.json -> theme/footer.json + public/footer-logo.png
    nm = d / "node_modules"
    if not nm.exists():
        target = DECK_SRC / "node_modules"
        if not target.exists():
            raise RenderError("deck/node_modules missing: run `cd deck && npm install`")
        if sys.platform == "win32":  # junction: no admin rights needed
            subprocess.run(["cmd", "/c", "mklink", "/J", str(nm), str(target)], check=True, capture_output=True)
        else:
            os.symlink(target, nm, target_is_directory=True)
    return d


def _run(cmd: list[str], cwd: Path, timeout: int, label: str) -> str:
    env = dict(os.environ, CI="1", FORCE_COLOR="0")
    p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RenderError(f"{label} failed ({p.returncode}):\n{(p.stdout + p.stderr)[-1500:]}")
    return p.stdout


def build(run_dir: Path, timeout: int = 300) -> Build:
    d = prepare_deck_dir(run_dir)
    if not (d / "slides.md").exists():
        raise RenderError(f"{d / 'slides.md'} does not exist")
    dist = d / "dist"
    if dist.exists():
        shutil.rmtree(dist)
    _run([NPX, "slidev", "build", "slides.md", "--out", "dist", "--base", "./"], d, timeout, "slidev build")
    n = len(parse_slides((d / "slides.md").read_text(encoding="utf-8")))
    return Build(d, dist, n)


def capture(b: Build, out_dir: Path, timeout: int = 600) -> list[dict]:
    """Visit each slide at 1280x720: PNG + elements.json + checks.json under out_dir. Returns the per-slide summary."""
    out_dir.mkdir(parents=True, exist_ok=True)
    p = subprocess.run(["node", str(PKG / "qa" / "run_qa.mjs"), "--dist", str(b.dist), "--deck", str(b.deck_dir),
                        "--out", str(out_dir), "--n", str(b.n_slides)],
                       capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RenderError(f"qa capture failed:\n{(p.stdout + p.stderr)[-1500:]}")
    return json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))


def export(b_or_dir: Build | Path, fmt: str, out_file: Path, timeout: int = 900) -> Path:
    """fmt in pdf | pptx | png. Uses `slidev export` (Playwright)."""
    d = b_or_dir.deck_dir if isinstance(b_or_dir, Build) else Path(b_or_dir)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    _run([NPX, "slidev", "export", "slides.md", "--format", fmt, "--output", str(out_file.resolve()), "--timeout", "60000"],
         d, timeout, f"slidev export {fmt}")
    if not out_file.exists():
        raise RenderError(f"export produced no {out_file}")
    return out_file
