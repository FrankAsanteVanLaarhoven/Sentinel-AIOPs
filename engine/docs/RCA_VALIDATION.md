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

## Within-domain detection — coverage vs precision (measured)
The ~29 % detection gap above is a *detection-layer* limitation, so we attacked
it **within domain** on PetShop's own signals — scoring each node on **all of its
metrics, two-sided** instead of the single target metric one-sided. Two variants,
both with the same `causal_root` rule and the same z ≥ 3 threshold, fixed a
priori (only the detection signal changes): **broad** (elevated if ≥1 metric
deviates) and **selective** (elevated if ≥2 metrics deviate — multivariate
evidence). `make validate-rca` runs all three signals.

Numbers below are reported **all (train+test) / held-out test split** — the test
split is what guards against reading too much into a variant we picked after
comparing several.

| detection signal | recall@1 | recall@3 | coverage | avg #elev |
|---|---:|---:|---:|---:|
| target metric · 1-sided (default) | **0.265 / 0.271** | **0.471 / 0.458** | 0.706 / 0.708 | 4.4 |
| within-domain broad (any ≥1 metric, 2-sided) | 0.206 / 0.208 | 0.441 / 0.438 | **0.971 / 0.958** | 8.8 |
| within-domain selective (≥2 metrics, 2-sided) | 0.250 / 0.229 | 0.471 / 0.396 | 0.941 / 0.917 | 6.3 |

**Findings, stated plainly.**
- Two-sided on the *target* metric alone changes nothing — so the missing 29 %
  genuinely do not move the target metric; the anomaly lives in a *different*
  metric.
- The **broad** within-domain signal **closes almost the entire coverage gap
  (0.706 → 0.971)** by catching availability drops and non-target-metric
  anomalies — but it **doubles the elevated set** (4.4 → 8.8) and **costs ~6 pts
  of recall@1** (0.265 → 0.206). Saturating "elevated" weakens the causal rule.
- The **selective** signal requires **multivariate evidence** (≥2 of a node's
  metrics deviate), on the principle that genuine incidents perturb correlated
  metrics while noise is usually single-metric. It **recovers recall@1 vs broad**
  (0.206 → 0.250 all; 0.208 → 0.229 test) while keeping coverage high (0.941).

**The honest verdict — the tension is mitigated, not eliminated.** On the
combined set the selective signal looks like a near-full recovery, but that is
propped up by the small 20-incident train split. On the **held-out test split**
it does *not* reach the target's recall@1 (0.229 vs 0.271) and its recall@3 even
*dips* (0.458 → 0.396). So: within-domain detection reliably closes the coverage
gap, and multivariate selectivity reliably beats the naive broad signal on
recall@1 — but **no within-domain signal restores full localization precision on
held-out data.** The detection↔localization tension is real.

The conservative target-metric signal remains the **default** (localization-
precision first). `signal="within_domain"` (broad) and
`signal="within_domain_selective"` (≥2 metrics) are explicit, measured
alternatives. None modifies the causal rule.

## Boundary
The harness reads the engine; it never rewrites it. Localization stays
deterministic and replayable; only the detection signal is adapted, and both
options are fixed a priori (not tuned to the benchmark). This is empirical
validation of the deterministic core — not a learned model fitted to a
leaderboard.
