import io
import json

from PIL import Image, ImageDraw

from common.schemas import Plan, PlanSlide, QAIssue, Quiz, QuizItem, validate_plan, validate_quiz
from qa.source_map import parse_slides


# ------------------------------------------------------------------ quiz
def item(kind="concept", ans="Because the first answer sticks, so later details are ignored.", ev="paper", anchor="p.5", q="Why does the first answer stick?"):
    return QuizItem(kind=kind, question=q, answer=ans, anchor=anchor, evidence=ev)


def good_quiz():
    items = [item(q=f"Concept question number {i}?") for i in range(4)]
    items += [item(kind="what_if", q=f"What if we change setting {i}?") for i in range(3)]
    items += [item(kind="what_if", q="What if the model is larger?", ev="reasoned", ans="Not tested: a larger model has the same unreliability gap in the paper.")]
    return Quiz(items=items)


def test_good_quiz_passes():
    assert validate_quiz(good_quiz(), n_pages=36) == []


def test_quiz_needs_seven_or_eight_and_three_what_ifs():
    q = good_quiz()
    q.items = q.items[:6]
    assert any("need 7 or 8" in e for e in validate_quiz(q))
    q2 = good_quiz()
    for i in q2.items:
        i.kind = "concept"
    assert any("what-if" in e for e in validate_quiz(q2))


def test_reasoned_answers_must_say_not_tested_and_limits_hold():
    q = good_quiz()
    q.items[-1].answer = "A larger model has the same gap."
    assert any("must start with 'Not tested:'" in e for e in validate_quiz(q))
    q = good_quiz()
    q.items[0].question = " ".join(["word"] * 17)
    q.items[1].answer = " ".join(["word"] * 30)
    errs = validate_quiz(q)
    assert any("question 1 has 17 words" in e for e in errs) and any("answer 2 has 30 words" in e for e in errs)
    q = good_quiz()
    q.items[0].anchor = "somewhere"
    assert any("valid anchor" in e for e in validate_quiz(q))


def test_quiz_slide_is_generated_from_quiz_json_with_questions_above_answers(tmp_path):
    from report import quiz_slide

    md = ("---\ntheme: ./theme\nlayout: title\n---\n\n# T\n\n<!--\nn\n-->\n\n---\nlayout: claim-quiz\n---\n\n# Check it\n\nold body\n\n"
          "<!--\nrun the quiz\n-->\n\n---\nlayout: workflow\n---\n\n# Tools\n\n<!--\nw\n-->\n")
    new, no = quiz_slide.apply(md, good_quiz())
    assert no == 2
    s = parse_slides(new)[1]
    assert s.layout == "claim-quiz" and "old body" not in s.text and "run the quiz" in s.text and "# Check it" in s.text
    assert s.text.count('class="qa-q"') == 8 and s.text.count('class="qa-a"') == 8
    assert s.text.index("qa-questions") < s.text.index("qa-answers") and "v-click" in s.text
    assert len(parse_slides(new)) == 3                       # the HTML did not split the slide
    again, _ = quiz_slide.apply(new, good_quiz())
    assert again == new                                      # idempotent


def test_quiz_slide_patch_registers_answers_as_claims(tmp_path):
    from report import quiz_slide

    (tmp_path / "deck").mkdir()
    (tmp_path / "deck" / "slides.md").write_text("---\nlayout: claim-quiz\n---\n\n# Q\n\n<!--\nn\n-->\n", encoding="utf-8")
    (tmp_path / "quiz.json").write_text(good_quiz().model_dump_json(), encoding="utf-8")
    (tmp_path / "deck.json").write_text(json.dumps({"claims": [{"slide": 1, "text": "stale", "kind": "claim", "source": "p.1"}]}), encoding="utf-8")
    assert quiz_slide.patch(tmp_path)
    claims = json.loads((tmp_path / "deck.json").read_text())["claims"]
    assert len(claims) == 8 and all(c["slide"] == 1 and c["source"].startswith("p.") for c in claims)


# ------------------------------------------------------------------ plan rules for the quiz slide
def plan_with(n=14, quiz_at=9):
    sl = [PlanSlide(id=str(i), title=f"Motivation setup metrics headline result failure prior limitations our analysis takeaway {i}", purpose="x", key_points=[], minutes=1.4,
                    layout="claim-quiz" if i == quiz_at else "title" if i == 0 else "claim-figure") for i in range(n)]
    sl[-1].title, sl[-1].purpose, sl[-1].layout = "Tools & Workflow", "tools and workflow", "workflow"
    return Plan(story_arc="a", slides=sl, backup_slides=[{"id": str(i), "title": "b", "purpose": "p"} for i in range(3)])


def test_plan_needs_exactly_one_quiz_slide_not_first_or_last():
    assert not any("quiz" in e for e in validate_plan(plan_with(), []))
    assert any("exactly one quiz slide" in e for e in validate_plan(plan_with(quiz_at=99), []))
    assert any("goes after the results" in e for e in validate_plan(plan_with(quiz_at=0), []))


def test_plan_slide_count_is_13_to_16():
    assert any("need 13-16" in e for e in validate_plan(plan_with(n=12), []))
    assert not any("need 13-16" in e for e in validate_plan(plan_with(n=16, quiz_at=10), []))
    assert any("need 13-16" in e for e in validate_plan(plan_with(n=18), []))


# ------------------------------------------------------------------ per-slide revision
DECK = ("---\ntheme: ./theme\nlayout: title\n---\n\n# T\n\n<!--\nn1\n-->\n\n---\nlayout: claim-bullets\n---\n\n# Two\n\n- a\n\n<!--\nn2\n-->\n\n"
        "---\nlayout: claim-figure\n---\n\n# Three\n\n<!--\nn3\n-->\n\n---\nlayout: workflow\n---\n\n# Tools\n\n<!--\nn4\n-->\n")


def test_splice_replaces_only_the_named_slides():
    from stages.revise import splice

    new = splice(DECK, {2: "---\nlayout: claim-table\n---\n\n# Two, fixed\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n<!--\nn2 new\n-->"})
    s = parse_slides(new)
    assert len(s) == 4 and s[1].layout == "claim-table" and "fixed" in s[1].text
    assert [x.layout for x in s] == ["title", "claim-table", "claim-figure", "workflow"]
    assert parse_slides(DECK)[2].text == s[2].text and parse_slides(DECK)[3].text == s[3].text   # untouched slides identical


def test_splice_two_slides_keeps_order():
    from stages.revise import splice

    new = splice(DECK, {2: "---\nlayout: claim-bullets\n---\n\n# Two b\n\n<!--\nx\n-->", 3: "---\nlayout: claim-figure\n---\n\n# Three b\n\n<!--\ny\n-->"})
    t = [l for s in parse_slides(new) for l in s.lines if l.startswith("# ")]
    assert t == ["# T", "# Two b", "# Three b", "# Tools"]


def test_only_content_slides_with_high_issues_are_targeted():
    from stages.revise import targets_for

    slides = parse_slides(DECK)
    mk = lambda slide, sev="high": QAIssue(round=1, source="automatic", slide=slide, category="c", severity=sev, detail="d")
    assert targets_for(slides, [mk(1), mk(2), mk(3), mk(4), mk(3, "low")]) == [2, 3]   # title and workflow are generated, never rewritten


# ------------------------------------------------------------------ triage: no forced issues
def vi(cat, slide=1, sev="high", src="vision_slide"):
    return QAIssue(round=1, source=src, slide=slide, category=cat, severity=sev, detail="x")


def test_unconfirmed_layout_claims_are_demoted_confirmed_ones_stay():
    from qa.triage import triage

    out = triage([vi("Content Overflow/Cut-off"), vi("Insufficient Color Contrast for Readability", slide=2)], {1: set(), 2: {"contrast"}}, {1: [], 2: []}, set())
    assert out[0].severity == "low" and "not confirmed by measurement" in out[0].detail
    assert out[1].severity == "high"


def test_occlusion_needs_a_real_overlap():
    from qa.triage import overlapping, triage

    apart = [{"bbox": [0.1, 0.1, 0.3, 0.1]}, {"bbox": [0.1, 0.5, 0.3, 0.1]}]
    panel = [{"bbox": [0.1, 0.1, 0.8, 0.5]}, {"bbox": [0.2, 0.2, 0.3, 0.1]}]       # text inside a panel is design
    clash = [{"bbox": [0.1, 0.1, 0.4, 0.2]}, {"bbox": [0.3, 0.2, 0.4, 0.2]}]
    assert not overlapping(apart) and not overlapping(panel) and overlapping(clash)
    assert triage([vi("Occluded Content")], {1: set()}, {1: apart}, set())[0].severity == "low"
    assert triage([vi("Occluded Content")], {1: set()}, {1: clash}, set())[0].severity == "high"


def test_an_issue_still_reported_after_a_fix_attempt_is_contested():
    from qa.triage import triage

    out = triage([vi("Cluttered Layout")], {1: set()}, {1: []}, {(1, "Cluttered Layout")})
    assert out[0].severity == "low" and "contested" in out[0].detail
    assert triage([vi("Cluttered Layout", src="automatic")], {1: set()}, {1: []}, {(1, "Cluttered Layout")})[0].severity == "high"   # measurements are never contested


# ------------------------------------------------------------------ empty space
def test_sparse_slides_are_flagged_with_an_instruction_to_add_a_visual(tmp_path):
    from stages.render_loop import automatic_issues

    slides = parse_slides(DECK)
    for s, met in zip(slides, [{"coverage": 0.2, "empty_band_px": 300}, {"coverage": 0.3, "empty_band_px": 208},
                               {"coverage": 0.7, "empty_band_px": 16}, {"coverage": 0.6, "empty_band_px": 48}]):
        (tmp_path / f"slide-{s.no}.checks.json").write_text("[]")
        (tmp_path / f"slide-{s.no}.metrics.json").write_text(json.dumps(met))
    issues = automatic_issues(1, tmp_path, slides)
    sparse = [i for i in issues if i.category == "sparse_slide"]
    assert [i.slide for i in sparse] == [2] and sparse[0].severity == "high"       # title is exempt, 70% coverage is fine
    assert "add a relevant visual" in sparse[0].detail and "Do not add text" in sparse[0].detail


# ------------------------------------------------------------------ reference slides
def slide_png(seed, size=(640, 360)):
    im = Image.new("RGB", size, (250, 250, 247))
    d = ImageDraw.Draw(im)
    if seed == 0:
        d.rectangle([30, 30, 600, 70], fill=(10, 50, 90)); d.rectangle([30, 120, 300, 330], fill=(200, 200, 200))
    elif seed == 1:
        d.ellipse([200, 100, 500, 330], fill=(30, 30, 30)); d.rectangle([20, 20, 120, 60], fill=(200, 100, 0))
    else:
        for k in range(6):
            d.rectangle([30 + k * 95, 340 - k * 45, 100 + k * 95, 340], fill=(0, 100, 150))
    b = io.BytesIO(); im.save(b, "PNG")
    return b.getvalue()


def test_collect_reads_images_and_pdf_and_reports_unreadable_files(tmp_path):
    import pymupdf

    from tools.references import collect

    (tmp_path / "a.png").write_bytes(slide_png(0))
    (tmp_path / "broken.png").write_bytes(b"not an image")
    doc = pymupdf.open()
    for _ in range(8):
        doc.new_page().insert_text((72, 72), "slide")
    doc.save(tmp_path / "deck.pdf")
    (tmp_path / "deck.pptx").write_bytes(b"x")
    items, notes = collect(tmp_path)
    labels = [l for l, _ in items]
    assert "a" in labels and sum(1 for l in labels if l.startswith("deck p.")) == 5      # 5 evenly spaced pages of 8
    assert any("broken.png" in n for n in notes)
    assert collect(tmp_path / "missing")[0] == []


def test_near_copy_guard_flags_a_copied_layout_not_a_different_one():
    from tools.references import near_copies

    refs = [("ref0", slide_png(0)), ("ref1", slide_png(1))]
    assert near_copies([(1, slide_png(0))], refs) == [{"slide": 1, "reference": "ref0", "distance": 0}]
    assert near_copies([(2, slide_png(2))], refs) == []


def test_style_stage_without_references_writes_an_empty_brief(tmp_path):
    from common.ctx import RunCtx
    from common.llm import Harness
    from stages import style

    run = tmp_path / "run"
    ctx = RunCtx(run_dir=run, paper="", config="full", h=Harness(run, model_factory=lambda s: None))
    ctx.extra["refs"] = str(tmp_path / "no_such_folder")
    style.run(ctx)
    b = json.loads((run / "style_brief.json").read_text())
    assert b == {"examples": [], "principles": [], "quality_bar": []}
    from stages import author

    assert author.style_block(ctx) == "(no reference slides given)"


def test_reviser_prompt_fills_every_placeholder(tmp_path):
    """Regression: the reviser prompt once failed with a missing {style} field at run time."""
    from common.ctx import RunCtx
    from common.llm import Harness
    from stages import revise

    run = tmp_path / "run"
    run.mkdir()
    (run / "figures").mkdir()
    (run / "ingested.json").write_text(json.dumps({"figures": [{"id": "Fig. 1", "path": "figures/fig1.svg", "caption": "c"}]}), encoding="utf-8")
    (run / "tables.json").write_text("[]", encoding="utf-8")
    (run / "plan.json").write_text(json.dumps({"slides": [{"minutes": 1.0}, {"minutes": 1.5}]}), encoding="utf-8")
    ctx = RunCtx(run_dir=run, paper="", config="full", h=Harness(run, model_factory=lambda s: None))
    slides = parse_slides(DECK)
    iss = [QAIssue(round=1, source="automatic", slide=2, category="sparse_slide", severity="high", detail="empty")]
    p = revise.build_prompt(ctx, slides, iss, [2], [])
    assert "### Slide 2 (claim-bullets)" in p and "empty" in p and "(no reference slides given)" in p and "{" + "style" + "}" not in p
