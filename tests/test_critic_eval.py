import json
from pathlib import Path

import pytest
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from compare import critic_eval, slideaudit_data as sa
from common.budget import Budget
from common.llm import Harness


@pytest.mark.skipif(not sa.SAMPLE.exists() or not (sa.DATA / "images").exists(), reason="run `python -m compare.critic_eval --prepare` first")
def test_grid_runs_offline_with_a_fake_critic(tmp_path, monkeypatch):
    def factory(slug):
        def fn(messages, info):
            props = set(info.output_tools[0].parameters_json_schema["properties"])
            if props == {"mapped"}:
                return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"mapped": ["Cluttered Layout"]})])
            issue = {"slide": 1, "category": "Cluttered Layout", "element_ids": [1], "issue": "x", "problem_description": "y",
                     "fix_steps": ["z"], "expected_improvement": "w", "severity": "low"}
            return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {"issues": [issue]})])
        return FunctionModel(fn)

    def make(run_dir):
        return Harness(run_dir, cache_dir=tmp_path / "c", model_factory=factory,
                       budget=Budget(run_dir, {"per_run_usd": 5, "total_usd": 10}, ledger=tmp_path / "ledger.jsonl"))

    monkeypatch.setattr(critic_eval, "Harness", make)
    monkeypatch.setattr(critic_eval, "ROOT", tmp_path)
    (tmp_path / "compare").mkdir()
    out = critic_eval.run_grid(n=4)
    assert set(out["grid"]) == {f"{m} | {p}" for m in critic_eval.MODELS for p in critic_eval.PROMPTS}
    assert 0 <= out["best"]["macro_f1"] <= 1 and out["paper_best"]["macro_f1"] == 0.655
    assert (tmp_path / "compare" / "critic_results.md").exists()
