# Case study — Explaining the spike, in context

## The bottleneck
When a service degrades, engineers lose time *jumping between tools* to piece together context: metrics here,
traces there, deploy history somewhere else. The frontier (see Dash0's Agent0) is an agent embedded in the
workflow that investigates **where the work is happening** — not a chatbot bolted on the side.

## The system
Sentinel instruments services with OpenTelemetry, ships golden signals to an open-source stack, and runs an
incident engine that detects an SLO breach, **causally localizes** it, finds the root-cause change, and
proposes a fix — behind a human gate.

## The demonstration (real run, reproducible via `make demo`)
A feature-flag change breaks `productcatalog`; errors propagate to `frontend` and `cart`.

```
INCIDENT REPORT  (assistive - human approval required before any action)
When        : detected t=41m  (began t=40m - MTTD=1m)
Severity    : SLO breach - 22% errors on productcatalog vs 1% budget
Blast radius: productcatalog 22%, cart 11%, frontend 9%
Root cause  : productcatalog  (causal: dependents' errors explained by it; it depends on nothing elevated)
Evidence    : p95 119ms -> 483ms; failing span productcatalog.GetProduct;
              change: feature-flag 'new_ranking' enabled on productcatalog at t=39m
Hypothesis  : the change 'feature-flag 'new_ranking' enabled' introduced the failure
Proposed    : (1) roll back the change on productcatalog  (2) confirm recovery   [AWAIT HUMAN APPROVAL]
```

**Measured:** MTTD 1 minute; correct causal localization to `productcatalog` (not the downstream symptoms);
root-cause change identified; rollback proposed, human-gated.

## Why it's production-grade, not a toy
Real OpenTelemetry instrumentation; real Collector/Prometheus/Tempo/Loki/Grafana configs; SLOs as
multi-window burn-rate alerts; causal localization; assistive-with-human-gate remediation; portable and
open-source. The demo uses synthetic telemetry so it runs anywhere; the same tools point at live Prometheus/Tempo.

## Honest scope
The agent proposes, it does not act on production. The runnable demo is deterministic synthetic telemetry;
live data needs a running stack. Numbers above are produced by the engine at runtime, not hard-coded.
