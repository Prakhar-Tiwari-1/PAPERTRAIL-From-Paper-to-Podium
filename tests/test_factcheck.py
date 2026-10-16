from pathlib import Path

from papertrail.common.schemas import DeckClaim, NumberPair
from papertrail.qa.source_map import parse_slides
from papertrail.stages import factcheck as fc


def test_value_matching_exact_rounded_and_fraction():
    assert fc.value_matches("39%", "average drop of 39% across tasks")
    assert fc.value_matches("45.1", "scores 45.12 on code")          # equal after rounding to 1 decimal
    assert fc.value_matches("39%", "relative change 0.39")           # percentage vs fraction
    assert not fc.value_matches("45.9", "scores 45.12 on code")
    assert not fc.value_matches("200", "only 2 and 20 appear")


def test_extraction_ignores_structure_noise():
    md = "---\nlayout: claim-bullets\n---\n\n# Claim\n\n1. first\n- 39% drop\n<img src=\"/figures/fig3.svg\" />\n<SourceCaption>Laban et al., 2025, Fig. 3</SourceCaption>\n\n<!--\nNotes: 200,000 conversations.\n-->\n"
    vals = [i["value"] for i in fc.extract_numbers(parse_slides(md)[0])]
    assert "39%" in vals and "200,000" in vals
    assert "3" not in vals and "1" not in vals


class Ctx:  # minimal stand-in: check() only uses text/load_json/run_dir
    def __init__(self, tmp: Path):
        self.run_dir = tmp
        (tmp / "paper.md").write_text("[p.1]\nWe see a 39% drop.\n[p.2]\nOnly 200,000 simulated conversations.\n", encoding="utf-8")
        (tmp / "tables.json").write_text('[{"id": "Table 1", "caption": "x", "rows": [["A", "45.1"]]}]', encoding="utf-8")
        (tmp / "ingested.json").write_text('{"figures": []}', encoding="utf-8")

    def text(self, n): return (self.run_dir / n).read_text(encoding="utf-8")
    def load_json(self, n):
        import json
        return json.loads(self.text(n))


def test_anchor_scoped_check_does_not_match_by_accident(tmp_path):
    ctx = Ctx(tmp_path)
    claims = [DeckClaim(slide=1, text="39% drop", kind="number", source="p.1"),
              DeckClaim(slide=2, text="200,000 conversations", kind="number", source="p.1")]  # wrong page cited
    pairs = [NumberPair(slide=1, value="39%", claim="drop"), NumberPair(slide=2, value="200,000", claim="n"),
             NumberPair(slide=3, value="45.1", claim="score")]
    matched, unmatched = fc.check(ctx, pairs, claims)
    assert [p.value for p in matched] == ["39%"]
    assert {p.value for p in unmatched} == {"200,000", "45.1"}   # wrong page; and no claim cites slide 3 at all


def test_source_caption_years_are_not_checked():
    md = "---\nlayout: claim-figure\n---\n\n# Drop\n\n<SourceCaption>Laban et al., 2025, Fig. 3</SourceCaption>\n"
    assert fc.extract_numbers(parse_slides(md)[0]) == []


def test_number_words_match_digits():
    assert fc.value_matches("6", "across six tasks")
    assert not fc.value_matches("6", "across sixty tasks")
    assert not fc.value_matches("6%", "across six tasks")


def test_extractor_failure_degrades_instead_of_failing(tmp_path):
    import json
    from pydantic_ai.models.function import FunctionModel
    from papertrail.common.budget import Budget
    from papertrail.common.ctx import RunCtx
    from papertrail.common.llm import Harness

    run = tmp_path / "run"
    (run / "deck").mkdir(parents=True)
    (run / "deck" / "slides.md").write_text("---\nlayout: claim-bullets\n---\n\n# Drop\n\n- a 39% drop\n", encoding="utf-8")
    (run / "deck.json").write_text(json.dumps({"claims": [{"slide": 1, "text": "39% drop", "kind": "number", "source": "p.1"}]}), encoding="utf-8")
    (run / "paper.md").write_text("[p.1]\nA 39% drop.\n", encoding="utf-8")
    (run / "tables.json").write_text("[]", encoding="utf-8")
    (run / "ingested.json").write_text('{"figures": []}', encoding="utf-8")

    def boom(messages, info):
        raise RuntimeError("model ran away")

    h = Harness(run, model_factory=lambda s: FunctionModel(boom), cache_dir=tmp_path / "c",
                budget=Budget(run, {"per_run_usd": 5, "total_usd": 50}, ledger=tmp_path / "l.jsonl"))
    ctx = RunCtx(run_dir=run, paper="", config="full", h=h)
    res = fc.check_deck(ctx)
    assert res.n_extracted == 1 and res.n_matched == 1 and res.unmatched == []
    assert any(e.get("event") == "extractor_batch_failed" for e in h.trace.read())


def test_dataset_source_verifies_numbers_against_the_real_instance(tmp_path):
    from papertrail.common import profile as profile_mod

    profile_mod.set_current(profile_mod.load_profile("2505.06120"))   # this paper's profile names the released dataset (cached locally)
    ctx = Ctx(tmp_path)
    claims = [DeckClaim(slide=3, text="Ara plays 40 games per year", kind="number", source="dataset:sharded-GSM8K/1246"),
              DeckClaim(slide=3, text="Ara plays 41 games per year", kind="number", source="dataset:sharded-GSM8K/1246")]
    pairs = [NumberPair(slide=3, value="40", claim="games")]
    matched, unmatched = fc.check(ctx, pairs, claims[:1])
    assert [p.value for p in matched] == ["40"] and unmatched == []
    matched, unmatched = fc.check(ctx, [NumberPair(slide=3, value="41", claim="games")], claims[1:])
    assert unmatched and not matched          # a wrong number does not match the real instance


def test_quiz_question_numbers_are_labels_not_claims():
    md = ("---\nlayout: claim-quiz\n---\n\n# Check\n\n<div class=\"qa-board\">\n"
          "<div class=\"qa-q\"><span class=\"qa-n\">1</span><span>Why 39 percent?</span></div>\n</div>\n")
    vals = [i["value"] for i in fc.extract_numbers(parse_slides(md)[0])]
    assert vals == ["39"]
