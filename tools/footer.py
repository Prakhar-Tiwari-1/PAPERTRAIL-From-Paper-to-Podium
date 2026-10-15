"""Footer, title-page and watermark assets (editable via deck/footer.json).

`deck/footer.json` is the one place to edit: logo file, course code and name, page number on/off, layouts that hide the footer,
presenter names and the title-page details (paper citation, date, background photo, watermark, image credit).
`sync(deck_dir)` copies the config into the deck's theme and prepares the images in `public/`:
  footer-logo.png  the logo with its white margin cropped (small and legible)
  title-bg.jpg     the title-page photo, resized (the dark shading is applied in CSS so its strength is also editable)
  watermark.png    the coat of arms as a faint navy RGBA image for content slides
The pipeline calls it for every run; for the dev deck run `python -m tools.footer`.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "deck" / "footer.json"
NAVY = (6, 58, 89)


def load(path: Path = SRC) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve(p: str) -> Path:
    q = Path(p)
    return q if q.is_absolute() else ROOT / q


def prepare_logo(src: Path, dest: Path, pad: int = 6, max_h: int = 120) -> None:
    """Crop the white margin off a logo and save a small PNG."""
    im = Image.open(src).convert("RGB")
    bg = Image.new("RGB", im.size, (255, 255, 255))
    box = ImageChops.difference(im, bg).convert("L").point(lambda v: 255 if v > 18 else 0).getbbox()
    if box:
        l, t, r, b = box
        im = im.crop((max(l - pad, 0), max(t - pad, 0), min(r + pad, im.width), min(b + pad, im.height)))
    if im.height > max_h:
        im = im.resize((round(im.width * max_h / im.height), max_h), Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest)


def prepare_title_bg(src: Path, dest: Path, width: int = 1920) -> None:
    im = Image.open(src).convert("RGB")
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, quality=82, optimize=True)


def prepare_watermark(src: Path, dest: Path, strength: float = 0.11, height: int = 700) -> None:
    """Dark line art on white -> navy with alpha proportional to darkness (white becomes fully transparent)."""
    im = Image.open(src).convert("L")
    if im.height < height:
        im = im.resize((round(im.width * height / im.height), height), Image.LANCZOS)
    alpha = im.point(lambda v: int(max(0, 255 - v) * strength))
    out = Image.new("RGBA", im.size, NAVY + (0,))
    out.putalpha(alpha)
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.save(dest)


def sync(deck_dir: Path, config: Path = SRC, run_dir: Path | None = None) -> dict:
    """Write the footer config into <deck_dir>/theme/ and prepare the images under <deck_dir>/public/.
    With a run_dir the title-page citation is resolved: the paper profile's, else the text in footer.json, else built from the arXiv metadata."""
    from common.profile import citation_line

    cfg = load(config)
    if run_dir is not None:
        cfg["paper_citation"] = citation_line(run_dir, cfg.get("paper_citation", ""))
    (deck_dir / "theme").mkdir(parents=True, exist_ok=True)
    (deck_dir / "theme" / "footer.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    pub = deck_dir / "public"
    jobs = (("logo", "footer-logo.png", prepare_logo), ("title_background", "title-bg.jpg", prepare_title_bg),
            ("watermark", "watermark.png", prepare_watermark))
    for key, name, fn in jobs:
        if cfg.get(key):
            src = _resolve(cfg[key])
            if not src.exists():
                raise FileNotFoundError(f"{key} file not found: {src} (edit deck/footer.json)")
            fn(src, pub / name)
        elif name == "watermark.png":  # switched off: a transparent pixel, so the stylesheet url() always resolves
            pub.mkdir(parents=True, exist_ok=True)
            Image.new("RGBA", (1, 1), (0, 0, 0, 0)).save(pub / name)
        elif (pub / name).exists():
            (pub / name).unlink()  # option switched off: do not leave a stale asset behind
    return cfg


if __name__ == "__main__":
    print(sync(ROOT / "deck"))
