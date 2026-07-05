"""Hermetic tests for the PetShop localization-validation harness.

No download — a tiny synthetic fixture exercises graph parsing, the elevated
signal, and the ranking so the suite stays offline. The real corpus evaluation
lives in scripts/validate_localization.py.
"""
import numpy as np
import pandas as pd

from sentinel.incident_agent import causal_root
from sentinel.rca_petshop import (
    deps_from_graph,
    elevated_services,
    rank_candidates,
    within_domain_elevated,
)

# A -> B -> C, and A -> D. The fault is injected at C and propagates up to B, A.
GRAPH = ",A,B,C,D\nA,0,1,0,1\nB,0,0,1,0\nC,0,0,0,0\nD,0,0,0,0\n"


def _frame(values: dict[str, float], rows: int = 8) -> pd.DataFrame:
    cols = pd.MultiIndex.from_tuples([(n, "latency", "Average") for n in values])
    data = np.column_stack([np.full(rows, v, dtype=float) for v in values.values()])
    return pd.DataFrame(data, columns=cols)


def test_deps_from_graph(tmp_path):
    p = tmp_path / "graph.csv"
    p.write_text(GRAPH)
    deps = deps_from_graph(str(p))
    assert deps["A"] == ["B", "D"]
    assert deps["B"] == ["C"]
    assert deps["C"] == [] and deps["D"] == []


def test_elevated_and_rank_locate_the_true_root():
    normal = _frame({"A": 100, "B": 100, "C": 100, "D": 100})
    abnormal = _frame({"A": 480, "B": 450, "C": 500, "D": 100})  # C source; A,B inherit; D healthy
    deps = {"A": ["B", "D"], "B": ["C"], "C": [], "D": []}

    elevated = elevated_services(normal, abnormal, "latency", "Average", z_thr=3.0)
    assert set(elevated) == {"A", "B", "C"}  # D not elevated

    ranked = rank_candidates(elevated, deps)
    # C is the only elevated service with no elevated dependency -> ranked first,
    # and this must equal the engine's own single pick.
    assert ranked[0] == "C"
    assert ranked[0] == causal_root(elevated, deps)
    assert "C" in ranked[:3]


def _multi(vals: dict, rows: int = 8) -> pd.DataFrame:
    cols = pd.MultiIndex.from_tuples([(n, m, "Average") for (n, m) in vals])
    data = np.column_stack([np.full(rows, v, dtype=float) for v in vals.values()])
    return pd.DataFrame(data, columns=cols)


def test_within_domain_catches_non_target_metric():
    # A's availability drops (a two-sided anomaly in a NON-latency metric);
    # the within-domain signal must flag A while B stays healthy.
    normal = _multi({("A", "latency"): 100, ("A", "availability"): 99,
                     ("B", "latency"): 100, ("B", "availability"): 99})
    abnormal = _multi({("A", "latency"): 100, ("A", "availability"): 50,
                       ("B", "latency"): 100, ("B", "availability"): 99})
    el = within_domain_elevated(normal, abnormal, z_thr=3.0)
    assert "A" in el and "B" not in el
    # the single target-metric (latency) test would miss it — nothing moved on latency
    assert elevated_services(normal, abnormal, "latency", "Average", z_thr=3.0) == {}


def test_within_domain_selective_requires_multivariate_evidence():
    # A moves on ONE metric; B moves on TWO. Broad (>=1) flags both;
    # selective (>=2) requires multivariate evidence, so it drops A and keeps B.
    normal = _multi({("A", "latency"): 100, ("A", "availability"): 99,
                     ("B", "latency"): 100, ("B", "availability"): 99})
    abnormal = _multi({("A", "latency"): 100, ("A", "availability"): 50,   # 1 metric
                       ("B", "latency"): 200, ("B", "availability"): 50})   # 2 metrics
    broad = within_domain_elevated(normal, abnormal, z_thr=3.0, min_metrics=1)
    selective = within_domain_elevated(normal, abnormal, z_thr=3.0, min_metrics=2)
    assert "A" in broad and "B" in broad
    assert "A" not in selective and "B" in selective


def test_robust_elevation_recovers_shift_masked_by_baseline_spikes():
    # A's baseline carries a couple of spikes that inflate mean/std, so a modest but genuine
    # upward shift is buried (z < 3) under the standard statistic. Median/IQR is unaffected by
    # the spikes and recovers the shift — the mechanism behind the RE3 robust-elevation change.
    cols = pd.MultiIndex.from_tuples([("A", "latency", "Average"), ("B", "latency", "Average")])
    base = pd.DataFrame(np.column_stack([
        np.array([100, 100, 100, 100, 100, 100, 100, 400], float),  # A: spiky baseline
        np.full(8, 100.0),                                          # B: flat
    ]), columns=cols)
    abn = pd.DataFrame(np.column_stack([
        np.full(8, 160.0),   # A: modest, real upward shift
        np.full(8, 100.0),   # B: unchanged
    ]), columns=cols)

    std = within_domain_elevated(base, abn, z_thr=3.0)                # mean/std (default)
    rob = within_domain_elevated(base, abn, z_thr=3.0, robust=True)   # median/IQR
    assert "A" not in std                       # the inflated std masks the shift
    assert "A" in rob and "B" not in rob        # robust recovers A; B stays quiet


def test_no_anomaly_yields_no_candidates():
    normal = _frame({"A": 100, "B": 100})
    abnormal = _frame({"A": 101, "B": 100})  # within noise -> nothing elevated
    elevated = elevated_services(normal, abnormal, "latency", "Average", z_thr=3.0)
    assert elevated == {}
    assert rank_candidates(elevated, {"A": [], "B": []}) == []
