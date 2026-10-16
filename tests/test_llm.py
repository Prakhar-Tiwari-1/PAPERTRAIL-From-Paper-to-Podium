import json

import pytest
from pydantic import BaseModel
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.test import TestModel

from papertrail.common.budget import Budget, BudgetExceeded
from papertrail.common.llm import Harness, MissingAPIKey, check_vendor_rules, load_models


class Out(BaseModel):
    x: int


def make(tmp_path, factory, caps=None, dev=False):
    run = tmp_path / "runs" / "r1"
    run.mkdir(parents=True)
    budget = Budget(run, caps or {"per_run_usd": 2.0, "total_usd": 10.0}, ledger=tmp_path / "runs" / "_spend.jsonl")
    return Harness(run, dev=dev, budget=budget, cache_dir=tmp_path / "cache", model_factory=factory)


def test_call_is_traced_and_costed(tmp_path):
    h = make(tmp_path, lambda slug: TestModel(custom_output_args={"x": 3}))
    out = h.call("digest", "hello", output_type=Out)
    assert out.x == 3
    events = h.trace.read()
    assert events[-1]["role"] == "digest" and events[-1]["cached"] is False
    assert (h.run_dir / "cost.json").exists()
    assert json.loads((h.run_dir / "cost.json").read_text())["calls"] == 1


def test_cache_key_includes_repeat_idx(tmp_path):
    calls = []

    def factory(slug):
        def fn(messages, info: AgentInfo):
            calls.append(1)
            return ModelResponse(parts=[TextPart('{"x": 1}')])

        return FunctionModel(fn)

    h = make(tmp_path, factory)
    h.cfg_prompted = True
    h.roles["judge"].prompted = True
    h.call("judge", "same prompt", output_type=Out, repeat_idx=0)
    h.call("judge", "same prompt", output_type=Out, repeat_idx=0)  # served from cache
    assert len(calls) == 1
    h.call("judge", "same prompt", output_type=Out, repeat_idx=1)  # distinct repeat: real call
    assert len(calls) == 2
    k0 = h.cache_key("m", "s", "p", [], {}, 0, "Out")
    k1 = h.cache_key("m", "s", "p", [], {}, 1, "Out")
    assert k0 != k1


def test_over_cap_call_refused_before_network(tmp_path):
    called = []
    h = make(tmp_path, lambda slug: called.append(slug) or TestModel(), caps={"per_run_usd": 0.0001, "total_usd": 10})
    with pytest.raises(BudgetExceeded):
        h.call("author", "x" * 1000, output_type=Out)  # sonnet worst case >> $0.0001
    assert called == []


def test_total_cap_spans_runs(tmp_path):
    h = make(tmp_path, lambda slug: TestModel(), caps={"per_run_usd": 5, "total_usd": 0.01})
    h.budget.ledger.write_text(json.dumps({"run": "old", "usd": 0.0099, "model": "m", "role": "r"}) + "\n")
    with pytest.raises(BudgetExceeded):
        h.budget.check(0.001)


def test_missing_api_key_errors_before_network(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    h = make(tmp_path, None)
    with pytest.raises(MissingAPIKey):
        h.call("digest", "hi", output_type=Out)


def test_fallback_after_three_failures(tmp_path):
    seen = []

    def factory(slug):
        seen.append(slug)

        def fn(messages, info):
            if slug == h.slug_for("digest"):
                raise RuntimeError("429 rate limited")
            return ModelResponse(parts=[TextPart('{"x": 7}')])

        return FunctionModel(fn)

    h = make(tmp_path, factory)
    h.roles["digest"].prompted = True
    out = h.call("digest", "hi", output_type=Out)
    assert out.x == 7
    primary = h.slug_for("digest")
    assert seen.count(primary) == 3 and seen[-1] == h.slug_for("digest", fallback=True)
    assert any(e.get("fallback_used") for e in h.trace.read())


def test_images_never_routed_to_deepseek(tmp_path):
    h = make(tmp_path, lambda s: TestModel())
    h.roles["vision_critic"].model = "deepseek/deepseek-v4-flash"
    with pytest.raises(ValueError):
        h.call("vision_critic", "look", output_type=Out, images=[b"png"])


def test_vendor_rules_in_shipped_config():
    roles, _ = load_models()
    import yaml
    from papertrail.common.llm import ROOT

    rules = yaml.safe_load((ROOT / "config" / "models.yaml").read_text())["vendor_rules"]
    assert check_vendor_rules(roles, rules) == []
    assert check_vendor_rules(roles, rules, dev=True) == []


def test_budget_resume_rebuilds_run_totals(tmp_path):
    run = tmp_path / "runs" / "r1"
    run.mkdir(parents=True)
    ledger = tmp_path / "runs" / "_spend.jsonl"
    b1 = Budget(run, {"per_run_usd": 2.0, "total_usd": 10.0}, ledger=ledger)
    b1.add(0.25, model="m1", role="digest")
    b2 = Budget(run, {"per_run_usd": 2.0, "total_usd": 10.0}, ledger=ledger)  # a resumed process
    b2.add(0.5, model="m2", role="author")
    cost = json.loads((run / "cost.json").read_text())
    assert cost["run_usd"] == 0.75 and cost["calls"] == 2 and set(cost["by_model"]) == {"m1", "m2"}


def test_tool_loop_estimate_scales_with_tool_cap(tmp_path):
    def tool_fn(x: str) -> str:
        "a tool"
        return x

    h = make(tmp_path, lambda slug: TestModel(), caps={"per_run_usd": 0.05, "total_usd": 10})
    # fits once (one round) but not with 4 extra tool round-trips of the same prompt: guard refuses before any call
    big = "x" * 120_000
    h.roles["difficulty"].max_tokens = 1000
    with pytest.raises(BudgetExceeded):
        h.call("difficulty", big, output_type=Out, tools=[tool_fn], max_tool_calls=4)


def test_unreachable_ollama_goes_straight_to_the_fallback(tmp_path, monkeypatch):
    seen = []

    def factory(slug):
        seen.append(slug)
        return TestModel(custom_output_args={"x": 5})

    h = make(tmp_path, factory)
    h.model_factory = factory
    h.roles["digest"].model = "ollama:qwen3:4b"  # a role that prefers the local model
    monkeypatch.setattr(Harness, "_ollama_up", lambda self: False)
    out = h.call("digest", "hi", output_type=Out)
    assert out.x == 5
    assert seen and all(not s.startswith("ollama:") for s in seen)
