"""Hermetic tests for the RCAEval adapter (no network, no dataset)."""
import os

import numpy as np
import pandas as pd

from sentinel.rca_rcaeval import SYSTEM_DEPS, evaluate_system, load_case


def _write_case(cdir: str, inject: int, spike: set, n: int = 12):
    os.makedirs(cdir, exist_ok=True)
    t = list(range(1000, 1000 + n))
    data = {"time": t}
    for c in ("svcA_cpu", "svcA_mem", "svcB_cpu", "svcB_mem"):
        vals = np.full(n, 10.0)
        if c in spike:
            vals = np.array([100.0 if ti >= inject else 10.0 for ti in t])
        data[c] = vals
    pd.DataFrame(data).to_csv(os.path.join(cdir, "data.csv"), index=False)
    with open(os.path.join(cdir, "inject_time.txt"), "w") as f:
        f.write(str(inject))


def test_load_case_splits_on_inject_time(tmp_path):
    cdir = tmp_path / "svcA_cpu" / "1"
    _write_case(str(cdir), inject=1006, spike={"svcA_cpu", "svcA_mem"})
    normal, abnormal = load_case(str(cdir / "data.csv"), 1006)
    assert len(normal) == 6 and len(abnormal) == 6
    assert ("svcA", "cpu", "value") in normal.columns
    assert "time" not in {c[0] for c in normal.columns}


def test_evaluate_localizes_root_over_symptom(tmp_path):
    # svcA is the injected root; svcB is a downstream symptom (both spike).
    # The causal rule must pick svcA (svcB has an elevated dependency).
    sysdir = tmp_path / "sys"
    _write_case(str(sysdir / "svcA_cpu" / "1"), inject=1006,
                spike={"svcA_cpu", "svcA_mem", "svcB_cpu", "svcB_mem"})
    SYSTEM_DEPS["TEST"] = {"svcA": [], "svcB": ["svcA"]}
    try:
        e = evaluate_system(str(sysdir), system="TEST", signal="within_domain_selective")
        assert e.n == 1 and e.top1 == 1 and e.top3 == 1
    finally:
        SYSTEM_DEPS.pop("TEST", None)
