"""Reference slides: examples of slides the owner likes (references/slides/). They teach the author a quality bar; they are never copied.

Accepted: images (png, jpg, jpeg, webp), PDF decks (a few evenly spaced pages), PPTX (converted through LibreOffice if it is installed; otherwise
export the deck to PDF yourself). At most MAX_IMAGES images reach the model, resized to 1280 px wide.
The near-copy guard compares small perceptual hashes of our slides with the references and flags any slide that looks like one of them.
"""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIR = ROOT / "references" / "slides"
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
MAX_IMAGES = 10
PDF_PAGES_PER_FILE = 5


def refs_dir(override: str | Path | None = None) -> Path:
    return Path(override or os.getenv("PAPERTRAIL_REFS") or DEFAULT_DIR)


def _png(im: Image.Image, width: int = 1280) -> bytes:
    im = im.convert("RGB")
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def _pdf_pages(path: Path, n: int) -> list[tuple[str, bytes]]:
    import pymupdf

    doc = pymupdf.open(path)
    idx = sorted({round(i * (len(doc) - 1) / max(n - 1, 1)) for i in range(min(n, len(doc)))}) if len(doc) > 1 else [0]
    out = []
    for i in idx:
        pm = doc[i].get_pixmap(dpi=110)
        out.append((f"{path.stem} p.{i + 1}", _png(Image.frombytes("RGB", [pm.width, pm.height], pm.samples))))
    return out


def _pptx_to_pdf(path: Path) -> Path | None:
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe:
        return None
    tmp = Path(tempfile.mkdtemp())
    subprocess.run([exe, "--headless", "--convert-to", "pdf", "--outdir", str(tmp), str(path)], capture_output=True, timeout=180)
    pdf = tmp / (path.stem + ".pdf")
    return pdf if pdf.exists() else None


def collect(folder: str | Path | None = None, max_images: int = MAX_IMAGES) -> tuple[list[tuple[str, bytes]], list[str]]:
    """([(label, png bytes)], [notes about files that could not be used])."""
    d = refs_dir(folder)
    items: list[tuple[str, bytes]] = []
    notes: list[str] = []
    if not d.exists():
        return items, notes
    for f in sorted(d.iterdir()):
        ext = f.suffix.lower()
        try:
            if ext in IMAGE_EXT:
                items.append((f.stem, _png(Image.open(f))))
            elif ext == ".pdf":
                items += _pdf_pages(f, PDF_PAGES_PER_FILE)
            elif ext == ".pptx":
                pdf = _pptx_to_pdf(f)
                if pdf is None:
                    notes.append(f"{f.name}: LibreOffice is not installed, so a .pptx cannot be read; export it to PDF and put the PDF here")
                else:
                    items += _pdf_pages(pdf, PDF_PAGES_PER_FILE)
        except Exception as e:  # a broken file must not stop the run
            notes.append(f"{f.name}: could not be read ({e!r})")
    if len(items) > max_images:  # keep evenly spaced images
        step = len(items) / max_images
        items = [items[int(i * step)] for i in range(max_images)]
    return items, notes


def dhash(png: bytes, size: int = 8) -> int:
    """Difference hash: 64 bits describing the coarse light/dark structure of a slide."""
    im = Image.open(io.BytesIO(png)).convert("L").resize((size + 1, size), Image.LANCZOS)
    px = list(im.getdata())
    bits = 0
    for y in range(size):
        for x in range(size):
            bits = (bits << 1) | (px[y * (size + 1) + x] > px[y * (size + 1) + x + 1])
    return bits


def near_copies(ours: list[tuple[int, bytes]], refs: list[tuple[str, bytes]], max_distance: int = 6) -> list[dict]:
    """Slides of ours whose hash is within `max_distance` bits (of 64) of a reference: a layout copied wholesale looks like this."""
    rh = [(label, dhash(b)) for label, b in refs]
    hits = []
    for no, png in ours:
        h = dhash(png)
        for label, r in rh:
            d = bin(h ^ r).count("1")
            if d <= max_distance:
                hits.append({"slide": no, "reference": label, "distance": d})
    return hits
