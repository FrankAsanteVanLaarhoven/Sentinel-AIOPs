"""Five canonical incident scenarios for the Demo provider.

Each returns the same ``store`` shape the simulator produces (metrics / changes /
traces) plus a documented ``ground_truth_root``. The incident engine's
detect -> localize -> correlate logic is scenario-agnostic — it runs unchanged on
every store — so these exercise its behaviour across incident *shapes*:

  flag_spike          step failure on a leaf; textbook propagation   (root: productcatalog)
  gradual             slow error-budget burn; later MTTD             (root: payment)
  shared_infra        shared backend fails; wide blast radius        (root: productcatalog)
  symptom_louder      a symptom is LOUDER than the root              (root: productcatalog)
  noisy_multi_change  four changes near onset; ranking must choose   (root: payment)

All incidents begin at INC so MTTD stays comparable across scenarios.
"""
from __future__ import annotations

import numpy as np

from .telemetry_sim import simulate, SERVICES, N, INC


SCENARIO_META = [
    {"id": "flag_spike", "label": "Flag spike", "root": "productcatalog",
     "note": "Feature-flag breaks productcatalog; errors propagate to cart + frontend."},
    {"id": "gradual", "label": "Gradual burn", "root": "payment",
     "note": "payment degrades on a slow ramp — a slower, later detection."},
    {"id": "shared_infra", "label": "Shared infra", "root": "productcatalog",
     "note": "A shared backend fails; wide blast radius across dependents."},
    {"id": "symptom_louder", "label": "Symptom louder", "root": "productcatalog",
     "note": "A symptom (frontend) shows a HIGHER error rate than the true root."},
    {"id": "noisy_multi_change", "label": "Noisy changes", "root": "payment",
     "note": "Four changes near onset; correlation must pick the right one."},
]
SCENARIO_IDS = [m["id"] for m in SCENARIO_META]


def _blank(rng):
    return {
        s: {
            "error_rate": np.full(N, 0.004) + rng.normal(0, 0.001, N).clip(0),
            "latency_p95": np.full(N, 120.0) + rng.normal(0, 8, N),
            "rps": np.full(N, 200.0) + rng.normal(0, 15, N),
        }
        for s in SERVICES
    }


def _inject(T, service, err, lat, rng, ramp=0):
    """Drive a service into failure from INC. ramp>0 makes it a gradual burn."""
    for t in range(INC, N):
        frac = 1.0 if ramp == 0 else min(1.0, (t - INC + 1) / ramp)
        T[service]["error_rate"][t] = max(0.0, err * frac + rng.normal(0, 0.02))
        T[service]["latency_p95"][t] = 120 + (lat - 120) * frac + rng.normal(0, 25)
        T[service]["rps"][t] = T[service]["rps"][t]  # unchanged


def build(scenario: str = "flag_spike", seed: int = 7):
    if scenario == "flag_spike":
        # delegate to the original simulator so the engine's tests stay exact
        st = simulate(seed)
        st["ground_truth_root"] = "productcatalog"
        st["scenario"] = "flag_spike"
        return st

    rng = np.random.default_rng(seed)
    T = _blank(rng)
    changes: list = []
    traces: list = []
    gt = None

    if scenario == "gradual":
        gt = "payment"
        _inject(T, "payment", 0.19, 370, rng, ramp=10)
        _inject(T, "checkout", 0.09, 210, rng, ramp=10)  # symptom (depends on payment)
        changes = [
            {"t": 12, "service": "productcatalog", "change": "deploy v2.1.0"},
            {"t": INC - 1, "service": "payment", "change": "deploy v1.5.0 (pool -50%)"},
        ]
        traces = [{"trace_id": "b7d3e1", "root": "checkout.POST /pay",
                   "error_span": "payment.Charge", "status": "ERROR", "t": INC + 5}]

    elif scenario == "shared_infra":
        gt = "productcatalog"
        _inject(T, "productcatalog", 0.29, 520, rng)
        _inject(T, "cart", 0.15, 190, rng)       # depends on productcatalog
        _inject(T, "frontend", 0.17, 330, rng)   # depends on productcatalog + cart
        _inject(T, "checkout", 0.08, 175, rng)   # depends on cart (indirect)
        changes = [
            {"t": 20, "service": "frontend", "change": "deploy v3.0.0"},
            {"t": INC - 1, "service": "productcatalog", "change": "db connection pool exhausted"},
        ]
        traces = [{"trace_id": "c1a2f8", "root": "frontend.GET /",
                   "error_span": "productcatalog.GetProduct", "status": "ERROR", "t": INC + 4}]

    elif scenario == "symptom_louder":
        gt = "productcatalog"
        _inject(T, "productcatalog", 0.18, 455, rng)  # the root — moderate
        _inject(T, "frontend", 0.31, 340, rng)        # LOUDER symptom
        _inject(T, "cart", 0.12, 170, rng)
        changes = [
            {"t": 38, "service": "frontend", "change": "deploy v4.2.0"},  # tempting wrong change
            {"t": INC - 1, "service": "productcatalog", "change": "feature-flag 'ranking_v2'"},
        ]
        traces = [{"trace_id": "d9f451", "root": "frontend.GET /",
                   "error_span": "productcatalog.GetProduct", "status": "ERROR", "t": INC + 5}]

    elif scenario == "noisy_multi_change":
        gt = "payment"
        _inject(T, "payment", 0.20, 390, rng)
        _inject(T, "checkout", 0.10, 215, rng)  # symptom
        changes = [
            {"t": 38, "service": "frontend", "change": "deploy v5.1.0"},
            {"t": INC - 1, "service": "payment", "change": "config: retry budget lowered"},  # true cause
            {"t": INC, "service": "cart", "change": "deploy v2.2.0"},
            {"t": INC + 1, "service": "productcatalog", "change": "cache TTL 60s->5s"},
        ]
        traces = [{"trace_id": "e2b877", "root": "checkout.POST /pay",
                   "error_span": "payment.Charge", "status": "ERROR", "t": INC + 4}]

    else:
        raise ValueError(f"unknown scenario: {scenario}")

    return {"metrics": T, "changes": changes, "traces": traces,
            "ground_truth_root": gt, "scenario": scenario}
