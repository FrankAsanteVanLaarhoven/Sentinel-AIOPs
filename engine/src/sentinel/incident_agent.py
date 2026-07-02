"""The 'explain-the-spike' incident engine: detect -> causally localize -> find root cause -> report.
Deterministic and testable. In production, an LLM agent narrates this via the MCP tools; the correlation
logic here is the real engine. Assistive only: proposes, never acts, until a human approves."""
import numpy as np
from .telemetry_sim import SERVICES, DEPS, N, INC, SLO_ERR
from .tools import TelemetryTools

def _baseline(tools, s, signal): return float(np.median(tools.query_metric(s, signal, 0, INC-2)))

def detect(tools, burn=5.0):
    """Multi-window error-budget burn: error_rate > burn*SLO for 2 consecutive minutes."""
    for t in range(1, N):
        hot = [s for s in SERVICES
               if tools.query_metric(s, "error_rate", t, t+1)[0] > burn*SLO_ERR
               and tools.query_metric(s, "error_rate", t-1, t)[0] > burn*SLO_ERR]
        if hot: return t, hot
    return None, []

def causal_root(elevated, deps):
    """The causal rule, as a pure function: a service is the ROOT if it is
    elevated and *none of its dependencies are also elevated* (so its dependents
    merely inherited the failure). Pick the loudest such root, else the loudest
    elevated service overall. Shared verbatim by localize() and the RCA
    validation harness so the two never diverge."""
    if not elevated:
        return None
    roots = [s for s in elevated if not any(d in elevated for d in deps.get(s, ()))]
    return max(roots, key=lambda s: elevated[s]) if roots else max(elevated, key=elevated.get)

def localize(tools, t, burn=5.0):
    """Causal localization: a service is ROOT if none of its dependencies are also elevated."""
    elevated = {s: float(tools.query_metric(s, "error_rate", t, t+1)[0])
                for s in SERVICES if tools.query_metric(s, "error_rate", t, t+1)[0] > burn*SLO_ERR}
    return causal_root(elevated, DEPS), elevated

def find_root_cause(tools, culprit, t):
    cand = [c for c in tools.list_changes(0, t) if c["service"] == culprit]
    return cand[-1] if cand else None

def investigate(store):
    tools = TelemetryTools(store)
    t, _ = detect(tools)
    if t is None:
        return {"detected": False}, "No SLO breach detected in window."
    culprit, elevated = localize(tools, t)
    cause = find_root_cause(tools, culprit, t)
    traces = tools.get_error_traces(culprit)
    m = {"detected": True, "detect_t": t, "mttd_minutes": t - INC, "localized": culprit,
         "localization_correct": culprit == "productcatalog", "root_cause_found": bool(cause),
         "affected": sorted(elevated, key=elevated.get, reverse=True),
         "error_pct": {s: round(v*100) for s, v in elevated.items()}}
    lat0, lat1 = _baseline(tools, culprit, "latency_p95"), float(tools.query_metric(culprit, "latency_p95", t, t+1)[0])
    report = f"""INCIDENT REPORT  (assistive - human approval required before any action)
When        : detected t={t}m  (began t={INC}m - MTTD={t-INC}m)
Severity    : SLO breach - {m['error_pct'][culprit]}% errors on {culprit} vs 1% budget
Blast radius: {', '.join(f'{s} {m['error_pct'][s]}%' for s in m['affected'])}
Root cause  : {culprit}  (causal: dependents' errors explained by it; it depends on nothing elevated)
Evidence    : p95 {lat0:.0f}ms -> {lat1:.0f}ms; failing span {traces[0]['error_span'] if traces else 'n/a'};
              change: {cause['change'] if cause else 'none'} on {culprit} at t={cause['t'] if cause else '?'}m
Hypothesis  : the change '{cause['change'] if cause else '?'}' introduced the failure
Proposed    : (1) roll back the change on {culprit}  (2) confirm recovery   [AWAIT HUMAN APPROVAL]
"""
    return m, report
