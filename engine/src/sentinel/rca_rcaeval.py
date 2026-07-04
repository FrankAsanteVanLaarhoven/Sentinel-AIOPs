"""Validate the deterministic causal-localization rule against the public
**RCAEval** benchmark (Pham et al., TheWebConf 2025; DOI 10.1145/3701716.3715290) —
a standardized microservice RCA corpus of 735 failure cases across three systems
(Online Boutique, Sock Shop, Train Ticket) and three difficulty tiers (RE1/RE2/RE3).

We reuse Sentinel's own signal and rule **verbatim**:
- the within-domain "elevated" signal (:func:`sentinel.rca_petshop.within_domain_elevated`),
- the causal graph rule (:func:`sentinel.incident_agent.causal_root`, via
  :func:`sentinel.rca_petshop.rank_candidates`).

Only the *adapter* is new: RCAEval RE1 ships one ``data.csv`` per case (columns
``time`` + ``{service}_{metric}``) plus ``inject_time.txt``. The pre-injection
window is the baseline; the post-injection window is the incident. The
ground-truth root-cause service is encoded in the case directory name
(``{service}_{fault}``). No localization logic is modified or tuned.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import pandas as pd

from .rca_petshop import Z_DEFAULT, rank_candidates, within_domain_elevated

# --- Static service dependency graphs (caller -> callees). ---------------------
# Online Boutique's canonical gRPC call graph. `main` is the ingress/load path.
OB_DEPS: dict[str, list[str]] = {
    "main": ["frontend"],
    "frontend": [
        "adservice", "cartservice", "checkoutservice", "currencyservice",
        "productcatalogservice", "recommendationservice", "shippingservice",
    ],
    "checkoutservice": [
        "cartservice", "currencyservice", "productcatalogservice",
        "shippingservice", "paymentservice", "emailservice",
    ],
    "recommendationservice": ["productcatalogservice"],
    "cartservice": [],
    "adservice": [], "currencyservice": [], "productcatalogservice": [],
    "shippingservice": [], "paymentservice": [], "emailservice": [],
}

# Sock Shop's documented application-service topology. Candidates are the
# injectable application/routing services only (the ground-truth granularity),
# which — via the `s in deps` filter — excludes host node-exporters (192-168-*),
# `*-exporter`, the network-only istio stubs (`front`/`queue`/`session`), and
# datastores/broker (`*-db`, `rabbitmq`) that RCAEval never labels as root causes.
SS_DEPS: dict[str, list[str]] = {
    "front-end": ["catalogue", "carts", "orders", "user"],
    "orders": ["carts", "payment", "shipping", "user"],
    "carts": [], "catalogue": [], "user": [], "payment": [],
    "shipping": [], "queue-master": [],
}

# Train Ticket. RE1 is metrics-only, so no verified call graph is available for
# its ~40 services; we therefore run TT **graph-free** — candidates are the
# injectable application services (all `ts-*-service`, excluding the `ts`
# aggregate and the `*-mongo`/`*-mysql` datastores), with no dependency edges.
# With an empty graph `causal_root` reduces to "loudest multivariate-anomalous
# app service". This is a weaker use of the rule than OB/SS (no symptom demotion),
# disclosed as such; a verified TT topology (or one derived from RE2/RE3 traces)
# is future work.
TT_APP_SERVICES = [
    "ts-admin-basic-info-service", "ts-admin-order-service", "ts-admin-route-service",
    "ts-admin-travel-service", "ts-admin-user-service", "ts-assurance-service",
    "ts-auth-service", "ts-avatar-service", "ts-basic-service", "ts-cancel-service",
    "ts-config-service", "ts-consign-price-service", "ts-consign-service",
    "ts-contacts-service", "ts-execute-service", "ts-food-map-service", "ts-food-service",
    "ts-inside-payment-service", "ts-news-service", "ts-notification-service",
    "ts-order-other-service", "ts-order-service", "ts-payment-service",
    "ts-preserve-other-service", "ts-preserve-service", "ts-price-service",
    "ts-rebook-service", "ts-route-plan-service", "ts-route-service", "ts-seat-service",
    "ts-security-service", "ts-station-service", "ts-ticket-office-service",
    "ts-ticketinfo-service", "ts-train-service", "ts-travel-plan-service",
    "ts-travel-service", "ts-travel2-service", "ts-user-service",
    "ts-verification-code-service", "ts-voucher-service",
]
TT_DEPS: dict[str, list[str]] = {s: [] for s in TT_APP_SERVICES}

SYSTEM_DEPS = {"OB": OB_DEPS, "SS": SS_DEPS, "TT": TT_DEPS}
FAULTS = ("cpu", "mem", "disk", "delay", "loss")


def load_case(data_csv: str, inject_time: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split one RE1 ``data.csv`` into (normal, abnormal) MultiIndex frames.

    Columns become ``(service, metric, "value")`` so the frames are drop-in
    compatible with :func:`within_domain_elevated`. Rows with ``time <
    inject_time`` are the pre-injection baseline; the rest are the incident.
    """
    df = pd.read_csv(data_csv)
    time_col = "time" if "time" in df.columns else df.columns[0]
    t = pd.to_numeric(df[time_col], errors="coerce")
    tuples, keep = [], []
    for c in df.columns:
        if c == time_col or c.startswith("time") or "_" not in c:
            continue
        svc, metric = c.rsplit("_", 1)
        tuples.append((svc, metric, "value"))
        keep.append(c)
    sub = df[keep].copy()
    sub.columns = pd.MultiIndex.from_tuples(tuples)
    mask = (t < inject_time).to_numpy()
    return sub[mask], sub[~mask]


@dataclass
class BenchEval:
    n: int = 0
    top1: int = 0
    top3: int = 0
    detected: int = 0
    hits: dict = field(default_factory=lambda: {k: 0 for k in range(1, 6)})
    per_fault: dict = field(default_factory=dict)

    def add(self, fault: str, truth: str, ranked: list[str]):
        self.n += 1
        self.detected += len(ranked) > 0
        for k in range(1, 6):  # AC@k = ground truth within the top-k candidates
            if truth in ranked[:k]:
                self.hits[k] += 1
        h1 = ranked[:1] == [truth]
        h3 = truth in ranked[:3]
        self.top1 += h1
        self.top3 += h3
        f = self.per_fault.setdefault(fault, {"n": 0, "top1": 0, "top3": 0})
        f["n"] += 1
        f["top1"] += h1
        f["top3"] += h3

    def ac(self, k: int) -> float:  # AC@k
        return self.hits[k] / self.n if self.n else 0.0

    @property
    def avg5(self) -> float:  # Avg@5 = mean(AC@1..AC@5), RCAEval's headline metric
        return sum(self.hits[k] for k in range(1, 6)) / (5 * self.n) if self.n else 0.0


def evaluate_system(
    system_dir: str,
    system: str = "OB",
    signal: str = "within_domain_selective",
    z_thr: float = Z_DEFAULT,
) -> BenchEval:
    """Run the verbatim causal rule over every RE1 case in ``system_dir``.

    ``signal`` selects the (reused) elevated signal: ``"within_domain"`` (>=1
    metric) or ``"within_domain_selective"`` (>=2 metrics). The ranking rule is
    identical to PetShop and the live engine.
    """
    deps = SYSTEM_DEPS[system]
    min_metrics = 2 if signal == "within_domain_selective" else 1
    ev = BenchEval()
    for case in sorted(os.listdir(system_dir)):
        cdir = os.path.join(system_dir, case)
        if case.startswith(".") or not os.path.isdir(cdir) or "_" not in case:
            continue
        truth, fault = case.rsplit("_", 1)
        if fault not in FAULTS:
            continue
        for inst in sorted(os.listdir(cdir)):
            idir = os.path.join(cdir, inst)
            csv = os.path.join(idir, "data.csv")
            itf = os.path.join(idir, "inject_time.txt")
            if not (os.path.isfile(csv) and os.path.isfile(itf)):
                continue
            inject_time = int(open(itf).read().strip())
            normal, abnormal = load_case(csv, inject_time)
            if len(normal) < 3 or len(abnormal) < 1:
                continue
            elevated = within_domain_elevated(normal, abnormal, z_thr, min_metrics)
            # Candidates = known topology nodes only (drops host node-exporters,
            # `*-exporter`, and duplicate istio stubs that are not real services).
            elevated = {s: m for s, m in elevated.items() if s in deps}
            ev.add(fault, truth, rank_candidates(elevated, deps))
    return ev
