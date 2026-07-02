# Architecture

```
services (OpenTelemetry SDK: traces + RED metrics + logs)
   └─OTLP─▶ OTel Collector ─▶ Prometheus (metrics, SLO rules, burn-rate alerts)
                            ─▶ Tempo (traces)
                            ─▶ Loki (logs)
                            ─▶ Grafana (dashboards over all three)
Incident engine (MCP tools: query_metric | list_changes | get_error_traces)
   detect (multi-window burn) ─▶ localize (causal: root has no elevated dependency)
   ─▶ root cause (change near onset) ─▶ report + proposed fix ─▶ [HUMAN GATE] ─▶ act
```

## Design principles
Vendor-neutral (OpenTelemetry, CNCF standard) · golden signals + error-budget SLOs · **causal** localization
(blame the cause, not the symptom) · assistive, human-gated remediation (observe first, act never-without-approval) ·
portable open-source stack (no lock-in). In production, an LLM agent reads the tools over MCP and narrates; the
detection/localization/correlation logic is deterministic and testable.
