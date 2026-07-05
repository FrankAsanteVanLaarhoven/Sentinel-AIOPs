"""A/B experiment: standard mean/std vs robust median/IQR elevation on an RCAEval tier.

The verbatim causal rule, the z>=3 gate, and min_metrics are all held fixed; the ONLY thing
that changes is the per-metric statistic used to score deviation (mean/std -> median/IQR, the
robust scorer BARO uses). So any movement in AC@1 is attributable to the statistic alone, not
to tuning. The question: does the robust statistic close the RE3 code-level-fault gap without
regressing RE1/RE2?

    TIER=RE3 python scripts/robust_elevation_experiment.py   # target tier
    TIER=RE2 python scripts/robust_elevation_experiment.py   # regression check

Reuses the multi-source harness's selective download (metrics channel only). Read-only: writes
no cards and changes no defaults (robust is opt-in, default off everywhere else).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sentinel.rca_rcaeval import evaluate_system  # noqa: E402
from validate_rcaeval_multi import SYSTEMS, TIER, TIER_FAULTS, ensure  # noqa: E402

# Reported metric-only baselines on RE3 (RCAEval, TheWebConf 2025) for context.
BARO_RE3_AC1 = 0.784


def _best(sysdir: str, code: str, faults: tuple, robust: bool):
    """Best signal (broad / selective) by AC@1 for one system — mirrors the harness."""
    best = None
    for signal in ("within_domain", "within_domain_selective"):
        ev = evaluate_system(sysdir, code, signal=signal, faults=faults, robust=robust)
        if best is None or ev.ac(1) > best[0]:
            best = (ev.ac(1), ev)
    return best[1]


def main() -> int:
    if TIER not in TIER_FAULTS:
        sys.exit(f"TIER must be RE2 or RE3 (got {TIER})")
    faults = TIER_FAULTS[TIER]
    print(f"RCAEval {TIER} · A/B: mean/std vs robust median/IQR (same z>=3 gate, same rule)\n")
    agg = {"n": 0, "b_h1": 0, "r_h1": 0, "b_a5": 0.0, "r_a5": 0.0}
    for code, archive in SYSTEMS.items():
        root = ensure(archive)
        inner = os.path.join(root, archive)
        sysdir = inner if os.path.isdir(inner) else root
        bev = _best(sysdir, code, faults, robust=False)
        rev = _best(sysdir, code, faults, robust=True)
        print(f"{code}: AC@1 {bev.ac(1):.3f} -> {rev.ac(1):.3f}   "
              f"Avg@5 {bev.avg5:.3f} -> {rev.avg5:.3f}   (n={bev.n})")
        agg["n"] += bev.n
        agg["b_h1"] += bev.hits[1]
        agg["r_h1"] += rev.hits[1]
        agg["b_a5"] += sum(bev.hits[k] for k in range(1, 6)) / 5
        agg["r_a5"] += sum(rev.hits[k] for k in range(1, 6)) / 5
    n = agg["n"]
    if n:
        print(f"\naggregate ({n} cases, best signal per system):")
        print(f"  AC@1   mean/std {agg['b_h1']/n:.3f}  ->  robust {agg['r_h1']/n:.3f}"
              + (f"   (metric-only BARO RE3 = {BARO_RE3_AC1})" if TIER == "RE3" else ""))
        print(f"  Avg@5  mean/std {agg['b_a5']/n:.3f}  ->  robust {agg['r_a5']/n:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
