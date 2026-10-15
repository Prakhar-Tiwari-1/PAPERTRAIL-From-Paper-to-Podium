"""The pipeline must not depend on any particular paper: everything paper-specific lives in an optional profile."""
import json
import re
from pathlib import Path

import pytest

from common import profile as profile_mod
from common.profile import DatasetSpec, Profile, cite_short, citation_line, load_profile
from common.schemas import Plan, PlanSlide, validate_plan

ROOT = Path(__file__).resolve().parent.parent
GENERIC_SOURCES = ["stages/difficulty.py", "stages/plan.py", "stages/quiz.py", "stages/digest.py", "stages/analyze.py", "stages/author.py",
                   "stages/revise.py", "common/schemas.py", "judges/checklist_gen.py", "config/rubric.yaml", "tools/dataset.py"]
PAPER_WORDS = re.compile(r"sharded|shard\b|aptitude|unreliab|lost_in_conv|RECAP|SNOWBALL|2505\.06120|Laban|ICLR|GSM8K", re.I)


def test_no_code_or_prompt_mentions_the_test_paper():
    hits = {f: PAPER_WORDS.findall((ROOT / f).read_text(encoding="utf-8")) for f in GENERIC_SOURCES}
    assert {f: h for f, h in hits.items() if h} == {}


def test_default_profile_is_empty_and_valid_for_an_unknown_paper():
    p = load_profile("9999.99999")
    assert p.candidate_concepts == [] and p.known_critiques == [] and p.dataset is None and p.extra_required_slides == []


def test_this_papers_profile_carries_what_used_to_be_hard_coded():
    p = load_profile("2505.06120")
    assert p.dataset and p.dataset.id_field == "task_id" and any("dated" in c for c in p.known_critiques)
    assert p.cite_short == "Laban et al., 2025" and p.candidate_concepts


def test_explicit_profile_file_wins(tmp_path):
    f = tmp_path / "mine.yaml"
    f.write_text("quiz_hints: [the learning rate]\ncite_short: Doe et al., 2030\n", encoding="utf-8")
    p = load_profile("9999.99999", f)
    assert p.quiz_hints == ["the learning rate"] and p.cite_short == "Doe et al., 2030"


# ------------------------------------------------------------------ generic plan rules
def plan(titles, layouts=None):
    sl = [PlanSlide(id=str(i), title=t, purpose=t, key_points=[], minutes=1.4, layout=(layouts or {}).get(i, "claim-figure")) for i, t in enumerate(titles)]
    sl[0].layout = "title"
    sl[-1].layout, sl[-1].title, sl[-1].purpose = "workflow", "Tools & Workflow", "tools and workflow"
    return Plan(story_arc="a", slides=sl, backup_slides=[{"id": str(i), "title": "b", "purpose": "p"} for i in range(3)])


TITLES = ["Title", "The problem: models forget instructions", "Our method adds a memory module", "Experiment design and baselines", "The key result: higher accuracy",
          "How it compares to earlier work", "An ablation removes the memory", "Our analysis re-plots the main table", "Limitations and caveats of the study",
          "A second result on a harder task", "Why it works", "Check your understanding", "The takeaway for practitioners", "Tools & Workflow"]


def test_generic_plan_passes_without_any_paper_specific_slide():
    p = plan(TITLES, {11: "claim-quiz"})
    assert validate_plan(p, []) == []


def test_extra_required_slides_come_from_the_profile():
    p = plan(TITLES, {11: "claim-quiz"})
    errs = validate_plan(p, [], [{"name": "scaling law", "keywords": ["scaling law", "power law"]}])
    assert any("missing required slide: scaling law" in e for e in errs)
    p.slides[9].title = "A scaling law fits the loss"
    assert validate_plan(p, [], [{"name": "scaling law", "keywords": ["scaling law"]}]) == []


def test_generic_plan_still_requires_the_basics():
    errs = validate_plan(plan([t for t in TITLES if "result" not in t.lower()] + ["Another"], {10: "claim-quiz"}), [])
    assert any("headline result" in e for e in errs)


# ------------------------------------------------------------------ dataset is optional and generic
RECORDS = [{"id": "a1", "kind": "math", "question": "What is 2+2?", "parts": [{"s": "add"}, {"s": "two and two"}]},
           {"id": "b2", "kind": "code", "question": "Reverse a list", "parts": [{"s": "use slicing"}]}]


def synthetic():
    from tools.dataset import Dataset

    spec = DatasetSpec(name="toy", id_field="id", task_field="kind", text_fields=["question"], shards_field="parts", shard_text_field="s", example_tasks=["math"])
    return Dataset(spec, records=RECORDS)


def test_dataset_class_is_generic():
    ds = synthetic()
    assert ds.ids() == {"a1", "b2"} and ds.tasks() == ["code", "math"]
    assert ds.lookup("math", 3)[0]["parts"][1]["text"] == "two and two"
    assert "What is 2+2? add two and two" == ds.full_text("a1")
    assert ds.full_text("zzz") == ""


def test_no_dataset_means_no_tool_and_worked_examples_must_cite_the_paper():
    from stages import difficulty
    from common.schemas import AudienceModel, DifficultyMap, HardConcept
    from tools import dataset as dataset_tool

    assert dataset_tool.active() is None and dataset_tool.tool() is None
    mk = lambda mat: DifficultyMap(concepts=[HardConcept(concept=f"c{i}", why_hard="jargon", misconception_to_avoid="x", device="worked_example",
                                                         device_material=mat, anchor="p.3") for i in range(5)],
                                   audience_model=AudienceModel(already_knows=[], must_be_taught=[]))
    assert any("printed in the paper" in e for e in difficulty.validate(mk("an invented example"), None))
    assert difficulty.validate(mk("the example in Table 2 on p.7"), None) == []
    assert any("real record id" in e for e in difficulty.validate(mk("record zz9"), {"a1"}))
    assert difficulty.validate(mk("record a1 shown turn by turn"), {"a1"}) == []


def test_dataset_citation_without_a_dataset_is_an_error(tmp_path):
    from common.deckcheck import validate_deck
    from common.schemas import DeckClaim

    md = "---\ntheme: ./theme\nlayout: title\n---\n\n# T\n\n<!--\nn\n-->\n"
    errs = validate_deck(md, tmp_path, check_mermaid=False, check_notes_total=False, require_quiz=False,
                         claims=[DeckClaim(slide=1, text="x", kind="claim", source="dataset:a1")])
    assert any("this paper has none" in e for e in errs)


# ------------------------------------------------------------------ citations from the arXiv metadata
ATOM = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom"><entry>
<title>A  Great
 Paper</title><published>2024-03-05T10:00:00Z</published><author><name>Ada Lovelace</name></author><author><name>Alan Turing</name></author>
<author><name>Grace Hopper</name></author><arxiv:comment>Accepted at ICML 2024, 12 pages</arxiv:comment></entry></feed>"""


def test_arxiv_metadata_is_parsed():
    from tools import arxiv_meta

    m = arxiv_meta.parse(ATOM)
    assert m["authors"][0] == "Ada Lovelace" and m["year"] == 2024 and m["venue"] == "ICML 2024" and m["title"] == "A Great Paper"
    assert arxiv_meta.parse("<feed xmlns='http://www.w3.org/2005/Atom'></feed>") == {}


def run_with_meta(tmp_path, **kw):
    d = {"paper_id": "2401.00001", "source": "arxiv-latex", "authors": ["Ada Lovelace", "Alan Turing", "Grace Hopper"], "year": 2024, "venue": "ICML 2024"}
    d.update(kw)
    (tmp_path / "ingested.json").write_text(json.dumps(d), encoding="utf-8")
    return tmp_path


def test_citations_are_built_from_metadata_for_any_paper(tmp_path):
    run = run_with_meta(tmp_path)
    assert cite_short(run) == "Lovelace et al., 2024"
    assert citation_line(run, "auto") == "Lovelace, Turing and Hopper  ·  ICML 2024  ·  arXiv:2401.00001"
    assert citation_line(run, "My own line") == "My own line"          # the owner's text in footer.json wins over auto
    run2 = run_with_meta(tmp_path, authors=["Ada Lovelace"], venue="")
    assert cite_short(run2) == "Lovelace, 2024"


def test_profile_overrides_the_citations(tmp_path):
    run = run_with_meta(tmp_path)
    profile_mod.set_current(Profile(paper_citation="Custom line", cite_short="Custom, 2030"))
    assert cite_short(run) == "Custom, 2030" and citation_line(run, "auto") == "Custom line"


def test_a_pdf_without_metadata_still_gets_safe_defaults(tmp_path):
    run = run_with_meta(tmp_path, authors=[], year=None, venue="", paper_id="my-paper", source="pdf")
    assert cite_short(run) == "the paper" and citation_line(run, "auto") == ""


def test_footer_sync_resolves_auto_citation(tmp_path):
    from tools import footer

    (tmp_path / "run").mkdir()
    run = run_with_meta(tmp_path / "run")
    deck = tmp_path / "deck"
    footer.sync(deck, run_dir=run)
    cfg = json.loads((deck / "theme" / "footer.json").read_text(encoding="utf-8"))
    assert cfg["paper_citation"].startswith("Lovelace, Turing and Hopper")
    assert cfg["course_code"] == "CSC_53432_EP"                       # the owner's course details are untouched
