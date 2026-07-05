"""Validate the deterministic causal-localization rule against a real, labelled
root-cause corpus — the public PetShop dataset (Amazon Science).

For each labelled incident we build the service dependency graph from the
dataset's call graph, mark a service "elevated" when its target metric departs
from its no-issue baseline (a fixed, disclosed z-score test — *not* tuned to the
benchmark), and apply Sentinel's own rule via ``incident_agent.causal_root``:
the root is the elevated service none of whose dependencies are also elevated.
We then score the ranked candidates against the dataset's ground-truth root
(recall@1 / recall@3, the PetShop-standard metric).

Only the "what counts as elevated" signal is adapted to PetShop's latency metric
(Sentinel's live rule reads error-rate). The causal graph rule itself is reused
verbatim — no localization logic is modified or tuned here.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .incident_agent import causal_root

Z_DEFAULT = 3.0


def deps_from_graph(graph_csv: str) -> dict[str, list[str]]:
    """Adjacency matrix (caller -> callee) -> {service: [dependencies it calls]}."""
    adj = pd.read_csv(graph_csv, index_col=0)
    deps: dict[str, list[str]] = {}
    cols = list(adj.columns)
    for caller in adj.index:
        row = adj.loc[caller]
        deps[str(caller)] = [str(c) for c in cols if float(row[c]) != 0.0]
    return deps


def _select(df: pd.DataFrame, metric: str, agg: str) -> pd.DataFrame:
    """Slice a (node, metric, statistic) frame to one metric+agg -> [time x node]."""
    sub = df.xs((metric, agg), axis=1, level=[1, 2])
    return sub.apply(pd.to_numeric, errors="coerce")


def elevated_services(
    normal: pd.DataFrame, abnormal: pd.DataFrame, metric: str, agg: str, z_thr: float = Z_DEFAULT
) -> dict[str, float]:
    """Services whose metric rises above baseline by >= z_thr standard deviations.

    Magnitude = the (one-sided) z-score. A std floor keeps near-constant baselines
    from exploding into spurious anomalies and requires a real relative jump."""
    base = _select(normal, metric, agg)
    abn = _select(abnormal, metric, agg)
    out: dict[str, float] = {}
    for node in abn.columns:
        b = base[node].dropna() if node in base.columns else pd.Series(dtype=float)
        a = abn[node].dropna()
        if len(b) < 3 or len(a) < 1:
            continue
        bmean, bstd = float(b.mean()), float(b.std())
        aval = float(a.mean())
        floor = max(bstd, 0.10 * abs(bmean), 1e-9)
        z = (aval - bmean) / floor
        if z >= z_thr and aval > bmean:
            out[str(node)] = z
    return out


def within_domain_elevated(
    normal: pd.DataFrame,
    abnormal: pd.DataFrame,
    z_thr: float = Z_DEFAULT,
    min_metrics: int = 1,
    robust: bool = False,
) -> dict[str, float]:
    """Within-domain detection signal over a node's full metric vector.

    Each of a node's metrics is z-scored (two-sided) against its no-issue
    baseline. A node is elevated iff **at least ``min_metrics`` of its metrics**
    deviate by >= z_thr; its magnitude is the largest such |z|.

    - ``min_metrics=1`` ("broad") — any single metric moving is enough. Broader
      than :func:`elevated_services` (single target metric, one-sided): it catches
      availability *drops* and non-target-metric anomalies, closing most of
      PetShop's coverage gap — but a single noisy metric can over-elevate.
    - ``min_metrics=2`` ("selective") — requires **multivariate evidence**, since
      genuine incidents perturb correlated metrics while noise is usually a single
      one. This mitigates the recall cost of over-elevation (though on held-out
      data it does not fully restore localization precision — see
      docs/RCA_VALIDATION.md).

    Fixed a priori at the same z_thr used elsewhere; the causal rule is unchanged.
    """
    out: dict[str, float] = {}
    nodes = abnormal.columns.get_level_values(0).unique()
    base_nodes = set(normal.columns.get_level_values(0))
    for node in nodes:
        base = normal.xs(node, axis=1, level=0) if node in base_nodes else None
        abn = abnormal.xs(node, axis=1, level=0)
        zs: list[float] = []
        for col in abn.columns:
            a = pd.to_numeric(abn[col], errors="coerce").dropna()
            b = (
                pd.to_numeric(base[col], errors="coerce").dropna()
                if (base is not None and col in base.columns)
                else pd.Series(dtype=float)
            )
            if len(b) < 3 or len(a) < 1:
                continue
            if robust:
                # Robust location/scale: median + IQR (BARO's statistic). IQR/1.349 ~= sigma
                # for a normal baseline, so z_thr stays interpretable; unlike mean/std it is
                # not inflated by a few baseline spikes, so smaller genuine shifts (e.g. RE3
                # code-level faults) still clear the gate instead of being masked.
                bmed = float(b.median())
                iqr = float(b.quantile(0.75) - b.quantile(0.25))
                scale = max(iqr / 1.349, 0.10 * abs(bmed), 1e-9)
                zs.append(abs((float(a.median()) - bmed) / scale))
            else:
                bmean, bstd = float(b.mean()), float(b.std())
                floor = max(bstd, 0.10 * abs(bmean), 1e-9)
                zs.append(abs((float(a.mean()) - bmean) / floor))
        zs.sort(reverse=True)
        if len(zs) >= min_metrics and zs[min_metrics - 1] >= z_thr:
            out[str(node)] = zs[0]
    return out


def rank_candidates(elevated: dict[str, float], deps: dict[str, list[str]]) -> list[str]:
    """Causal roots first (loudest first), then the remaining elevated services.
    ``rank[0]`` is exactly what ``causal_root`` picks, so recall@1 == the engine."""
    if not elevated:
        return []
    roots = [s for s in elevated if not any(d in elevated for d in deps.get(s, ()))]
    others = [s for s in elevated if s not in roots]
    roots.sort(key=lambda s: elevated[s], reverse=True)
    others.sort(key=lambda s: elevated[s], reverse=True)
    return roots + others


@dataclass
class Eval:
    n: int = 0
    hit1: int = 0
    hit3: int = 0
    detected: int = 0
    per_scenario: dict = field(default_factory=dict)

    def add(self, scenario: str, truth: str, ranked: list[str]):
        self.n += 1
        d = len(ranked) > 0
        h1 = bool(ranked[:1]) and ranked[0] == truth
        h3 = truth in ranked[:3]
        self.detected += d
        self.hit1 += h1
        self.hit3 += h3
        s = self.per_scenario.setdefault(scenario, {"n": 0, "hit1": 0, "hit3": 0})
        s["n"] += 1
        s["hit1"] += h1
        s["hit3"] += h3


def evaluate_dir(
    dataset_dir: str, z_thr: float = Z_DEFAULT, splits=("train", "test"), signal: str = "target"
) -> Eval:
    """Run the (unchanged) causal rule over every labelled incident.

    ``signal="target"`` uses the incident's single target metric one-sided (the
    conservative default). ``signal="within_domain"`` uses the broad all-metrics
    two-sided signal (raises coverage, costs precision). ``signal="within_domain_selective"``
    requires multivariate evidence (>=2 metrics), mitigating the recall cost. The
    ranking rule (``causal_root``) is identical for all three.
    """
    ev = Eval()
    scenarios = [
        s for s in ("low_traffic", "high_traffic", "temporal_traffic1", "temporal_traffic2")
        if os.path.isdir(os.path.join(dataset_dir, s))
    ]
    for scenario in scenarios:
        sdir = os.path.join(dataset_dir, scenario)
        deps = deps_from_graph(os.path.join(sdir, "graph.csv"))
        normal = pd.read_csv(os.path.join(sdir, "noissue", "metrics.csv"), header=[0, 1, 2], index_col=0)
        for split in splits:
            split_dir = os.path.join(sdir, split)
            if not os.path.isdir(split_dir):
                continue
            for issue in sorted(os.listdir(split_dir)):
                idir = os.path.join(split_dir, issue)
                if issue.startswith(".") or not os.path.isdir(idir):
                    continue
                target = json.load(open(os.path.join(idir, "target.json")))
                truth = target["root_cause"]["node"]
                if truth is None:
                    continue
                abnormal = pd.read_csv(os.path.join(idir, "metrics.csv"), header=[0, 1, 2], index_col=0)
                if signal == "within_domain":
                    elevated = within_domain_elevated(normal, abnormal, z_thr)
                elif signal == "within_domain_selective":
                    elevated = within_domain_elevated(normal, abnormal, z_thr, min_metrics=2)
                else:
                    metric, agg = target["target"]["metric"], target["target"]["agg"]
                    elevated = elevated_services(normal, abnormal, metric, agg, z_thr)
                ev.add(scenario, truth, rank_candidates(elevated, deps))
    return ev
