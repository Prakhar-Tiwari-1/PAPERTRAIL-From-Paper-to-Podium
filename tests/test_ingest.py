import fitz

from papertrail.common.ctx import RunCtx
from papertrail.common.llm import Harness
from papertrail.stages import ingest


def make_pdf(path):
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((72, 80), "A Tiny Paper About Things", fontsize=22)
    p1.insert_text((72, 140), "1 Introduction", fontsize=14)
    p1.insert_text((72, 170), "We lose 39% of performance in multi-turn settings.", fontsize=10)
    for i in range(8):
        p1.insert_text((72, 190 + 12 * i), f"Body line number {i} of the introduction.", fontsize=10)
    p1.draw_rect(fitz.Rect(100, 300, 400, 500), fill=(0.8, 0.8, 1))
    p1.insert_text((100, 520), "Figure 1: Performance drop across tasks.", fontsize=10)
    p2 = doc.new_page()
    p2.insert_text((72, 80), "References", fontsize=14)
    p2.insert_text((72, 110), "[1] Laban, P. et al. 2025. Lost in conversation. arXiv.", fontsize=10)
    doc.save(path)


def test_pdf_fallback_ingest(tmp_path):
    pdf = tmp_path / "tiny.pdf"
    make_pdf(pdf)
    run = tmp_path / "run"
    ctx = RunCtx(run_dir=run, paper=str(pdf), config="full", h=Harness(run, model_factory=lambda s: None))
    ingest.run(ctx)
    md = (run / "paper.md").read_text(encoding="utf-8")
    assert "[p.1]" in md and "[p.2]" in md and "39%" in md
    assert "## 1 Introduction" in md
    info = ctx.load_json("ingested.json")
    assert info["source"] == "pdf" and info["n_pages"] == 2
    assert info["figures"] and (run / info["figures"][0]["path"]).exists()
    assert "Performance drop" in info["figures"][0]["caption"]


def test_missing_paper_gives_clear_error(tmp_path):
    run = tmp_path / "run"
    ctx = RunCtx(run_dir=run, paper="does-not-exist.pdf", config="full", h=Harness(run, model_factory=lambda s: None))
    try:
        ingest.run(ctx)
    except FileNotFoundError as e:
        assert "neither an arXiv ID" in str(e)
    else:
        raise AssertionError("expected FileNotFoundError")


def test_latex_tables_and_refs():
    tex = r"""\begin{table}\caption{Scores.}\begin{tabular}{lr}
    \toprule Model & Score \\ \midrule A & 45.1 \\ B & \textbf{39} \\ \bottomrule \end{tabular}\end{table}"""
    t = ingest.latex_tables(tex)
    assert t[0]["rows"][1] == ["A", "45.1"] and t[0]["caption"] == "Scores."


def test_safe_extract_blocks_traversal(tmp_path):
    import io
    import tarfile

    tgz = tmp_path / "x.tgz"
    with tarfile.open(tgz, "w:gz") as tf:
        info = tarfile.TarInfo("../evil.txt")
        data = b"x"
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
        ok = tarfile.TarInfo("good.tex")
        ok.size = 1
        tf.addfile(ok, io.BytesIO(b"y"))
    dest = tmp_path / "out"
    dest.mkdir()
    ingest.safe_extract(tgz, dest)
    assert (dest / "good.tex").exists() and not (tmp_path / "evil.txt").exists()


def test_heatmap_cells_wraptable_and_pdf_numbering():
    assert ingest._clean_cell("DFE9F830.9") == "30.9" and ingest._clean_cell("FFFFFF 27.4") == "27.4"
    assert ingest._clean_cell("3.1-8B") == "3.1-8B" and ingest._clean_cell("123456") == "123456"
    tex = (r"\begin{wraptable}{l}{0.4\linewidth}\caption{Answer earliness breakdown.}\begin{tabular}{lc}" "\n"
           r"Model & A \\ x & DFE9F830.9 \\ \end{tabular}\end{wraptable}")
    t = ingest.latex_tables(tex)
    assert t and t[0]["rows"][1] == ["x", "30.9"]
    md = "[p.20]\nTable 6: Answer earliness breakdown.\n"
    assert ingest.relabel_tables(t, md)[0]["id"] == "Table 6"


def test_input_prefers_tex_file_over_same_named_folder(tmp_path):
    (tmp_path / "sections" / "appendix").mkdir(parents=True)
    (tmp_path / "sections" / "appendix.tex").write_text("APPENDIX TEXT", encoding="utf-8")
    (tmp_path / "main.tex").write_text(r"\begin{document}\input{sections/appendix}\end{document}", encoding="utf-8")
    assert "APPENDIX TEXT" in ingest.read_tex(tmp_path)


def test_two_line_title_is_joined(tmp_path):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 90), "A Long Title That Wraps", fontsize=24)
    page.insert_text((72, 124), "Onto A Second Line", fontsize=24)
    for i in range(12):
        page.insert_text((72, 180 + 14 * i), "Body text of the paper line.", fontsize=10)
    pdf = tmp_path / "t.pdf"
    doc.save(pdf)
    assert ingest.pdf_to_markdown(pdf)[2] == "A Long Title That Wraps Onto A Second Line"
