# RCAEval benchmark — deterministic localization on a standardized corpus

[RCAEval](https://doi.org/10.1145/3701716.3715290) (Pham et al., TheWebConf 2025)
is a public root-cause-analysis benchmark: **735 failure cases** across three
microservice systems (Online Boutique, Sock Shop, Train Ticket) and three
difficulty tiers (RE1 metrics-only, RE2 +logs/traces, RE3), shipped with 15
baseline methods. This harness scores Sentinel's **deterministic** `causal_root`
rule — reused verbatim from the live engine — against it.

Reproduce: `make install-ml && make validate-rcaeval`.

## Method
- **Rule (reused verbatim):** `incident_agent.causal_root` via
  `rca_petshop.rank_candidates` — root = elevated service with no elevated
  dependency, loudest first. Identical to PetShop and the live engine.
- **Elevated signal (reused):** `rca_petshop.within_domain_elevated` — a service
  is elevated when its own metrics depart from the **pre-injection baseline**;
  `within_domain` = ≥1 metric, `within_domain_selective` = ≥2 metrics (both
  two-sided, z ≥ 3). Fixed a priori — **not** swept on RCAEval.
- **Adapter (the only new code):** RE1 ships one `data.csv` per case (`time` +
  `{service}_{metric}` columns) and `inject_time.txt`. Rows before the injection
  are the baseline; rows after are the incident. The ground-truth root-cause
  service is the case directory prefix (`{service}_{fault}`).
- **Graph:** each system's static application-service topology (`rca_rcaeval.OB_DEPS`,
  `SS_DEPS`).
- **Candidate set (a disclosed modeling choice):** candidates are the **injectable
  application/routing services** — the granularity at which RCAEval labels ground
  truth. Via the `s in deps` filter this uniformly excludes host node-exporters
  (`192-168-*`), `*-exporter`, istio passthrough/external endpoints, network-only
  istio stubs (`front`/`queue`/`session`), and datastores/brokers (`redis`,
  `*-db`, `rabbitmq`) — none of which is ever a labelled root cause. This is a
  category decision fixed a priori, **not** label tuning; it applies identically
  to every system.
- **Metric:** we report RCAEval's own metrics. **AC@k** = the ground-truth service
  is within the top-k ranked candidates (so our **Top-1/Top-3 are exactly AC@1/AC@3**);
  **Avg@5** = mean(AC@1…AC@5), RCAEval's headline number; **coverage** = fraction of
  cases with any candidate.

## Result — full RE1 (OB + SS + TT, 125 cases each = 375), measured

| system | graph | elevated signal | AC@1 | AC@3 | Avg@5 | coverage |
|---|---|---|---:|---:|---:|---:|
| Online Boutique (OB) | topology | broad (≥1) | **0.808** | 0.936 | **0.910** | 0.992 |
| | | selective (≥2) | 0.800 | 0.816 | 0.811 | 0.840 |
| Sock Shop (SS) | topology | broad (≥1) | 0.792 | 0.864 | 0.878 | 1.000 |
| | | **selective (≥2)** | **0.872** | **0.960** | **0.947** | 1.000 |
| Train Ticket (TT) | graph-free | broad (≥1) | 0.664 | 0.904 | 0.866 | 1.000 |
| | | **selective (≥2)** | **0.864** | **0.960** | **0.942** | 0.992 |
| **aggregate (375)** | | **selective** | **0.845** | **0.912** | **0.900** | — |

The coverage/precision trade-off appears in Avg@5 too: on OB the higher-coverage
**broad** signal has the better Avg@5 (0.910 vs 0.811), while on the richer-metric
SS/TT the **selective** signal wins on every metric.

**Per-fault Top-1 (selective).** OB: delay/disk/mem = 1.000, cpu 0.360, loss 0.640.
SS: disk 0.960, cpu 0.920, mem 0.880, delay/loss 0.800. TT: cpu/mem 1.000, disk 0.920,
delay 0.760, loss 0.640.

**Reading it.** Across three independent microservice systems the **selective**
(multivariate-evidence) signal gives Top-1 0.800 / 0.872 / 0.864 — the same effect
first measured on PetShop, now consistent at scale. Broad over-elevates on the
richer-metric systems (SS/TT), so selective is decisively better there (SS Top-1
0.792→0.872). **Train Ticket is run graph-free** (see below): RE1 has no verified
call graph for its ~40 services, so `causal_root` reduces to the loudest
multivariate-anomalous app service — a *weaker* use of the rule (no symptom
demotion), yet still Top-1 0.864, because a TT fault's own metric signature
dominates. CPU/loss remain the cross-system weak spots — a disclosed failure mode.

## Scope and boundary (what is / is not claimed)
- **Measured:** full RE1 (OB + SS + TT, 375 cases). **RE2/RE3** tiers are **not yet
  included**.
- **Train Ticket is graph-free.** OB and SS use their static topology graph (symptom
  demotion); TT has no verified RE1 call graph, so it is ranked by anomaly magnitude
  over the app-service candidate set. A verified TT topology (or one derived from
  RE2/RE3 traces) is future work and could change TT's numbers either way.
- **No baseline comparison is claimed yet** — these are Sentinel's own numbers;
  positioning against RCAEval's 15 baselines requires their per-system reported
  results and is future work.
- The candidate-set restriction is disclosed above; without it, infra/datastore
  nodes become spurious roots (e.g. OB broad Top-1 falls to 0.664).
- The localization rule is deterministic and unchanged; only the adapter is new,
  and the signal is fixed a priori (not tuned to the benchmark).
- Corpus and card are git-ignored (regenerated via `make validate-rcaeval`).
