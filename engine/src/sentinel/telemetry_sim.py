"""Synthetic-but-realistic golden-signal telemetry with an injected incident.
In production these signals come from OpenTelemetry -> Collector -> Prometheus/Tempo/Loki;
the sim lets the incident engine and its tests run anywhere, deterministically."""
import numpy as np
DEPS = {"frontend":["productcatalog","cart"], "cart":["productcatalog"],
        "checkout":["cart","payment"], "payment":[], "productcatalog":[]}
SERVICES = list(DEPS)
N, INC, SLO_ERR = 60, 40, 0.01   # 60 min window; incident at t=40; 99% availability SLO

def simulate(seed: int = 7):
    rng = np.random.default_rng(seed)
    T = {s: {"error_rate": np.full(N, 0.004) + rng.normal(0, 0.001, N).clip(0),
             "latency_p95": np.full(N, 120.0) + rng.normal(0, 8, N),
             "rps": np.full(N, 200.0) + rng.normal(0, 15, N)} for s in SERVICES}
    for t in range(INC, N):                      # productcatalog breaks
        T["productcatalog"]["error_rate"][t] = 0.22 + rng.normal(0, 0.02)
        T["productcatalog"]["latency_p95"][t] = 480 + rng.normal(0, 30)
        T["cart"]["error_rate"][t] = 0.09 + rng.normal(0, 0.015)          # cart -> productcatalog
        T["frontend"]["error_rate"][t] = 0.11 + rng.normal(0, 0.015)      # frontend -> productcatalog, cart
        T["frontend"]["latency_p95"][t] = 300 + rng.normal(0, 25)
    changes = [{"t": 12, "service": "payment", "change": "deploy v1.4.2"},
               {"t": INC-1, "service": "productcatalog", "change": "feature-flag 'new_ranking' enabled"},
               {"t": 55, "service": "checkout", "change": "config: timeout 3s->5s"}]
    traces = [{"trace_id": "a1f9c2", "root": "frontend.GET /", "error_span": "productcatalog.GetProduct",
               "status": "ERROR", "t": INC+3}]
    return {"metrics": T, "changes": changes, "traces": traces}
