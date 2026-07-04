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
- **Metric:** **Top-k** = the ground-truth service is within the top-k ranked
  candidates; **coverage** = fraction of cases with any candidate.

## Result — RE1-OB + RE1-SS (125 cases each), measured

| system | elevated signal | Top-1 | Top-3 | coverage |
|---|---|---:|---:|---:|
| Online Boutique (OB) | broad (≥1 metric) | **0.808** | **0.936** | 0.992 |
| | selective (≥2 metrics) | 0.800 | 0.816 | 0.840 |
| Sock Shop (SS) | broad (≥1 metric) | 0.792 | 0.864 | 1.000 |
| | **selective (≥2 metrics)** | **0.872** | **0.960** | 1.000 |

**Per-fault Top-1 (selective).** OB: delay/disk/mem = 1.000, cpu 0.360, loss 0.640.
SS: disk 0.960, cpu 0.920, mem 0.880, delay 0.800, loss 0.800.

**Reading it.** The two signals trade off differently per system: on OB broad is
marginally sharper at Top-1 (0.808) while selective wins the harder faults; on the
richer-metric SS, **selective is decisively better** (Top-1 0.792→0.872,
Top-3 0.864→0.960) because broad over-elevates when every service exposes ~30
metrics. This is the same multivariate-evidence effect measured on PetShop, now on
two independent microservice systems. CPU/loss on OB remain the weak spots — a
disclosed failure mode.

## Scope and boundary (what is / is not claimed)
- **Measured:** RE1-OB + RE1-SS (250 cases). **Train Ticket (RE1-TT)** and the
  **RE2/RE3** tiers are **not yet included**.
- **No baseline comparison is claimed yet** — these are Sentinel's own numbers;
  positioning against RCAEval's 15 baselines requires their per-system reported
  results and is future work.
- The candidate-set restriction is disclosed above; without it, infra/datastore
  nodes become spurious roots (e.g. OB broad Top-1 falls to 0.664).
- The localization rule is deterministic and unchanged; only the adapter is new,
  and the signal is fixed a priori (not tuned to the benchmark).
- Corpus and card are git-ignored (regenerated via `make validate-rcaeval`).
