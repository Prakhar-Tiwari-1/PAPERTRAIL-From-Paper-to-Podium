"""7.0 Ingest (no model). arXiv ID or PDF -> paper.md ([p.N] markers), figures/, tables.json, refs.json.

paper.md always comes from the PDF (it is the only source of page anchors). The arXiv LaTeX source, when
available, supplies figures (PDF -> SVG), tables and the bibliography; otherwise PyMuPDF finds them in the PDF.
"""
from __future__ import annotations

import re
from collections import Counter
import shutil
import tarfile
from pathlib import Path

import fitz  # PyMuPDF
import httpx

from papertrail.common.ctx import RunCtx
from papertrail.common.papertext import make_llm_text
from papertrail.tools import arxiv_meta
from papertrail.common.schemas import FigureRef, Ingested, RefEntry

ARXIV_RE = re.compile(r"^(\d{4}\.\d{4,5})(v\d+)?$")
UA = {"User-Agent": "papertrail/0.1 (course project)"}


# ------------------------------------------------------------------ acquisition
def fetch_arxiv(arxiv_id: str, run_dir: Path) -> tuple[Path, Path | None]:
    pdf = run_dir / "source.pdf"
    with httpx.Client(timeout=120, follow_redirects=True, headers=UA) as c:
        r = c.get(f"https://arxiv.org/pdf/{arxiv_id}")
        r.raise_for_status()
        pdf.write_bytes(r.content)
        src_dir: Path | None = None
        try:
            r2 = c.get(f"https://arxiv.org/e-print/{arxiv_id}")
            if r2.status_code == 200 and len(r2.content) > 1000:
                tgz = run_dir / "source.tgz"
                tgz.write_bytes(r2.content)
                src_dir = run_dir / "source"
                src_dir.mkdir(exist_ok=True)
                safe_extract(tgz, src_dir)
        except Exception:  # no source (e.g. PDF-only submission): fall back to the PDF
            src_dir = None
    return pdf, src_dir


def safe_extract(tgz: Path, dest: Path) -> None:
    """The tarball is untrusted: refuse absolute paths, traversal and links; cap the total size."""
    total = 0
    with tarfile.open(tgz) as tf:
        for m in tf.getmembers():
            target = (dest / m.name).resolve()
            if not str(target).startswith(str(dest.resolve())) or m.issym() or m.islnk() or m.isdev():
                continue
            total += m.size
            if total > 200 * 1024 * 1024:
                raise ValueError("source archive too large")
            tf.extract(m, dest, filter="data")


# ------------------------------------------------------------------ paper.md from the PDF
def pdf_to_markdown(pdf: Path) -> tuple[str, int, str]:
    doc = fitz.open(pdf)
    sizes: Counter[float] = Counter()
    pages_lines: list[list[tuple[str, float, bool]]] = []
    for page in doc:
        lines = []
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                spans = line["spans"]
                text = "".join(s["text"] for s in spans).strip()
                if not text:
                    continue
                size = max(s["size"] for s in spans)
                bold = any("bold" in s["font"].lower() for s in spans)
                lines.append((text, size, bold))
                sizes[round(size * 2) / 2] += len(text)
        pages_lines.append(lines)
    # body size = the most common size by character count among text of 8.5pt or more: footnotes, figure labels and
    # appendix tables are set smaller and must not drag it down (a median over lines put it under 7pt on a long paper)
    text_sizes = Counter({k: v for k, v in sizes.items() if k >= 8.5}) or sizes
    body = max(text_sizes, key=text_sizes.get) if text_sizes else 10.0
    out = []
    title_parts: list[str] = []
    title_done = False
    for n, lines in enumerate(pages_lines, start=1):
        out.append(f"\n[p.{n}]\n")
        for text, size, bold in lines:
            is_heading = len(text) < 90 and (size > body * 1.15 or (bold and re.match(r"^(\d+(\.\d+)*\.?|[A-Z]\.?)\s+\S", text)))
            if n == 1 and not title_done:
                # the title may wrap over several lines of the same large size
                if size > body * 1.4 and not text.lower().startswith("arxiv"):
                    title_parts.append(text)
                elif title_parts:
                    title_done = True
            out.append(("## " + text) if is_heading else text)
    title = " ".join(title_parts)
    return "\n".join(out), len(doc), title


# ------------------------------------------------------------------ LaTeX helpers
def read_tex(src: Path) -> str:
    texs = sorted(src.rglob("*.tex"), key=lambda p: p.stat().st_size, reverse=True)
    main = ""
    for t in texs:
        s = t.read_text(encoding="utf-8", errors="ignore")
        if r"\begin{document}" in s:
            main = s
            break
    if not main and texs:
        main = texs[0].read_text(encoding="utf-8", errors="ignore")
    # inline \input / \include (one level of nesting is enough for most papers)
    def inline(m):
        name = m.group(1)
        for cand in (src / (name + ".tex"), src / name):  # LaTeX tries name.tex first; a folder may share the name
            if cand.is_file():
                return cand.read_text(encoding="utf-8", errors="ignore")
        return ""

    return re.sub(r"\\(?:input|include)\{([^}]+)\}", inline, main)


def strip_tex(s: str) -> str:
    s = re.sub(r"%.*", "", s)
    s = re.sub(r"\\(?:cellcolor|rowcolor|columncolor)(?:\[[^\]]*\])?\{[^}]*\}", "", s)
    s = re.sub(r"\\c?midrule(?:\([^)]*\))?(?:\[[^\]]*\])?\{[^}]*\}", "", s)
    s = re.sub(r"\\(?:multicolumn|multirow)\{[^}]*\}\{[^}]*\}\{((?:[^{}]|\{[^{}]*\})*)\}", r"\1", s)
    s = re.sub(r"\\(textbf|textit|emph|texttt|underline|mathbf|mathrm|text)\{([^{}]*)\}", r"\2", s)
    s = re.sub(r"\\(cite|ref|label|footnote)\{[^}]*\}", "", s)
    s = s.replace(r"\%", "%").replace(r"\&", "&").replace("$", "").replace("~", " ")
    s = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", "", s)
    return re.sub(r"\s+", " ", s.replace("{", "").replace("}", "")).strip()


def _clean_cell(c: str) -> str:
    """Heat-map cells carry their colour as a leading hex code: 'FFFFFF 27.4' or glued 'DFE9F830.9'. Keep only the value."""
    c = re.sub(r"^[0-9A-Fa-f]{6}\s+(?=[\d\-])", "", c)
    m = re.match(r"^[0-9A-Fa-f]{6}(\d+(?:\.\d+)?)$", c)
    return m.group(1) if m else c


def latex_tables(tex: str) -> list[dict]:
    tables = []
    for i, m in enumerate(re.finditer(r"\\begin\{(table\*?|wraptable|sidewaystable)\}(.*?)\\end\{\1\}", tex, re.S), start=1):
        block = m.group(2)
        cap = re.search(r"\\caption\{((?:[^{}]|\{[^{}]*\})*)\}", block)
        tab = re.search(r"\\begin\{tabular\*?\}.*?\n(.*?)\\end\{tabular\*?\}", block, re.S)
        rows = []
        if tab:
            for raw in re.split(r"\\\\", tab.group(1)):
                raw = re.sub(r"\\(hline|toprule|midrule|bottomrule|cline\{[^}]*\})", "", raw)
                cells = [_clean_cell(strip_tex(c)) for c in raw.split("&")]
                if any(cells):
                    rows.append(cells)
        tables.append({"id": f"Table {i}", "caption": strip_tex(cap.group(1)) if cap else "", "rows": rows, "source": "latex"})
    return tables


def _norm_caption(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def relabel_tables(tables: list[dict], md: str) -> list[dict]:
    """LaTeX order is not the printed order (appendix tables, input files): number each table by the PDF's own "Table N:" caption."""
    pdf = {}
    for m in re.finditer(r"^Table (\d+)\s*[:.]\s*(.+)$", md, re.M):
        pdf.setdefault(m.group(1), _norm_caption(m.group(2))[:40])
    for t in tables:
        key = _norm_caption(t.get("caption", ""))[:40]
        for num, cap in pdf.items():
            if key and cap and (key.startswith(cap[:30]) or cap.startswith(key[:30])):
                t["id"] = f"Table {num}"
                break
    return tables


def latex_figures(tex: str, src: Path, out_dir: Path) -> list[FigureRef]:
    figs = []
    for i, m in enumerate(re.finditer(r"\\begin\{figure\*?\}(.*?)\\end\{figure\*?\}", tex, re.S), start=1):
        block = m.group(1)
        cap = re.search(r"\\caption\{((?:[^{}]|\{[^{}]*\})*)\}", block)
        inc = re.search(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", block)
        if not inc:
            continue
        name = inc.group(1)
        cand = [p for p in [src / name, *(src / (name + e) for e in (".pdf", ".png", ".jpg", ".jpeg"))] if p.exists()]
        if not cand:
            continue
        f = cand[0]
        dest = out_dir / f"fig{i}"
        if f.suffix.lower() == ".pdf":
            d = fitz.open(f)
            dest = dest.with_suffix(".svg")
            dest.write_text(d[0].get_svg_image(), encoding="utf-8")
        else:
            dest = dest.with_suffix(f.suffix.lower())
            shutil.copy(f, dest)
        figs.append(FigureRef(id=f"Fig. {i}", path=str(dest.relative_to(out_dir.parent)), caption=strip_tex(cap.group(1)) if cap else ""))
    return figs


def latex_refs(src: Path) -> list[RefEntry]:
    refs = []
    for bbl in src.rglob("*.bbl"):
        txt = bbl.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r"\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}(.*?)(?=\\bibitem|\\end\{thebibliography\})", txt, re.S):
            body = strip_tex(m.group(2))
            yr = re.search(r"\b(19|20)\d{2}\b", body)
            refs.append(RefEntry(key=m.group(1), title=body[:300], year=int(yr.group(0)) if yr else None))
    return refs


# ------------------------------------------------------------------ PDF fallbacks
def pdf_figures(pdf: Path, out_dir: Path) -> list[FigureRef]:
    """Crop each figure from its page: union of images/drawings above the caption, rendered at 300 dpi."""
    doc = fitz.open(pdf)
    figs: list[FigureRef] = []
    seen: set[str] = set()
    for pno, page in enumerate(doc):
        for block in page.get_text("blocks"):
            x0, y0, x1, y1, text = block[:5]
            m = re.match(r"^\s*(Figure|Fig\.)\s*(\d+)\s*[:.]", text)
            if not m or m.group(2) in seen:
                continue
            seen.add(m.group(2))
            rects = [fitz.Rect(i["bbox"]) for i in page.get_image_info()] + [d["rect"] for d in page.get_drawings()]
            above = [r for r in rects if r.y1 <= y0 + 2 and r.y0 > y0 - 450 and r.width > 8 and r.height > 8]
            if above:
                u = above[0]
                for r in above[1:]:
                    u |= r
                clip = fitz.Rect(max(u.x0 - 6, 0), max(u.y0 - 6, 0), min(u.x1 + 6, page.rect.x1), y0 - 2)
            else:  # nothing vector/raster detected: keep the whole page, honestly
                clip = page.rect
            pix = page.get_pixmap(clip=clip, dpi=300)
            dest = out_dir / f"fig{m.group(2)}.png"
            pix.save(dest)
            cap = " ".join(text.split())[:400]
            figs.append(FigureRef(id=f"Fig. {m.group(2)}", path=str(dest.relative_to(out_dir.parent)), caption=cap, page=pno + 1))
    return figs


def pdf_tables(pdf: Path) -> list[dict]:
    doc = fitz.open(pdf)
    tables = []
    for pno, page in enumerate(doc, start=1):
        try:
            found = page.find_tables()
        except Exception:
            continue
        for t in found.tables:
            rows = [[(c or "").replace("\n", " ").strip() for c in r] for r in t.extract()]
            if len(rows) >= 2:
                tables.append({"id": f"p.{pno} table {len(tables) + 1}", "caption": "", "rows": rows, "source": "pdf", "page": pno})
    # attach captions "Table N:" found on the same page
    for t in tables:
        page = doc[t["page"] - 1]
        for block in page.get_text("blocks"):
            m = re.match(r"^\s*Table\s*(\d+)\s*[:.]\s*(.*)", block[4], re.S)
            if m and not t["caption"]:
                t["id"], t["caption"] = f"Table {m.group(1)}", " ".join(m.group(2).split())[:300]
    return tables


def pdf_refs(md: str) -> list[RefEntry]:
    m = re.search(r"\n## (References|REFERENCES|Bibliography)\s*\n", md)
    if not m:
        return []
    tail = md[m.end():]
    tail = re.sub(r"\[p\.\d+\]", "", tail)
    parts = re.split(r"\n(?=\[\d+\]|[A-Z][a-zA-Z\-]+,\s+[A-Z]\.)", tail)
    refs = []
    for p in parts:
        p = " ".join(p.split())
        if len(p) < 30:
            continue
        yr = re.search(r"\b(19|20)\d{2}\b", p)
        refs.append(RefEntry(title=p[:300], year=int(yr.group(0)) if yr else None))
    return refs


# ------------------------------------------------------------------ stage entry
def run(ctx: RunCtx) -> None:
    run_dir = ctx.run_dir
    paper = ctx.paper
    m = ARXIV_RE.match(paper.strip())
    src: Path | None = None
    if m:
        paper_id = m.group(1)
        pdf, src = fetch_arxiv(paper.strip(), run_dir)
    else:
        pdf = Path(paper)
        if not pdf.exists():
            raise FileNotFoundError(f"--paper {paper!r} is neither an arXiv ID nor an existing PDF")
        paper_id = pdf.stem
        shutil.copy(pdf, run_dir / "source.pdf")
        pdf = run_dir / "source.pdf"

    md, n_pages, title = pdf_to_markdown(pdf)
    ctx.p("paper.md").write_text(md, encoding="utf-8")
    ctx.p("paper_llm.md").write_text(make_llm_text(md), encoding="utf-8")  # what prompts see (small); paper.md stays the verification source

    fig_dir = ctx.p("figures", ".keep").parent
    figures: list[FigureRef] = []
    tables: list[dict] = []
    refs: list[RefEntry] = []
    source = "pdf"
    if src is not None:
        tex = read_tex(src)
        if tex:
            source = "arxiv-latex"
            figures = latex_figures(tex, src, fig_dir)
            tables = relabel_tables(latex_tables(tex), md)
            refs = latex_refs(src)
            t = re.search(r"\\title\{((?:[^{}]|\{[^{}]*\})*)\}", tex)
            if t and strip_tex(t.group(1)) and not title:  # the printed title wins: the LaTeX one can be an older variant
                title = strip_tex(t.group(1))
    if not figures:
        figures = pdf_figures(pdf, fig_dir)
    if not tables:
        tables = pdf_tables(pdf)
    if not refs:
        refs = pdf_refs(md)

    ctx.save("tables.json", tables)
    ctx.save("refs.json", [r.model_dump() for r in refs])
    meta = arxiv_meta.fetch(paper_id) if m else {}   # authors, year, venue for the title page and the captions; best effort
    ctx.save("ingested.json", Ingested(paper_id=paper_id, title=title or meta.get("title") or paper_id, source=source, n_pages=n_pages,
                                       figures=figures, n_tables=len(tables), n_refs=len(refs), authors=meta.get("authors", []),
                                       year=meta.get("year"), venue=meta.get("venue", "")))
