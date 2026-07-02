"""HTTP surface for the Sentinel incident engine.

This module adds *no* detection or correlation logic of its own. It calls the
existing, tested functions in ``sentinel.incident_agent`` (``detect`` ->
``localize`` -> ``find_root_cause`` -> ``investigate``) and reads the
``telemetry_sim.simulate`` store, shaping their output into JSON for the
Sentinel Console BFF. Swap the telemetry source (Demo <-> Prometheus/Tempo)
behind ``DATA_SOURCE`` without touching the engine.

Run:  uvicorn sentinel.api.engine_api:app --port 8008
"""
from __future__ import annotations

import math
import os
import time

import numpy as np
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from sentinel.incident_agent import detect, localize, find_root_cause, investigate, _baseline
from sentinel.telemetry_sim import SERVICES, DEPS, N, INC, SLO_ERR
from sentinel.tools import TelemetryTools
from sentinel.providers import get_provider
from sentinel.scenarios import SCENARIO_META, SCENARIO_IDS

DATA_SOURCE = os.environ.get("DATA_SOURCE", "demo")

app = FastAPI(title="Sentinel incident engine", version="1.0")
# Not strictly required (the Next BFF calls us server-side), but convenient for
# direct inspection and for a browser hitting the engine during development.
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


# --- telemetry source -------------------------------------------------------
# The provider assembles the store (metrics/changes/traces); the engine runs the
# same detect/localize/correlate logic on it regardless of source or scenario.
# Demo is deterministic (cache per scenario); Prometheus re-queries on a short TTL.
_PROVIDER = get_provider()
_TTL = 0.0 if _PROVIDER.name == "demo" else 15.0
_CACHE: dict = {}  # cache key -> {"store": ..., "at": ...}


def _store(scenario: str = "flag_spike"):
    key = scenario if _PROVIDER.name == "demo" else "_prom"
    ent = _CACHE.get(key)
    now = time.time()
    if ent is None or (_TTL and now - ent["at"] > _TTL):
        ent = {"store": _PROVIDER.build_store(scenario), "at": now}
        _CACHE[key] = ent
    return ent["store"]


def _tools(scenario: str = "flag_spike") -> TelemetryTools:
    return TelemetryTools(_store(scenario))


def _scn(scenario: str) -> str:
    """Validate a requested scenario; unknown -> the default flag_spike."""
    return scenario if scenario in SCENARIO_IDS else "flag_spike"


# --- shared analysis (single engine pass, reused by every endpoint) ----------
def _analysis(scenario: str = "flag_spike"):
    store = _store(scenario)
    tools = TelemetryTools(store)
    t, _hot = detect(tools)
    if t is None:
        return {"detected": False, "tools": tools, "store": store}
    culprit, elevated = localize(tools, t)
    cause = find_root_cause(tools, culprit, t)
    return {
        "detected": True,
        "tools": tools,
        "store": store,
        "detect_t": t,
        "culprit": culprit,
        "elevated": elevated,  # {service: error_rate} for services over burn threshold
        "cause": cause,        # {t, service, change} or None
    }


def _confidence(elevated: dict, root: str, has_cause: bool) -> float:
    """Heuristic, derived (not hard-coded): separation of the root's error from
    the loudest *other* elevated service, plus a bump when a change is correlated.
    When a symptom is louder than the root the margin is 0 -> lower confidence,
    which is honest. Documented as heuristic in the UI footer."""
    root_err = elevated[root]
    others = [v for s, v in elevated.items() if s != root]
    loudest_other = max(others) if others else 0.0
    margin = max(0.0, (root_err - loudest_other) / root_err) if root_err > 0 else 0.0
    conf = 0.55 + 0.25 * margin + (0.15 if has_cause else 0.0)
    return round(min(conf, 0.97), 2)


METHOD = (
    "Root-service identification via error-propagation graph analysis — "
    "graph reasoning over the dependency topology, not formal causal inference."
)
FAILURE_MODES = [
    "If a real root's dependency edges are not modelled, propagation reasoning can mislocalize it.",
    "Two independent simultaneous failures yield multiple roots; the highest-error root is chosen.",
    "Change correlation is proximity-based — an unlogged or mis-timestamped change won't surface.",
    "Thresholds are error-budget burn heuristics; a slow burn under the multiple may detect late.",
]


@app.get("/health")
def health():
    return {"status": "ok", "dataSource": DATA_SOURCE, "demo": DATA_SOURCE == "demo"}


@app.get("/investigate")
def api_investigate(scenario: str = Query("flag_spike")):
    scenario = _scn(scenario)
    a = _analysis(scenario)
    if not a["detected"]:
        return {"detected": False, "method": METHOD, "failureModes": FAILURE_MODES}

    tools, t = a["tools"], a["detect_t"]
    root, elevated, cause = a["culprit"], a["elevated"], a["cause"]
    _, report = investigate(a["store"])  # the engine's own human-readable report

    lat0 = _baseline(tools, root, "latency_p95")
    lat1 = float(tools.query_metric(root, "latency_p95", t, t + 1)[0])
    traces = tools.get_error_traces(root)
    failing_span = traces[0]["error_span"] if traces else None
    error_pct = {s: round(v * 100) for s, v in elevated.items()}
    blast = [
        {"service": s, "errorPct": error_pct[s]}
        for s in sorted(elevated, key=elevated.get, reverse=True)
    ]
    conf = _confidence(elevated, root, bool(cause))

    steps = [
        {
            "key": "detected",
            "title": "SLO burn detected",
            "t": t,
            "metric": f"MTTD {t - INC}m",
            "detail": (
                f"Error-budget burn exceeded {5}× the {SLO_ERR*100:.0f}% SLO "
                f"for 2 consecutive minutes (began t={INC}m)."
            ),
        },
        {
            "key": "localized",
            "title": "Root service identified",
            "t": t,
            "service": root,
            "detail": (
                f"{root}: its dependents' errors are explained by it, and it "
                f"depends on nothing elevated — so it is the cause, not a symptom."
            ),
        },
        {
            "key": "correlated",
            "title": "Root-cause change correlated",
            "t": cause["t"] if cause else None,
            "change": cause["change"] if cause else None,
            "detail": (
                f"{cause['change']} on {root} at t={cause['t']}m — closest change "
                f"on the root service to incident onset."
                if cause
                else "No change found on the root service near onset."
            ),
        },
        {
            "key": "proposed",
            "title": "Proposed action",
            "gated": True,
            "detail": (
                f"(1) Roll back {cause['change'] if cause else 'the change'} on "
                f"{root}.  (2) Confirm recovery.  Awaits human approval — the "
                f"engine proposes, it does not act."
            ),
        },
    ]

    return {
        "detected": True,
        "detectT": t,
        "incidentT": INC,
        "mttd": t - INC,
        "root": root,
        "localizationCorrect": root == a["store"].get("ground_truth_root"),
        "groundTruthRoot": a["store"].get("ground_truth_root"),
        "scenario": scenario,
        "sloErrPct": round(SLO_ERR * 100, 2),
        "blastRadius": blast,
        "evidence": {
            "p95Before": round(lat0),
            "p95After": round(lat1),
            "failingSpan": failing_span,
        },
        "change": (
            {"service": cause["service"], "change": cause["change"], "t": cause["t"]}
            if cause
            else None
        ),
        "steps": steps,
        "confidence": conf,
        "method": METHOD,
        "failureModes": FAILURE_MODES,
        "report": report,
        "demo": DATA_SOURCE == "demo",
    }


@app.get("/topology")
def api_topology(scenario: str = Query("flag_spike")):
    a = _analysis(_scn(scenario))
    tools = a["tools"]
    detected = a["detected"]
    elevated = a.get("elevated", {}) if detected else {}
    root = a.get("culprit") if detected else None
    t = a.get("detect_t", N - 1) if detected else N - 1

    def status(s: str) -> str:
        if s == root:
            return "root"
        if s in elevated:
            return "warn"
        return "ok"

    services = []
    for s in SERVICES:
        rps = float(tools.query_metric(s, "rps", t, t + 1)[0])
        err = float(tools.query_metric(s, "error_rate", t, t + 1)[0])
        p95 = float(tools.query_metric(s, "latency_p95", t, t + 1)[0])
        services.append(
            {
                "id": s,
                "status": status(s),
                "rps": round(rps),
                "errorPct": round(err * 100, 1),
                "p95": round(p95),
                "dependsOn": DEPS[s],
            }
        )

    edges = []
    for s in SERVICES:
        for dep in DEPS[s]:
            # errors flow from the dependency (target) up into the dependent
            # (source); the edge is "erroring" when the dependency is elevated.
            edges.append({"source": s, "target": dep, "erroring": dep in elevated})

    return {
        "detected": detected,
        "root": root,
        "incidentT": t,
        "services": services,
        "edges": edges,
        "demo": DATA_SOURCE == "demo",
    }


@app.get("/changes")
def api_changes(scenario: str = Query("flag_spike")):
    """Rank changes by the engine's score (service-match × onset-proximity) and,
    for the differentiator, annotate each with its naive recency rank."""
    scenario = _scn(scenario)
    a = _analysis(scenario)
    store = a["store"]
    changes = store["changes"]
    root = a.get("culprit")
    elevated = a.get("elevated", {})
    cause = a.get("cause")
    onset = a.get("detect_t", INC)

    # naive baseline: rank purely by most-recent-first
    order = sorted(range(len(changes)), key=lambda i: changes[i]["t"], reverse=True)
    recency_rank = {i: r + 1 for r, i in enumerate(order)}

    tau = 6.0
    items = []
    for i, c in enumerate(changes):
        if c["service"] == root:
            service_match = 1.0
        elif c["service"] in elevated:
            service_match = 0.4
        else:
            service_match = 0.1
        onset_prox = math.exp(-abs(c["t"] - onset) / tau)
        score = service_match * onset_prox
        is_root = bool(
            cause and c["service"] == cause["service"] and c["t"] == cause["t"]
        )
        items.append(
            {
                "service": c["service"],
                "change": c["change"],
                "t": c["t"],
                "score": round(score, 4),
                "serviceMatch": round(service_match, 2),
                "onsetProximity": round(onset_prox, 4),
                "recencyRank": recency_rank[i],
                "isRoot": is_root,
            }
        )
    items.sort(key=lambda x: x["score"], reverse=True)
    return {"items": items, "onsetT": onset, "root": root, "demo": DATA_SOURCE == "demo"}


def _slice(range_key: str):
    """Map a UI range to indices of the 60-minute window (only 60 min exist)."""
    if range_key == "10m":
        start = max(0, N - 10)
    else:  # 1h / 24h -> the whole available window
        start = 0
    return start, N


@app.get("/telemetry")
def api_telemetry(
    range_: str = Query("1h", alias="range"),
    service: str | None = Query(None),
    scenario: str = Query("flag_spike"),
):
    a = _analysis(_scn(scenario))
    tools = a["tools"]
    root = a.get("culprit") or a["store"].get("ground_truth_root") or "productcatalog"
    svc = service if service in SERVICES else root
    start, end = _slice(range_)

    err = [round(float(x) * 100, 2) for x in tools.query_metric(svc, "error_rate", start, end)]
    p95 = [round(float(x)) for x in tools.query_metric(svc, "latency_p95", start, end)]
    rps = [round(float(x)) for x in tools.query_metric(svc, "rps", start, end)]
    t_labels = [str(i) for i in range(start, end)]

    incident = None
    if INC < end:  # the incident (INC..N) overlaps the visible slice
        incident = [max(INC, start) - start, (end - 1) - start]

    change_markers = [
        {"t": c["t"] - start, "label": c["change"], "service": c["service"]}
        for c in a["store"]["changes"]
        if start <= c["t"] < end
    ]

    return {
        "service": svc,
        "range": range_,
        "t": t_labels,
        "err": err,
        "p95": p95,
        "rps": rps,
        "slo": round(SLO_ERR * 100, 2),
        "incident": incident,
        "changes": change_markers,
        "demo": DATA_SOURCE == "demo",
    }


def _dep_path(a: str, b: str):
    """A dependency path from service ``a`` down to service ``b`` (a depends on
    … depends on b), following the DEPS edges. None if unreachable."""
    stack = [(a, [a])]
    seen = set()
    while stack:
        node, path = stack.pop()
        if node == b:
            return path
        if node in seen:
            continue
        seen.add(node)
        for d in DEPS.get(node, []):
            stack.append((d, path + [d]))
    return None


def _build_trace(tools, store, root):
    """The failing trace as nested spans along the real dependency path from the
    request entrypoint down to the root service (whose span carries the error).
    Timed from p95 latencies; root-aware so payment- and productcatalog-rooted
    scenarios show the correct failing path."""
    tr = (store.get("traces") or [{}])[0]
    entry_full = tr.get("root", "frontend.GET /")
    error_span = tr.get("error_span", f"{root}.Call" if root else "unknown")
    entry_svc = entry_full.split(".")[0]
    path = _dep_path(entry_svc, root) if root else None
    if not path:
        path = [entry_svc] + ([root] if root and root != entry_svc else [])

    def p95(s):
        return round(float(tools.query_metric(s, "latency_p95", N - 1, N)[0]))

    # durations: root innermost; each parent contains its child plus its own cost
    dur = {}
    prev = 0
    for s in reversed(path):
        dur[s] = p95(s) + prev + (12 if prev else 0)
        prev = dur[s]

    spans = []
    for depth, s in enumerate(path):
        if depth == 0:
            name = entry_full
        elif s == root:
            name = error_span
        else:
            name = f"{s}.Get{s.capitalize()}"
        spans.append({
            "name": name, "service": s, "depth": depth, "start": depth * 10,
            "dur": dur[s], "status": "ERROR" if (s == root or depth == 0) else "OK",
        })
    total = max(s["start"] + s["dur"] for s in spans)
    return {"traceId": tr.get("trace_id", "a1f9c2"), "total": total,
            "errorSpan": error_span, "spans": spans}


@app.get("/panels")
def api_panels(scenario: str = Query("flag_spike")):
    """Derived, secondary panels (host grid, trace, span throughput, latency
    heatmap, error share) — all computed from the same store in one pass so the
    board is internally consistent. Values are derived from real signals; DEMO."""
    a = _analysis(_scn(scenario))
    tools = a["tools"]
    root = a.get("culprit")
    elevated = a.get("elevated", {})
    t = a.get("detect_t", N - 1)

    def status(s):
        return "root" if s == root else ("warn" if s in elevated else "ok")

    def cur(s, sig):
        return float(tools.query_metric(s, sig, t, t + 1)[0])

    # error share: errors/sec per service (rate x throughput)
    error_share = [
        {"service": s, "value": round(cur(s, "error_rate") * cur(s, "rps"), 1),
         "status": status(s)}
        for s in SERVICES
    ]

    # span throughput: spans/sec per service (= request rate)
    span_throughput = [
        {"service": s, "rps": round(cur(s, "rps")), "status": status(s)}
        for s in SERVICES
    ]

    # host/pod grid: pod count from throughput, unhealthy fraction from error rate
    hosts = []
    for s in SERVICES:
        rps = cur(s, "rps")
        err = cur(s, "error_rate")
        st = status(s)
        pods = max(4, round(rps / 22))
        crit = min(pods, round(pods * err)) if st != "ok" else 0
        warn = 1 if (st == "warn" and crit < pods) else 0
        healthy = max(0, pods - crit - warn)
        cells = ["crit"] * crit + ["warn"] * warn + ["ok"] * healthy
        hosts.append({"service": s, "total": pods, "healthy": healthy, "warn": warn,
                      "crit": crit, "cells": cells, "status": st})

    # latency heatmap: percentile band x time (ms), derived from the p95 series
    svc = root or a["store"].get("ground_truth_root") or "productcatalog"
    p95series = [float(x) for x in tools.query_metric(svc, "latency_p95", 0, N)]
    bands = [("p50", 0.52), ("p75", 0.72), ("p90", 0.88), ("p95", 1.0), ("p99", 1.22)]
    cells = []
    for ti, p in enumerate(p95series):
        for bi, (_, mult) in enumerate(bands):
            cells.append([ti, bi, round(p * mult)])
    latency_heatmap = {"service": svc, "bands": [b[0] for b in bands],
                       "t": list(range(N)), "cells": cells, "incidentT": INC}

    trace = _build_trace(tools, a["store"], root)

    return {
        "errorShare": error_share,
        "spanThroughput": span_throughput,
        "hosts": hosts,
        "latencyHeatmap": latency_heatmap,
        "trace": trace,
        "root": root,
        "demo": DATA_SOURCE == "demo",
    }


@app.get("/scenarios")
def api_scenarios():
    """The demo scenario catalogue (id, label, ground-truth root, one-line note)
    so the Console can populate its scenario selector."""
    return {"scenarios": SCENARIO_META, "active": DATA_SOURCE, "demo": DATA_SOURCE == "demo"}


@app.get("/frame")
def api_frame(scenario: str = Query("flag_spike")):
    """One live tick for the SSE stream. In demo mode this continues the
    incident state with small jitter so the board feels alive; clearly DEMO."""
    a = _analysis(_scn(scenario))
    tools = a["tools"]
    root = a.get("culprit") or a["store"].get("ground_truth_root") or "productcatalog"
    elevated = a.get("elevated", {})
    rng = np.random.default_rng()

    # per-service current-state values (last known) with light jitter
    services = {}
    for s in SERVICES:
        base_err = float(tools.query_metric(s, "error_rate", N - 1, N)[0])
        base_p95 = float(tools.query_metric(s, "latency_p95", N - 1, N)[0])
        base_rps = float(tools.query_metric(s, "rps", N - 1, N)[0])
        services[s] = {
            "err": round(max(0.0, base_err + rng.normal(0, 0.004)) * 100, 2),
            "p95": round(max(1.0, base_p95 + rng.normal(0, 12))),
            "rps": round(max(1.0, base_rps + rng.normal(0, 10))),
            "status": "root" if s == a.get("culprit") else ("warn" if s in elevated else "ok"),
        }

    return {
        "ts": int(__import__("time").time() * 1000),
        "root": root,
        "services": services,
        "elevatedCount": len(elevated),
        "demo": DATA_SOURCE == "demo",
    }
