"""Annotated PNGs (numbered element boxes) and the 4x5 deck contact sheet (SPEC §6 element_map, §7.7 step 4)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _font(size: int):
    for name in ("arial.ttf", "DejaVuSans.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def annotate(png: Path, elements: list[dict], out: Path) -> Path:
    """Draw a numbered box around each element so the critic can refer to element IDs (SlideAudit style)."""
    im = Image.open(png).convert("RGB")
    w, h = im.size
    dr = ImageDraw.Draw(im)
    f = _font(max(14, h // 40))
    for el in elements:
        x, y, bw, bh = el["bbox"]
        x0, y0, x1, y1 = x * w, y * h, (x + bw) * w, (y + bh) * h
        dr.rectangle([x0, y0, x1, y1], outline=(220, 30, 30), width=2)
        label = str(el["id"])
        tw = dr.textlength(label, font=f)
        dr.rectangle([x0, y0 - f.size - 2, x0 + tw + 8, y0], fill=(220, 30, 30))
        dr.text((x0 + 4, y0 - f.size - 2), label, fill=(255, 255, 255), font=f)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    return out


def contact_sheets(pngs: list[Path], out_dir: Path, cols: int = 4, rows: int = 5, thumb=(480, 270)) -> list[Path]:
    """One or more 4x5 grids of numbered slide thumbnails (20 per sheet)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    per = cols * rows
    f = _font(22)
    sheets = []
    for s in range(0, len(pngs), per):
        chunk = pngs[s:s + per]
        r = (len(chunk) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * thumb[0], r * thumb[1]), (255, 255, 255))
        dr = ImageDraw.Draw(sheet)
        for i, p in enumerate(chunk):
            im = Image.open(p).convert("RGB").resize(thumb)
            x, y = (i % cols) * thumb[0], (i // cols) * thumb[1]
            sheet.paste(im, (x, y))
            dr.rectangle([x, y, x + thumb[0] - 1, y + thumb[1] - 1], outline=(150, 150, 150))
            dr.rectangle([x, y, x + 44, y + 30], fill=(31, 35, 40))
            dr.text((x + 8, y + 3), str(s + i + 1), fill=(255, 255, 255), font=f)
        path = out_dir / f"contact_{s // per + 1}.png"
        sheet.save(path)
        sheets.append(path)
    return sheets
