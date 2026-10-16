import pytest

from papertrail import pipeline


def test_full_stage_order_matches_spec():
    names = [s[0] for s in pipeline.STAGES]
    assert names == ["ingest", "digest", "difficulty", "prior_work", "plan", "analyze", "quiz", "style", "author",
                     "render_loop", "factcheck", "judge", "style_compare", "export"]


def test_only_selects_one_stage():
    assert [s[0] for s in pipeline.select_stages("full", None, "plan")] == ["plan"]


def test_from_stage_skips_earlier():
    names = [s[0] for s in pipeline.select_stages("full", 4, None)]
    assert names[0] == "plan" and "ingest" not in names


def test_unknown_stage_rejected():
    with pytest.raises(SystemExit):
        pipeline.select_stages("full", None, "nope")
    with pytest.raises(SystemExit):
        pipeline.select_stages("oneshot", None, "plan")  # not part of oneshot


def test_every_stage_module_has_run():
    import importlib

    for _, mod, _ in pipeline.STAGES + pipeline.ONESHOT_STAGES:
        assert callable(importlib.import_module(mod).run)
