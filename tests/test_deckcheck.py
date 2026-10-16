from papertrail.common.deckcheck import notes_of, split_main_backup, validate_deck, word_limit, words
from papertrail.common.repair import fill
from papertrail.qa.source_map import parse_slides

VISUAL = "```mermaid\nflowchart LR\n  A-->B\n```"
QUIZ_BODY = ('<div class="qa-board">\n<div class="qa-block qa-questions">\n'
             + "\n".join(f'<div class="qa-q"><span class="qa-n">{n}</span><span>Question {n}?</span></div>' for n in range(1, 7))
             + "\n</div>\n</div>")


def make_deck(n_main=13, n_backup=3, notes_words=170, last_layout="workflow", quiz=True):
    """title + content slides + quiz + workflow (n_main in total), then Backup and the backup slides."""
    note = " ".join(["word"] * notes_words)
    parts = ["---\ntheme: ./theme\nrouterMode: hash\nlayout: title\n---\n\n# Title\n\n<!--\n" + note + "\n-->\n"]
    for i in range(2, n_main - (1 if quiz else 0)):
        parts.append(f"---\nlayout: claim-diagram\n---\n\n# Claim number {i} holds\n\n{VISUAL}\n\n<!--\n{note}\n-->\n")
    if quiz:
        parts.append(f"---\nlayout: claim-quiz\n---\n\n# Check your understanding\n\n{QUIZ_BODY}\n\n<!--\n{note}\n-->\n")
    parts.append(f"---\nlayout: {last_layout}\n---\n\n# Tools and workflow\n\n<!--\n{note}\n-->\n")
    parts.append("---\nlayout: section\n---\n\n# Backup\n\n<!--\nbackup\n-->\n")
    for i in range(n_backup):
        parts.append(f"---\nlayout: claim-diagram\n---\n\n# Backup claim {i}\n\n{VISUAL}\n\n<!--\nnotes\n-->\n")
    return "\n".join(parts)


def test_valid_deck_passes(tmp_path):
    md = make_deck(n_main=13, notes_words=170)  # 13 * 170 = 2210 words, about 16 minutes
    assert validate_deck(md, tmp_path, check_mermaid=False) == []


def test_main_backup_split():
    main, backup = split_main_backup(parse_slides(make_deck()))
    assert len(main) == 13 and backup[0].layout == "section" and len(backup) == 4


def test_too_few_slides_and_short_notes_reported(tmp_path):
    errs = validate_deck(make_deck(n_main=8, notes_words=50), tmp_path, check_mermaid=False)
    assert any("need 13-16" in e for e in errs) and any("notes total" in e for e in errs)


def test_too_many_main_slides_reported(tmp_path):
    errs = validate_deck(make_deck(n_main=18), tmp_path, check_mermaid=False)
    assert any("need 13-16" in e for e in errs)


def test_last_main_slide_must_be_workflow(tmp_path):
    errs = validate_deck(make_deck(last_layout="claim-diagram"), tmp_path, check_mermaid=False)
    assert any("workflow" in e for e in errs)


def test_disallowed_layout_and_missing_notes(tmp_path):
    md = make_deck().replace("layout: claim-diagram", "layout: cover", 1)
    md = md.replace("<!--\nbackup\n-->", "")
    errs = validate_deck(md, tmp_path, check_mermaid=False)
    assert any("'cover' is not allowed" in e for e in errs)
    assert any("missing speaker notes" in e for e in errs)


def test_missing_image_reported(tmp_path):
    md = make_deck().replace(VISUAL, '<img src="/figures/nope.svg" />', 1)
    errs = validate_deck(md, tmp_path, check_mermaid=False)
    assert any("nope.svg" in e for e in errs)


def test_helpers():
    s = parse_slides(make_deck())[0]
    assert words(notes_of(s)) == 170
    assert fill('{"a": {x}}', x="1") == '{"a": 1}'


def test_normalize_minutes_hits_target_and_respects_cap():
    from papertrail.common.schemas import Plan, PlanSlide, normalize_minutes

    def slides(ms):
        return Plan(story_arc="x", backup_slides=[], slides=[PlanSlide(id=str(i), title="t", purpose="p", key_points=[], minutes=m) for i, m in enumerate(ms)])

    for ms in ([1.5] * 14, [0.5] * 12, [2.0, 2.0, 0.5] + [1.0] * 11):
        p = slides(ms)
        normalize_minutes(p)
        assert 19.0 <= sum(s.minutes for s in p.slides) <= 20.0 and all(s.minutes <= 2.0 for s in p.slides), ms


def test_normalize_minutes_pins_the_quiz_slide():
    from papertrail.common.schemas import Plan, PlanSlide, normalize_minutes

    sl = [PlanSlide(id=str(i), title="t", purpose="p", key_points=[], minutes=1.4, layout="claim-quiz" if i == 8 else "claim-figure") for i in range(14)]
    p = Plan(story_arc="x", backup_slides=[], slides=sl)
    normalize_minutes(p)
    assert p.slides[8].minutes == 3.0 and 19.0 <= sum(s.minutes for s in p.slides) <= 20.0
    assert all(s.minutes <= 2.0 for i, s in enumerate(p.slides) if i != 8)


def test_more_than_two_bullet_only_slides_is_an_error(tmp_path):
    md = make_deck()
    for i in (3, 4, 5, 6):
        md = md.replace(f"# Claim number {i} holds\n\n{VISUAL}", f"# Claim number {i} holds\n\n- one\n- two")
    errs = validate_deck(md, tmp_path, check_mermaid=False)
    assert any("no visual" in e and "bullets only" in e for e in errs)


def test_two_bullet_only_slides_are_allowed(tmp_path):
    md = make_deck()
    for i in (3, 4):
        md = md.replace(f"# Claim number {i} holds\n\n{VISUAL}", f"# Claim number {i} holds\n\n- one\n- two")
    assert not any("no visual" in e for e in validate_deck(md, tmp_path, check_mermaid=False))


def test_word_limit_is_70_visible_words(tmp_path):
    ok = " ".join(["word"] * 65)
    long = " ".join(["word"] * 80)
    base = make_deck()
    assert not any("visible words" in e for e in validate_deck(base.replace("# Claim number 7 holds", f"# Claim number 7 holds\n\n{ok}"), tmp_path, check_mermaid=False))
    errs = validate_deck(base.replace("# Claim number 7 holds", f"# Claim number 7 holds\n\n{long}"), tmp_path, check_mermaid=False)
    assert any("slide 7" in e and "visible words" in e for e in errs)


def test_exactly_three_backup_slides(tmp_path):
    errs = validate_deck(make_deck(n_backup=5), tmp_path, check_mermaid=False)
    assert any("need exactly 3" in e for e in errs)


def test_exactly_one_quiz_slide_with_six_questions(tmp_path):
    errs = validate_deck(make_deck(quiz=False), tmp_path, check_mermaid=False)
    assert any("exactly one quiz slide" in e for e in errs)
    two = make_deck().replace("layout: claim-diagram\n---\n\n# Claim number 3 holds\n\n" + VISUAL,
                              "layout: claim-quiz\n---\n\n# Another quiz\n\n" + QUIZ_BODY)
    assert any("exactly one quiz slide" in e for e in validate_deck(two, tmp_path, check_mermaid=False))
    few = make_deck().replace('<div class="qa-q"><span class="qa-n">6</span><span>Question 6?</span></div>\n', "")
    assert any("questions; need 6" in e for e in validate_deck(few, tmp_path, check_mermaid=False))


def test_quiz_and_workflow_slides_have_their_own_word_limits(tmp_path):
    assert word_limit("claim-quiz") == 300 and word_limit("workflow") == 90 and word_limit("claim-figure") == 70
    assert not any("visible words" in e for e in validate_deck(make_deck(), tmp_path, check_mermaid=False))


def test_latest_sheets_ignores_annotated_screenshots(tmp_path):
    from PIL import Image

    from papertrail.common.ctx import RunCtx
    from papertrail.common.llm import Harness
    from papertrail.judges.score import latest_sheets

    run = tmp_path / "run"
    rd = run / "render" / "round_2"
    rd.mkdir(parents=True)
    for n in (1, 2, 10):
        Image.new("RGB", (1280, 720), (250, 250, 247)).save(rd / f"slide-{n}.png")
        Image.new("RGB", (1280, 720), (250, 0, 0)).save(rd / f"slide-{n}.annotated.png")
    ctx = RunCtx(run_dir=run, paper="", config="full", h=Harness(run, model_factory=lambda s: None))
    sheets = latest_sheets(ctx)
    assert len(sheets) == 1 and sheets[0][:4] == b"\x89PNG"


def test_judge_faithfulness_quote_normalisation():
    from papertrail.judges import score as sc

    paper = "The drop is 39 percent across six tasks."
    assert sc._norm("The drop is 39 percent") in sc._norm(paper)
    assert sc._norm("a made up sentence") not in sc._norm(paper)


def test_table_pipes_are_not_counted_as_visible_words():
    from papertrail.common.deckcheck import visible_words
    from papertrail.qa.source_map import parse_slides

    md = "---\nlayout: claim-table\n---\n\n# Title\n\n| a | b |\n|---|---|\n| c | d |\n\n<!--\nnotes\n-->\n"
    s = parse_slides(md)[0]
    table = "| a | b |\n|---|---|\n| c | d |"
    plain = md.replace(table, "a b\nc d")      # the same words without any table syntax
    assert visible_words(s) == visible_words(parse_slides(plain)[0])
