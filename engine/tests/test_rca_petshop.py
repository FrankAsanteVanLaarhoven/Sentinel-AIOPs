"""Hermetic tests for the PetShop localization-validation harness.

No download — a tiny synthetic fixture exercises graph parsing, the elevated
signal, and the ranking so the suite stays offline. The real corpus evaluation
lives in scripts/validate_localization.py.
"""
import numpy as np
import pandas as pd

from sentinel.incident_agent import causal_root
from sentinel.rca_petshop import deps_from_graph, elevated_services, rank_candidates

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


def test_no_anomaly_yields_no_candidates():
    normal = _frame({"A": 100, "B": 100})
    abnormal = _frame({"A": 101, "B": 100})  # within noise -> nothing elevated
    elevated = elevated_services(normal, abnormal, "latency", "Average", z_thr=3.0)
    assert elevated == {}
    assert rank_candidates(elevated, {"A": [], "B": []}) == []
