"""Offline end-to-end run with scripted fake models (real ingest data, real Slidev render + Playwright QA, no API key, no cost).

    .venv/Scripts/python.exe tests/e2e_fake.py [--from-cache DIR]

Needs a previously ingested run directory (default: %TEMP%/p2d_ingest_real, produced by ingesting arXiv:2505.06120).
Output: runs/e2e-fake/ (gitignored). Also collected by pytest when RUN_E2E=1.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import pytest  # noqa: E402

import pipeline  # noqa: E402
from common.budget import Budget  # noqa: E402
from common.llm import Harness  # noqa: E402
from fakes import make_factory  # noqa: E402


def prepare_run(src: Path, run: Path) -> None:
    shutil.rmtree(run, ignore_errors=True)
    run.mkdir(parents=True)
    for name in ("paper.md", "tables.json", "refs.json", "ingested.json", "source.pdf"):
        shutil.copy(src / name, run / name)
    shutil.copytree(src / "figures", run / "figures")
    from common.papertext import make_llm_text

    (run / "paper_llm.md").write_text(make_llm_text((run / "paper.md").read_text(encoding="utf-8")), encoding="utf-8")


def make_reference_slides(folder: Path) -> Path:
    """Three synthetic example slides, so the style stages run too (different from our theme, so the near-copy guard stays quiet)."""
    from PIL import Image, ImageDraw

    folder.mkdir(parents=True, exist_ok=True)
    for k in range(3):
        im = Image.new("RGB", (1280, 720), (20 + 60 * k, 40, 90))
        d = ImageDraw.Draw(im)
        d.rectangle([60, 60 + 40 * k, 1220, 120 + 40 * k], fill=(240, 240, 240))
        for j in range(5):
            d.rectangle([80 + j * 220, 700 - 120 * (j + 1) // (k + 1), 260 + j * 220, 700], fill=(230, 160, 20))
        im.save(folder / f"example_{k + 1}.png")
    return folder


def run_e2e(src: Path, paper: str = "2505.06120") -> Path:
    run = ROOT / "runs" / f"e2e-fake-{paper.replace('.', '')}"
    prepare_run(src, run)
    factory, _ = make_factory(run)
    os.environ["P2D_CACHE_DIR"] = str(Path(tempfile.mkdtemp()))
    pipeline.HARNESS_FACTORY = lambda run_dir, dev=False: Harness(
        run_dir, dev=dev, model_factory=factory, cache_dir=Path(os.environ["P2D_CACHE_DIR"]),
        budget=Budget(run_dir, {"per_run_usd": 20.0, "total_usd": 50.0}, ledger=run_dir.parent / "_spend_e2e.jsonl"))
    refs = make_reference_slides(Path(tempfile.mkdtemp()) / "refs")
    rc = pipeline.main(["--config", "full", "--paper", paper, "--run-dir", str(run), "--from-stage", "1", "--dev", "--refs", str(refs)])
    assert rc == 0, "pipeline failed"
    return run


@pytest.mark.skipif(os.getenv("RUN_E2E") != "1", reason="set RUN_E2E=1 (slow: builds and renders a Slidev deck)")
def test_e2e_fake():
    src = Path(tempfile.gettempdir()) / "p2d_ingest_real"
    run = run_e2e(src)
    assert (run / "final" / "slides.pdf").exists()
    qa = json.loads((run / "qa.json").read_text(encoding="utf-8"))
    assert qa["rounds_run"] >= 1


if __name__ == "__main__":
    src = Path(sys.argv[sys.argv.index("--from-cache") + 1]) if "--from-cache" in sys.argv else Path(tempfile.gettempdir()) / "p2d_ingest_real"
    print(run_e2e(src, sys.argv[sys.argv.index("--paper") + 1] if "--paper" in sys.argv else "2505.06120"))
