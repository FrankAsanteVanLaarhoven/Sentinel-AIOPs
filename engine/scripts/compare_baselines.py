"""Apples-to-apples baseline comparison on RCAEval RE1: Sentinel vs BARO and ε-Diagnosis.

Runs each baseline (from the RCAEval repo) over the *same* RE1 cases, under the
*same* candidate set and the *same* service-level AC@k as Sentinel, so the only
thing that differs is the ranking algorithm.

Setup (the baselines' real code is not on PyPI as a usable wheel — clone the repo):
    git clone --depth 1 https://github.com/phamquiluan/RCAEval /path/to/RCAEval
    RCAEVAL_SRC=/path/to/RCAEval make compare-baselines   # or run this script

BARO needs only numpy/pandas/scikit-learn (already required). ε-Diagnosis is
OPTIONAL and uses Salesforce PyRCA — install it *without* its over-pinned deps
(it works with modern sklearn): `pip install --no-deps sfr-pyrca dill`. If PyRCA
is absent the script runs BARO alone.

BARO is invoked in RCAEval's **documented** config (`dk_select_useful=False`,
the setting `main.py` uses; `dk_select_useful=True` is tuned to RCAEval's internal
column format and drops all columns here, so it is not applicable). Windowing the
series to the official 20-min window changes nothing (verified). These are BARO
numbers **reproduced in our harness**, not BARO's (unavailable) published RE1 table.

Outputs (git-ignored): artifacts/baseline_comparison.json
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from sentinel.rca_rcaeval import SYSTEM_DEPS, FAULTS  # noqa: E402

ART = Path(__file__).resolve().parents[1] / "artifacts"
TIER = os.environ.get("TIER", "RE1").upper()  # RE1 (metrics-only) or RE2 (multi-source; metric channel only)
SYS = {c: (f"{TIER}-{c}", ds) for c, ds in
       (("OB", "online-boutique"), ("SS", "sock-shop"), ("TT", "train-ticket"))}
FAULTSET = FAULTS + (("socket",) if TIER == "RE2" else ())
# Sentinel's measured numbers (best signal per system, by AC@1): (AC@1, AC@3, Avg@5).
# RE2 = metrics-only reach on the multi-source tier (framing A); BARO is likewise metric-only here.
SENTINEL_BY_TIER = {
    "RE1": {"OB": (0.808, 0.936, 0.910), "SS": (0.872, 0.960, 0.947), "TT": (0.864, 0.960, 0.942)},
    "RE2": {"OB": (0.911, 0.978, 0.960), "SS": (0.878, 0.933, 0.916), "TT": (0.656, 0.767, 0.744)},
}
SENTINEL = SENTINEL_BY_TIER[TIER]


def _load_baro():
    src = os.environ.get("RCAEVAL_SRC")
    if not src or not os.path.isfile(os.path.join(src, "RCAEval/e2e/baro.py")):
        sys.exit("set RCAEVAL_SRC to a cloned RCAEval repo (git clone https://github.com/phamquiluan/RCAEval)")
    sys.path.insert(0, src)  # so baro.py's `from RCAEval.io.time_series import ...` resolves
    spec = importlib.util.spec_from_file_location("baro_mod", os.path.join(src, "RCAEval/e2e/baro.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # bypasses e2e/__init__ (which needs causallearn)
    return mod.baro


def _load_ediag(src):
    """ε-Diagnosis via Salesforce PyRCA, replicating RCAEval's e_diagnosis wrapper.
    Optional: install with `pip install --no-deps sfr-pyrca dill`. Returns None if
    unavailable so the script still runs BARO alone."""
    try:
        from pyrca.analyzers.epsilon_diagnosis import EpsilonDiagnosis
        sys.path.insert(0, src)
        from RCAEval.io.time_series import preprocess
    except Exception:
        return None

    def ediag(data, inject_time, dataset, alpha=0.01):
        m = EpsilonDiagnosis(config=EpsilonDiagnosis.config_class(alpha=alpha))
        nd = preprocess(data[data["time"] < inject_time], dataset=dataset, dk_select_useful=False)
        ad = preprocess(data[data["time"] >= inject_time], dataset=dataset, dk_select_useful=False)
        cols = [c for c in nd.columns if c in ad.columns]
        nd, ad = nd[cols], ad[cols]
        L = min(len(nd), len(ad))
        m.train(nd.tail(L))
        res = m.find_root_causes(ad.head(L)).to_dict()["root_cause_nodes"]
        return {"ranks": [x[0] for x in sorted(res, key=lambda x: x[1], reverse=True)]}
    return ediag


def _dedup(seq):
    out = []
    for x in seq:
        if x not in out:
            out.append(x)
    return out


def score_method(run, code: str):
    """`run(df, inject_time, dataset) -> ranked column names`. Maps columns to
    services, restricts to the same candidate set as Sentinel, dedups, scores AC@k."""
    arch, ds = SYS[code]
    root = ART / "rcaeval" / arch / arch
    deps = SYSTEM_DEPS[code]
    hits = {k: 0 for k in range(1, 6)}
    n = 0
    for case in sorted(os.listdir(root)):
        cdir = root / case
        if "_" not in case or not cdir.is_dir():
            continue
        truth, fault = case.rsplit("_", 1)
        if fault not in FAULTSET:
            continue
        for inst in sorted(os.listdir(cdir)):
            csv, itf = cdir / inst / "data.csv", cdir / inst / "inject_time.txt"
            if not csv.is_file():
                csv = cdir / inst / "simple_metrics.csv"  # RE2/RE3 metrics file
            if not (csv.is_file() and itf.is_file()):
                continue
            it = int(itf.read_text().strip())
            try:
                cols = run(pd.read_csv(csv), it, ds)
            except Exception:
                cols = []
            ranks = [s for s in _dedup([c.rsplit("_", 1)[0] for c in cols]) if s in deps]
            n += 1
            for k in range(1, 6):
                if truth in ranks[:k]:
                    hits[k] += 1
    ac = {k: hits[k] / n for k in hits}
    return {"n": n, "ac_1": round(ac[1], 3), "ac_3": round(ac[3], 3),
            "avg_5": round(sum(ac[k] for k in range(1, 6)) / 5, 3)}


def main() -> int:
    src = os.environ.get("RCAEVAL_SRC", "")
    baro = _load_baro()
    ediag = _load_ediag(src)
    baro_run = lambda df, it, ds: baro(df, inject_time=it, dataset=ds, dk_select_useful=False)["ranks"]
    print(f"RCAEval {TIER} baseline comparison — Sentinel (causal_root) vs baselines (reproduced, dk=False)")
    if TIER == "RE2":
        print("Framing A: metric channel only (simple_metrics.csv) for BOTH — not multi-source BARO.")
    print(f"ε-Diagnosis: {'available' if ediag else 'SKIPPED (pip install --no-deps sfr-pyrca dill)'}\n")
    print(f"{'sys':4}{'BARO AC@1':>10}{'ε-Diag AC@1':>12}{'Sentinel AC@1':>15}")
    card = {"benchmark": f"RCAEval {TIER}",
            "note": ("Baselines reproduced in our harness — same cases, same candidate set, same service-level "
                     "AC@k, RCAEval's documented config (dk_select_useful=False). Not the baselines' published "
                     "tables. On RE2 both sides use ONLY the metric channel (framing A) — not multi-source BARO."),
            "systems": {}}
    for code in ("OB", "SS", "TT"):
        s1, s3, s5 = SENTINEL[code]
        row = {"baro": score_method(baro_run, code), "sentinel": {"ac_1": s1, "ac_3": s3, "avg_5": s5}}
        if ediag:
            row["e_diagnosis"] = score_method(lambda df, it, ds: ediag(df, it, ds)["ranks"], code)
        card["systems"][code] = row
        e1 = row.get("e_diagnosis", {}).get("ac_1")
        print(f"{code:4}{row['baro']['ac_1']:>10.3f}{(f'{e1:.3f}' if e1 is not None else '—'):>12}{s1:>15.3f}")
    ART.mkdir(exist_ok=True)
    (ART / "baseline_comparison.json").write_text(json.dumps(card, indent=2))
    print("\ncard -> artifacts/baseline_comparison.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
