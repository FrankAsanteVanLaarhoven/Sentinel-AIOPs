# Localization validation — real RCA corpus (PetShop)

Sentinel's differentiator is a **deterministic** causal localizer. This harness
puts that claim under empirical test against a real, labelled root-cause corpus —
the public [PetShop dataset](https://github.com/amazon-science/petshop-root-cause-analysis)
(Amazon Science) — and reports how often the engine's own rule names the true
root service. It converts the previously-unmeasured "real-incident validation"
KPI into a number.

Reproduce: `make install-ml && make validate-rca`.

## Method
- **Rule (reused verbatim):** `incident_agent.causal_root` — a service is the root
  if it is elevated and *none of its dependencies are also elevated*; take the
  loudest such. The identical function drives the live engine and this harness,
  so they can never diverge. **No localization logic is modified or tuned.**
- **Graph:** PetShop's `graph.csv` call graph → `deps[service] = callees`.
- **Elevated signal (the one domain adaptation):** a service is elevated when its
  incident-window mean of the incident's *target metric* exceeds its no-issue
  baseline by **z ≥ 3** (std floored to avoid near-constant baselines exploding).
  This is a fixed, disclosed criterion — **not swept to fit the benchmark.** The
  live engine uses `error_rate > 5×SLO`; PetShop is a latency corpus, so only the
  "what counts as elevated" test is re-expressed, never the causal rule.
- **Scoring:** recall@1 / recall@3 against `target.json → root_cause.node`, the
  PetShop-standard metric. `rank[0]` is exactly `causal_root`'s pick, so
  **recall@1 = the engine's single answer.**

## Measured results (68 labelled incidents, z ≥ 3)
| scenario | n | recall@1 | recall@3 |
|---|---:|---:|---:|
| low_traffic | 26 | 0.231 | 0.538 |
| high_traffic | 26 | 0.192 | 0.385 |
| temporal_traffic1 | 8 | 0.375 | 0.500 |
| temporal_traffic2 | 8 | 0.500 | 0.500 |
| **all (train+test)** | **68** | **0.265** | **0.471** |
| test split only | 48 | 0.271 | 0.458 |

Detection coverage (some node flagged at all): **0.706**. These are honest,
untuned figures — PetShop is a hard benchmark on which even purpose-built RCA
methods score modestly; a two-line, training-free causal rule landing ~0.27
top-1 / ~0.47 top-3 is a credible deterministic baseline, and the gaps below are
as informative as the hits.

## Failure modes exposed (the point of the exercise)
- **Detection gap (~29%):** many incidents never push any node ≥ 3σ on the target
  metric — availability/fault-type targets, or the root's metric absent from the
  frame. These are **detection-stage** misses, not localization errors; a learned
  detector (see `docs/LOG_ANOMALY.md`) is the intended remedy, not a change to the
  causal rule.
- **Node granularity:** PetShop splits one logical service into several nodes
  (`…_AWS::Lambda`, `…::Function`, the API-Gateway stage). The rule often flags a
  *co-elevated sibling* of the labelled node — which is why recall@3 (0.47) is
  nearly double recall@1 (0.27): the right *region* is found more often than the
  exact node.
- **Dense co-elevation:** real AWS graphs light up many nodes at once, so
  "elevated with no elevated dependency" can admit several candidates.

## Boundary
The harness reads the engine; it never rewrites it. Localization stays
deterministic and replayable; only the elevated signal is adapted, and it is
fixed a priori. This is empirical validation of the deterministic core — not a
learned model fitted to a leaderboard.
