"""Footer, title-page and watermark assets (editable via deck/footer.json).

`deck/footer.json` is the one place to edit: logo file, course code and name, page number on/off, layouts that hide the footer,
presenter names and the title-page details (paper citation, date, background photo, watermark, image credit).
`sync(deck_dir)` copies the config into the deck's theme and prepares the images in `public/`:
  footer-logo.png  the logo with its white margin cropped (small and legible)
  title-bg.jpg     the title-page photo, resized (the dark shading is applied in CSS so its strength is also editable)
  watermark.png    the coat of arms as a faint navy RGBA image for content slides
The pipeline calls it for every run; for the dev deck run `python -m papertrail.tools.footer`.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter

from papertrail.paths import ROOT
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


def prepare_title_bg(src: Path, dest: Path, width: int = 2560, focus_y: float = 0.5) -> None:
    """Cut a 16:9 band out of the photo (the slide shows it "cover" style) and save it at `width` px. focus_y is where the band is centred in a
    photo that is taller than 16:9 (0 = top, 1 = bottom); a photo that is wider than 16:9 is cut at the sides, centred."""
    im = Image.open(src).convert("RGB")
    band_h = round(im.width * 9 / 16)
    if band_h < im.height:
        top = min(max(round(focus_y * im.height - band_h / 2), 0), im.height - band_h)
        im = im.crop((0, top, im.width, top + band_h))
    elif round(im.height * 16 / 9) < im.width:
        band_w = round(im.height * 16 / 9)
        left = (im.width - band_w) // 2
        im = im.crop((left, 0, left + band_w, im.height))
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    elif im.width < width:
        # A small photo would be stretched by the browser (soft and blocky). Upscale it here with a better filter, sharpen the edges a little and add
        # fine grain so the remaining softness reads as photo texture. It cannot add detail: a larger photo (1920 px wide or more) is still better.
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
        im = im.filter(ImageFilter.UnsharpMask(radius=2.0, percent=80, threshold=2))
        grain = Image.effect_noise(im.size, 14).convert("RGB")
        im = ImageChops.add(im, grain, scale=1, offset=-128)
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, quality=90, optimize=True)


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
    from papertrail.common.profile import citation_line

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
            if key == "title_background":
                fn(src, pub / name, focus_y=float(cfg.get("title_background_focus", 0.5)))
            else:
                fn(src, pub / name)
        elif name == "watermark.png":  # switched off: a transparent pixel, so the stylesheet url() always resolves
            pub.mkdir(parents=True, exist_ok=True)
            Image.new("RGBA", (1, 1), (0, 0, 0, 0)).save(pub / name)
        elif (pub / name).exists():
            (pub / name).unlink()  # option switched off: do not leave a stale asset behind
    return cfg


if __name__ == "__main__":
    print(sync(ROOT / "deck"))
