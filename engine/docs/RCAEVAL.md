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
- **Graph:** each system's static service topology (Online Boutique's gRPC call
  graph is encoded in `rca_rcaeval.OB_DEPS`).
- **Metric:** **Top-k** = the ground-truth service is within the top-k ranked
  candidates; **coverage** = fraction of cases with any candidate.

## Result — RE1-OB (Online Boutique, 125 cases), measured

| elevated signal | Top-1 | Top-3 | coverage |
|---|---:|---:|---:|
| within-domain broad (≥1 metric) | 0.664 | **0.920** | 0.992 |
| within-domain selective (≥2 metrics) | **0.800** | 0.816 | 0.840 |

Per-fault Top-1 (selective): **delay 1.000 · disk 1.000 · mem 1.000**, cpu 0.360,
loss 0.640. The two signals give a **coverage/precision trade-off**: broad finds
the region more often (Top-3 0.920); selective is sharper at Top-1 (0.800) but
misses more (coverage 0.840). CPU and network-loss faults are the weak spots — a
disclosed failure mode, not smoothed over.

## Scope and boundary (what is / is not claimed)
- **Measured:** RE1-OB only (125 cases). Sock Shop / Train Ticket (RE1-SS/TT) and
  the RE2/RE3 tiers are **not yet included**.
- **No baseline comparison is claimed yet** — these are Sentinel's own numbers;
  positioning against RCAEval's 15 baselines requires their per-system reported
  results and is future work.
- The localization rule is deterministic and unchanged; only the adapter is new,
  and the signal is fixed a priori (not tuned to the benchmark).
- Corpus and card are git-ignored (regenerated via `make validate-rcaeval`).
