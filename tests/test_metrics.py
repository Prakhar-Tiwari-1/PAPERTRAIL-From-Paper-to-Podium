from compare.metrics import macro_prf, prf
from compare import slideaudit_data as sa


def test_prf_basic_and_zero_division():
    assert prf(2, 2, 0) == (0.5, 1.0, 2 * 0.5 * 1.0 / 1.5)
    assert prf(0, 0, 0) == (0.0, 0.0, 0.0)


def test_macro_prf_toy():
    truth = [{"A"}, {"A", "B"}, set()]
    pred = [{"A"}, {"B"}, {"A"}]
    m = macro_prf(truth, pred, ["A", "B"])
    a, b = m["per_category"]["A"], m["per_category"]["B"]
    assert (a["tp"], a["fp"], a["fn"]) == (1, 1, 1)
    assert (b["tp"], b["fp"], b["fn"]) == (1, 0, 0)
    assert abs(m["macro_f1"] - (0.5 + 1.0) / 2) < 1e-9


def test_alias_mapping_and_19_categories():
    assert len(sa.CANON) == 19
    assert sa.canon_name("Object Alignment Issues") == "Content Alignment Issues"
    assert sa.canon_name("Unbalanced Space Distribution or Gapping") == "Unbalanced Space Distribution"
    assert sa.canon_name("slop_pattern") is None


def test_stratified_sample_is_balanced_and_deterministic():
    labels = {i: ["x"] * (i % 6) for i in range(1, 601)}
    s1, s2 = sa.stratified_sample(labels, 50), sa.stratified_sample(labels, 50)
    assert s1 == s2 and len(s1) == 50
    bins = [sum(1 for i in s1 if lo <= len(labels[i]) <= hi) for lo, hi in ((0, 1), (2, 3), (4, 99))]
    assert all(16 <= b <= 17 for b in bins)
