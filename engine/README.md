# Sentinel — agent-assisted, OpenTelemetry-native observability

Knowing your system is healthy — and getting help fixing it *in context* when it isn't — is the "Day 2"
discipline engineers stress about most. Sentinel is a small, self-hostable, open-source starter: a service
instrumented end to end with **OpenTelemetry**, a full **Prometheus + Tempo + Loki + Grafana** stack, real
**SLOs / burn-rate alerts**, and an **"explain-the-spike" incident engine** that detects a failure, localizes
it causally, finds the root-cause change, and proposes a fix — **behind a human gate.**

## The incident engine, measured (real run, `make demo`)
A feature-flag change breaks `productcatalog`; errors propagate upstream. The engine:

| Result | Value |
|---|---|
| Mean time to detect (MTTD) | **1 minute** (multi-window error-budget burn) |
| Localization | **productcatalog** — correct, by causal reasoning |
| Root cause found | **yes** — `feature-flag 'new_ranking' enabled` |
| Blast radius | productcatalog 26% · frontend 11% · cart 10% |
| Action | rollback **proposed**, awaits human approval |

Causal localization: a service is the root if **none of its dependencies are also elevated** — so the engine
blames `productcatalog` (which nothing broken feeds) rather than the downstream `frontend`/`cart` that merely
inherit its errors.

## Stack
OpenTelemetry (traces + RED metrics + logs) → OTel Collector → Prometheus (SLOs/alerts) + Tempo (traces) +
Loki (logs) + Grafana (dashboards). Incident engine with MCP-style tools. An LLM agent narrates the
investigation in production; the correlation logic is real and runs offline.

## Quickstart
```bash
make install
make test      # 4 passed — detects, localizes, finds root cause, no false alarm pre-incident
make demo      # prints the incident report + metrics; writes artifacts/incident_report.md
make stack     # full OTel + Grafana stack (Grafana :3000, Prometheus :9090)
make incident  # run the sample service with the failure flag on, to see it live
```

## Honest scope
Real OpenTelemetry instrumentation and real, deploy-ready stack configs. The incident **demo** runs on
synthetic-but-realistic golden-signal telemetry so it reproduces anywhere, deterministically; point the tools
at a live Prometheus/Tempo to run it on real data. The agent is **assistive with a human gate** — it
investigates and proposes; it does not act on production.

## Composes with DriftGuard → SRE for ML
Point Sentinel at a DriftGuard deployment and you get the full loop: **build & self-heal** the ML service
(DriftGuard) + **observe & investigate** it with an agent (Sentinel). Together: ship a real, observable,
self-healing AI service.
