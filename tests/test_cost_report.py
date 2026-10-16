from papertrail.tools.cost_report import report


def test_report_totals_by_run_model_and_role():
    entries = [
        {"run": "r1", "usd": 1.0, "model": "a/x", "role": "author"},
        {"run": "r1", "usd": 0.5, "model": "b/y", "role": "judge"},
        {"run": "r2", "usd": 0.25, "model": "a/x", "role": "author"},
    ]
    md = report(entries, {"per_run_usd": 5, "total_usd": 8})
    assert "**Total spent: $1.75** over 3 calls" in md
    assert "| `r1` |  | 2 | 1.50 |" in md and "| `r2` |  | 1 | 0.25 |" in md
    assert "| `a/x` | 1.25 |" in md and "| author | 1.000 |" in md
    assert "$5.00 per run, $8.00 in total" in md
