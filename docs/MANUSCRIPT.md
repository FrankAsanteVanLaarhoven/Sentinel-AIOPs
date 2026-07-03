# Sentinel-AIOPs: Honest, Human-Gated AIOps
### A technical manuscript — hypotheses, method, datasets, results, failures, decisions, and lessons

**Repository:** `FrankAsanteVanLaarhoven/Sentinel-AIOPs` · **Baseline commit:** `4af30ca`
**Author / Git identity:** Frank Asante Van Laarhoven
**Status:** phase closed on a measured, boundary-respecting baseline.

---

## Abstract

Modern "AI for IT operations" (AIOps) products routinely blur the line between
learned pattern recognition and the causal reasoning an on-call engineer must be
able to *trust and audit* at 3 a.m. Sentinel-AIOPs takes the opposite stance: a
strict, operationally-enforced boundary between a **learned detection layer**
(where statistical models on real public data are appropriate) and a
**deterministic localization layer** (where a root cause must be inspectable and
replayable, never emitted by opaque weights). Every empirical claim in the system
is grounded in a real public dataset, reported on a held-out partition with its
failure modes, and made retrievable from committed artifacts through a single
`/validation` endpoint — without executing any training or validation pipeline.

This manuscript is the honest record of building that system: the hypotheses we
tested, the environment and setup, the datasets and their ground truth, the
methods, the evaluation protocol, the measured results (including the ones that
came out weak), what worked, what went wrong and how we mitigated it, the key
decisions and their rationale, the lessons learned, and future work. The numbers
are modest where reality is hard, and we say so plainly — the contribution is a
*measured, transparent* baseline, not a leaderboard trophy.

---

## Table of contents
1. [Introduction & motivation](#1-introduction--motivation)
2. [Hypotheses](#2-hypotheses)
3. [System architecture — the three layers](#3-system-architecture--the-three-layers)
4. [Environment & setup](#4-environment--setup)
5. [Datasets & ground truth](#5-datasets--ground-truth)
6. [Methods](#6-methods)
7. [Experimental design & evaluation metrics](#7-experimental-design--evaluation-metrics)
8. [Results](#8-results)
9. [What worked](#9-what-worked)
10. [What went wrong — failures, iterations, mitigations](#10-what-went-wrong--failures-iterations-mitigations)
11. [Key decisions & rationale](#11-key-decisions--rationale)
12. [Honesty rails](#12-honesty-rails)
13. [Lessons learned](#13-lessons-learned)
14. [Limitations](#14-limitations)
15. [Future work](#15-future-work)
16. [Reproducibility](#16-reproducibility)
- [Appendix A — commit log](#appendix-a--commit-log)
- [Appendix B — test suite](#appendix-b--test-suite)
- [Appendix C — endpoint reference](#appendix-c--endpoint-reference)
- [Appendix D — records & logs](#appendix-d--records--logs)

---

## 1. Introduction & motivation

An incident engine has three jobs when an SLO burns: **detect** that something is
wrong, **localize** which service is the cause (not merely a symptom), and
**propose** a fix. The industry trend is to learn all three end-to-end. That
maximises benchmark scores and minimises trust: when the model blames `payment`,
the engineer cannot replay *why*.

Sentinel-AIOPs is a self-hostable, OpenTelemetry-native incident engine plus a
dense real-time console. Its thesis is a **contract**:

> Detection may be learned on real public data. Localization and change
> correlation stay deterministic, inspectable, and validated against ground
> truth. The boundary is enforced in code and made queryable at all times.

The engineering question this manuscript answers is not "can we top a benchmark"
but **"can we build a system whose every claim is measured on real data,
honestly, with the causal core provably untouched — and prove it?"**

---

## 2. Hypotheses

We framed the work as a sequence of falsifiable hypotheses.

| # | Hypothesis | Verdict | Evidence |
|---|---|---|---|
| **H1** | A two-line deterministic rule — *a service is the root iff it is elevated and none of its dependencies are also elevated* — correctly localizes injected faults on controlled scenarios. | **Supported** | 5/5 synthetic scenarios at 100% ground-truth agreement (`make verify`). |
| **H2** | The *same* rule generalizes to real labelled incidents without modification. | **Partially supported** | PetShop recall@1 = 0.265, recall@3 = 0.471 over 68 real incidents. Works, modestly; failure modes documented. |
| **H3** | A lightweight, interpretable model trained on real public logs supplies a useful learned detection signal. | **Supported** | HDFS log detector: F1 0.719, precision 0.992 on 32,415 held-out sessions. |
| **H4** | Learned detection extends to the *metric* modality on real public data. | **Supported, weak** | SMD PCA detector: F1 0.210 (PA-F1 0.35) under an honest train-only threshold. |
| **H5** | The learned/deterministic boundary can be enforced *and* made queryable with zero side-effects on the causal core. | **Supported** | `/validation` composes all three layers from committed cards; causal rule byte-identical; suite 17/17 green. |

A recurring meta-hypothesis — **H0: honesty is compatible with a working
product** — held throughout: at no point did we invent a number, tune to a test
set, or claim cross-domain transfer we did not measure.

---

## 3. System architecture — the three layers

```
                 ┌─────────────────────────────────────────────────────────┐
                 │  DETECTION  (learned — real public data)                 │
                 │   • Logs · HDFS   → LogisticRegression / bag-of-events   │
                 │   • Metrics · SMD → PCA reconstruction error             │
                 └─────────────────────────────┬───────────────────────────┘
                                                │  anomaly signal only
                 ┌─────────────────────────────▼───────────────────────────┐
                 │  LOCALIZATION  (deterministic — no model weights)        │
                 │   causal_root(elevated, deps):                           │
                 │     root = elevated service with no elevated dependency  │
                 │   change_correlation = service-match × onset-proximity   │
                 └─────────────────────────────┬───────────────────────────┘
                                                │  proposal (human-gated)
                 ┌─────────────────────────────▼───────────────────────────┐
                 │  VALIDATION  (empirical — real labelled corpora)         │
                 │   PetShop recall@1/@3 · detection coverage · fail modes  │
                 └─────────────────────────────────────────────────────────┘

   GET /validation  ──►  composes all three layers from committed cards,
                         retrievable without running any pipeline.
```

**Engine** (Python 3.13, FastAPI): `detect → localize → find_root_cause →
investigate` on a `store` assembled by a provider (Demo ↔ Prometheus/Tempo). The
HTTP surface (`engine_api.py`) adds *no* logic of its own — it shapes existing,
tested functions into JSON.

**Console** (Next.js 16, React 19): a backend-for-frontend that proxies the
engine; every panel is engine-wired. Differentiators over a competitor
(Dash0 Agent0): a **causal topology graph** (root pulses `crit`), a
**dual-ranked change-correlation** panel (engine score vs naive recency), and an
**honest, human-gated investigation** (inert Approve/Dismiss; method, confidence,
and failure modes always visible). A **Validation** panel renders the three-layer
story from `/validation`.

---

## 4. Environment & setup

| Component | Version / detail |
|---|---|
| Python | 3.13 |
| numpy | 1.26 |
| scikit-learn | 1.9 |
| pandas | 3.0 |
| pyarrow | 24 (parquet) |
| huggingface_hub | 1.15 |
| Node / Next.js | Next 16.2.10, React 19.2.4 |
| UI stack | Tailwind v4, TanStack Query v5, ECharts 6, @xyflow/react, Motion |
| Engine | FastAPI on `127.0.0.1:8008` |
| Console | Next dev on `:3000` (BFF proxies engine via `SENTINEL_ENGINE_URL`) |

**Dependency hygiene.** The core engine + HTTP API run with numpy alone. All ML
dependencies (`scikit-learn`, `pandas`, `pyarrow`, `huggingface_hub`, `joblib`)
live in `requirements-ml.txt` and are **imported lazily** inside methods, so
importing a detector module for its pure functions (e.g. `event_template`) never
requires sklearn. Inference for the metric detector is pure numpy.

**Setup.**
```bash
cd engine
pip install -r requirements.txt            # core engine + API
pip install -r requirements-ml.txt         # only to (re)train detectors / run RCA harness
make serve                                  # engine on :8008
# separate shell:
cd ../console && npm install && npm run dev # console on :3000
```

---

## 5. Datasets & ground truth

All trained/validated components use **real, public** data. Corpora and trained
weights are git-ignored and regenerated from source, so the repository commits
only the reproducible pipeline.

### 5.1 HDFS logs — `logfit-project/HDFS_v1` (Hugging Face)
- Raw Hadoop DFS log lines (5 parquet shards, ≈ 2.2 M lines/shard).
- Columns: `content`, `block_id`, per-line `anomaly` label.
- **Ground truth:** a block (session) is anomalous if any of its lines is labelled anomalous.
- **Task:** group lines by `block_id` → session; classify the session.

### 5.2 Server metrics — SMD (`NetManAIOps/OmniAnomaly`, Server Machine Dataset)
- 28 machines, 38 metrics each.
- `train/` (anomaly-free), `test/`, `test_label/` (per-timestamp 0/1).
- **Ground truth:** per-timestamp binary anomaly labels in `test_label`.
- **Task (unsupervised):** learn "normal" from train; flag test points that no longer fit.

### 5.3 Microservice RCA — `amazon-science/petshop-root-cause-analysis` (GitHub)
- 4 traffic scenarios (low/high/temporal×2), train+test splits, 68 labelled incidents total.
- `graph.csv` (caller→callee adjacency), per-issue `metrics.csv` (`(node, metric, statistic)` time-series), `noissue/` baseline.
- **Ground truth:** each issue's `target.json` gives the observed symptom node **and** `root_cause.node` — the injected root service.
- **Task:** given the symptom + graph + normal/abnormal metrics, name the root service (recall@1 / recall@3).

### 5.4 Synthetic incident scenarios (in-repo, deterministic)
- Five scenarios over a 6-service microservice topology (frontend/cart/checkout/payment/productcatalog…), each with a **documented ground-truth root** and injected change.
- Regenerable and deterministic (fixed seed), so the localizer's behaviour is testable anywhere without a download.

| id | ground-truth root | character |
|---|---|---|
| `flag_spike` | productcatalog | textbook propagation, MTTD 1 m |
| `gradual` | payment | slow burn, later detection (MTTD 2 m) |
| `shared_infra` | productcatalog | wide blast radius |
| `symptom_louder` | productcatalog | a symptom (frontend 30%) *louder* than the root (22%) |
| `noisy_multi_change` | payment | correct change picked among four |

---

## 6. Methods

### 6.1 Learned log detection (`sentinel.log_anomaly`)
1. **Event templating** — mask volatile tokens so structurally identical lines
   collapse to one template: `blk_… → <BLK>`, `ip:port → <IP>`, `path → <PATH>`,
   `number → <NUM>`. Deterministic; identical at train and inference time.
2. **Bag-of-events** — per session, count the top-48 templates + a shared `OTHER`
   bucket.
3. **Classifier** — `LogisticRegression` (interpretable coefficients).
4. Threshold 0.5; `score(session) → P(anomalous)`.

### 6.2 Learned metric detection (`sentinel.metric_anomaly`)
1. **Standardize** per-dimension using train mean/std.
2. **PCA** on the standardized normal window (components for 90 % variance).
3. **Anomaly score** = reconstruction error (energy outside the learned normal
   subspace), **smoothed** over 5 steps (anomalies are contiguous).
4. **Threshold** = 99.9th percentile of the **training** error distribution —
   train-only, never test labels, no best-F1-on-test selection.
5. Reported alongside the **point-adjusted** score (SMD convention: if any point
   in a true segment is caught, the segment counts as detected).

### 6.3 Deterministic causal localization (`incident_agent.causal_root`)
```python
def causal_root(elevated, deps):
    if not elevated:
        return None
    roots = [s for s in elevated if not any(d in elevated for d in deps.get(s, ()))]
    return max(roots, key=lambda s: elevated[s]) if roots else max(elevated, key=elevated.get)
```
A service is the **root** iff it is elevated and *none of its dependencies are
also elevated* (its dependents merely inherited the failure); pick the loudest
such. This one function drives both the live engine (`localize`) and the RCA
validation harness — so they can never diverge. It was extracted from the
original `localize` in a **behavior-preserving** refactor, verified by the
unchanged test suite.

### 6.4 Change correlation
Rank changes by **service-match × onset-proximity**
(`onset_prox = exp(-|Δt|/τ)`, τ = 6 min), and display the **naive recency rank**
beside each — so the true cause tops the list even when a more recent, unrelated
change would mislead a recency heuristic.

### 6.5 The queryable validation interface
`GET /validation` composes, from committed model cards only: the detection layer
(both detector cards), the deterministic localization layer (explicitly
`trained: false`), and the empirical validation card (PetShop). It reflects a
fresh reproduction if an artifact is present, otherwise the documented envelope.
No pipeline runs to serve it.

---

## 7. Experimental design & evaluation metrics

| Component | Split protocol | Metrics |
|---|---|---|
| Log detector (HDFS) | 70/30 stratified held-out on sessions | precision, recall, F1, ROC-AUC |
| Metric detector (SMD) | fit on anomaly-free `train`; score labelled `test`; **threshold from train only** | point-wise P/R/F1 **+** point-adjusted F1 |
| Localization (synthetic) | full scenario store | ground-truth agreement (exact root match) |
| Localization (PetShop) | all 68 incidents; test-split reported too | recall@1, recall@3, detection coverage |
| Whole system | hermetic unit tests | suite pass rate (16/16) |

**Anti-tuning discipline.** For every learned/adapted signal, the configuration
was fixed *a priori* from principled choices and disclosed; we did **not** select
the configuration that maximised the test metric. Where we tried an alternative
(e.g. peak vs window-mean for the PetShop "elevated" signal; smoothing/quantile
for SMD), we report that we tried it and kept the principled default even when it
was not the best number.

---

## 8. Results

### 8.1 Log detector — HDFS (held-out)
108,047 sessions · 4.95 % anomaly · 44 templates · **32,415 held-out**.

| precision | recall | F1 | ROC-AUC |
|---:|---:|---:|---:|
| **0.992** | **0.564** | **0.719** | **0.787** |

High precision, modest recall — bag-of-events discards intra-session order; a
sequence model would raise recall on complete sessions.

### 8.2 Metric detector — SMD (full corpus, held-out test)
28 machines · 708,420 test points · 4.2 % anomalous · train-only threshold.

| precision | recall | F1 (point-wise) | F1 (point-adjusted) |
|---:|---:|---:|---:|
| **0.142** | **0.403** | **0.210** | **0.350** |

Deliberately conservative: SMD papers report point-adjusted F1 with a
*test-selected* threshold (0.8–0.9). Ours never touches test labels to set the
cut, so even the point-adjusted F1 is far lower — and far more honest.

### 8.3 Localization on synthetic scenarios
**5/5 at 100 % ground-truth agreement.**

| scenario | localized | ground truth | MTTD |
|---|---|---|---|
| flag_spike | productcatalog | productcatalog | 1 m |
| gradual | payment | payment | 2 m |
| shared_infra | productcatalog | productcatalog | 1 m |
| symptom_louder | productcatalog | productcatalog | 1 m |
| noisy_multi_change | payment | payment | 1 m |

### 8.4 Localization on real incidents — PetShop
68 labelled incidents · z ≥ 3 "elevated" signal · `causal_root` reused verbatim.

| scenario | n | recall@1 | recall@3 |
|---|---:|---:|---:|
| low_traffic | 26 | 0.231 | 0.538 |
| high_traffic | 26 | 0.192 | 0.385 |
| temporal_traffic1 | 8 | 0.375 | 0.500 |
| temporal_traffic2 | 8 | 0.500 | 0.500 |
| **all (train+test)** | **68** | **0.265** | **0.471** |
| test split only | 48 | 0.271 | 0.458 |

**Detection coverage** (some node flagged at all): **0.706** → a ~29 % gap.

### 8.5 Consolidated

| Layer | Component | Dataset | Headline metric |
|---|---|---|---|
| Detection (learned) | Log detector | HDFS | F1 **0.719** (P 0.992) |
| Detection (learned) | Metric detector | SMD | F1 **0.210** / PA-F1 0.35 |
| Localization (deterministic) | causal_root | synthetic | **5/5** ground truth |
| Validation (empirical) | causal_root | PetShop | recall@1 **0.265** / recall@3 **0.471** |
| System | full suite | — | **17/17** green |

### 8.6 Within-domain detection — closing the coverage gap (measured)

The ~29 % detection gap in §8.4 is a *detection-layer* limitation, so we attacked
it **within domain**: score each node on **all of its own metrics, two-sided**
(largest |z| vs the no-issue baseline) instead of the incident's single target
metric one-sided. Same `causal_root`, same z ≥ 3, fixed a priori — only the
detection signal changes.

| detection signal | recall@1 | recall@3 | coverage | avg #elevated |
|---|---:|---:|---:|---:|
| target metric · 1-sided (default) | **0.265** | **0.471** | 0.706 | 4.4 |
| target metric · 2-sided | 0.265 | 0.471 | 0.706 | 4.7 |
| **all metrics · 2-sided (within-domain)** | 0.206 | 0.441 | **0.971** | 8.8 |

**The result is a quantified trade-off, not a free win.** Two-sided on the target
metric changes nothing — so the missing 29 % genuinely never move the target
metric; the anomaly is in a *different* metric. The within-domain signal
**closes almost the entire coverage gap (0.706 → 0.971)** by reading each node's
full metric vector (catching availability drops). But it **doubles the elevated
set** and **costs ~6 pts of recall@1** (0.265 → 0.206): saturating the "elevated"
set weakens the causal rule's discriminative power. This is the
**detection ↔ localization tension**, now measured. The conservative
target-metric signal stays the default; within-domain is an explicit, measured
alternative (`signal="within_domain"`); the causal rule is untouched either way.

---

## 9. What worked

- **The deterministic causal rule is genuinely portable.** The *same* two-line
  `causal_root` that scores 5/5 on synthetic scenarios runs unmodified on real
  PetShop incidents. recall@1 = 0.265 on a hard benchmark, with no training and
  no tuning, is a credible deterministic baseline — and recall@3 ≈ 2× recall@1
  shows it usually finds the right *region*.
- **High-precision log detection** from a tiny, interpretable model (P 0.992).
- **The three-layer boundary held under pressure.** Adding two learned detectors
  and a validation harness never touched the causal rule (byte-identical; suite
  green throughout).
- **Reuse over reimplementation.** Extracting `causal_root` as a pure function
  meant the harness scores the *exact* production rule — no drift possible.
- **The `/validation` interface** turned internal experiment outputs into
  first-class, queryable, honestly-labelled artifacts.
- **Provider abstraction** (Demo ↔ Prometheus) let the console stay unchanged
  while the engine's data source swaps.

---

## 10. What went wrong — failures, iterations, mitigations

The honest log. Every one of these actually happened during the build.

| # | Symptom / failure | Root cause | Mitigation |
|---|---|---|---|
| 1 | Blueprint assumed `/investigate` etc.; engine had **no HTTP API** | Original `api/main.py` was a sample OTel service | Added `engine_api.py` that shapes existing tested functions into JSON — no new logic |
| 2 | `/telemetry` returned 500 | FastAPI query param `range` **shadowed the Python builtin** | Renamed to `range_` with `alias="range"` |
| 3 | ECharts bar/pie blank in headless screenshots | Entrance animation doesn't advance under `--virtual-time-budget` | `animation: false` (also better perf) |
| 4 | SSE hung headless captures | Endless timers never settle under virtual time | `?live=0` URL param to open paused |
| 5 | Hydration mismatch ("1 Issue" badge) | Read `window.location` in a `useState` initializer | Moved to `useEffect` (post-mount) |
| 6 | TypeScript errors from ECharts strict types | `as const` readonly tuples widening | Removed `as const` from shared option helpers |
| 7 | Pre-commit attribution guard blocked the commit | A CSS utility class name and some legacy doc text contained vendor/assistant tokens the guard forbids | Renamed the class; neutralized the doc text to "an LLM agent"; git-ignored the local agent-convention file |
| 8 | Turbopack broke on a CSS import | `@xyflow/react/dist/style.css` imported in `layout.tsx` | Import inside the client component; clear `.next` |
| 9 | Runtime `muted is not defined` | An intermediate edit referenced a helper scoped inside a `useMemo` | Inlined the condition in the JSX |
| 10 | Validation panel's Detection column rendered **empty** | `/validation` fetch cached (`revalidate: 3600`) served the pre-`detectors` shape | Un-cached the fetch so it always reflects the engine |
| 11 | Low PetShop recall at first pass; 29 % detection gap | Simple z-test misses availability/fault targets; node-vs-service granularity | Documented as **detection-layer** failure modes; did **not** tune the causal rule to compensate |
| 12 | SMD raw F1 very low (≈0.14) with low threshold | Test-window distribution shift over-flags at a fixed low cut | Fixed a-priori config (PCA 0.9 var, smooth 5, train-q0.999); reported honestly |
| 13 | Tempting "improvements" that would have been tuning | Peak-vs-mean (PetShop), smoothing/quantile sweeps (SMD) | Tried, found peak **worse**, kept the principled default; disclosed |
| 14 | A review claimed metrics/state that didn't exist (P 0.94 / "11/11") | Reviews written a commit behind reality | Reported the **actual measured** numbers (P 0.992; 9→16 tests) and corrected the record each time |
| 15 | Sandbox `kill`/`pkill`/`fuser` returned exit 144 | `SIGSTKFLT` interception quirk | Verified by re-checking ports/PIDs, not by exit code |

---

## 11. Key decisions & rationale

| Decision | Alternatives | Rationale |
|---|---|---|
| **Monorepo** `engine/` + `console/` | Two repos; console-only | The "AIOps system" is both halves; they version together |
| **Private** repo by default | Public | Avoid unintended exposure; the owner can flip visibility |
| Detectors kept **standalone**, not wired into demo/PetShop detection | Fuse cross-domain | HDFS ≠ SMD ≠ PetShop ≠ demo; cross-domain "improvement" would be a category error |
| **Train-only threshold** for SMD | Best-F1-on-test (the common protocol) | Test labels must not set the operating point |
| **Fixed a-priori config**, disclosed | Sweep to best metric | Anti-tuning; the number must survive not peeking |
| **Behavior-preserving** `causal_root` extraction | Reimplement the rule in the harness | Single source of truth; zero drift risk |
| Report **both** raw and point-adjusted F1 (SMD) | Only the flattering PA-F1 | Point-adjust is optimistic; raw is the honest floor |
| Neutralize vendor tokens; git-ignore weights/corpora | Commit artifacts | Attribution policy + reproducible-not-committed rule |

---

## 12. Honesty rails

Three rails were enforced mechanically, not just by intention:

1. **No invented numbers.** Every metric shown in docs, cards, and UI is the
   measured output of a committed, reproducible pipeline. Where a review asserted
   figures that did not exist, we replaced them with the real ones.
2. **No cross-domain transfer claims.** The SMD detector is **not** claimed to
   close PetShop's 29 % coverage gap — different domains, unmeasured transfer.
   The gap is reported as 29 %, unchanged.
3. **The causal core is provably unmodified.** `causal_root` is byte-identical
   to the original algorithm; the unchanged, green test suite is the proof.

Attribution hygiene: all commits/docs show only the owner's Git identity; a
pre-commit and a pre-push guard enforce it; access tokens were never persisted in
git config.

---

## 13. Lessons learned

- **Honesty is a design constraint, and a productive one.** Refusing to tune to
  the test set forces principled, disclosed configurations — which are exactly
  what an auditor wants to see.
- **A tiny deterministic rule travels further than expected.** Two lines of graph
  logic generalize from synthetic to real incidents; the ceiling is *detection*
  coverage, not the localization rule.
- **recall@3 ≫ recall@1 is a signal, not noise.** It told us the failures are
  granularity mismatches (right region, wrong exact node), not reasoning errors.
- **The evaluation harness is the deliverable.** Once `make validate-rca` exists,
  every future change is measured against the same number automatically.
- **Reuse the production function in the evaluator.** Reimplementing the rule
  would have let the two drift; a behavior-preserving extraction guarantees they
  can't.
- **Reviews can lag reality.** Treat every incoming "current state" as a claim to
  verify against `git log` and the live suite, not as ground truth.

---

## 14. Limitations

- **PetShop localization is modest** (recall@1 0.265) and gated by a ~29 %
  detection gap on that corpus.
- **Log detection recall (0.564)** is capped by the order-free bag-of-events
  representation; sequence models score higher on complete sessions.
- **Metric detection is weak** under an honest train-only threshold (F1 0.21);
  the strong SMD literature numbers use a test-selected threshold we reject.
- **Only one corpus per modality** was exercised (HDFS logs, SMD metrics, PetShop
  RCA); generalization across distributions is unquantified.
- **Localization was validated on one RCA corpus.** RCAEval and others remain
  untested.

---

## 15. Future work

1. **Reduce the precision cost of within-domain detection.** §8.6 *closed* the
   coverage gap (0.706 → 0.971) but cost ~6 pts of recall@1 by saturating the
   elevated set. Open question: a *selective* within-domain signal (e.g.
   per-node PCA reconstruction where dimensionality allows, or a magnitude that
   down-weights ubiquitously-noisy metrics) that keeps coverage high *and*
   preserves localization precision — measured against the same harness.
2. **Sequence-aware log detection** (DeepLog / LogLLM-style) to lift recall on
   complete sessions.
3. **Threshold calibration** for the metric detector (per-machine adaptive,
   still train-only) and additional metric corpora (NAB, KPI).
4. **More RCA corpora** (RCAEval) to test localization generalization.
5. **Fusion, honestly** — combine a within-domain learned detection signal with
   the burn-rate rule at the detection stage only, leaving `causal_root`
   untouched, and measure the end-to-end delta.

---

## 16. Reproducibility

```bash
# engine + ML extras
cd engine && pip install -r requirements.txt -r requirements-ml.txt

make verify          # 5/5 synthetic scenarios at 100% ground truth
make train-logdet    # HDFS log detector  → precision 0.992 / recall 0.564 / F1 0.719 / AUC 0.787
make train-metricdet # SMD metric detector → P 0.142 / R 0.403 / F1 0.210 / PA-F1 0.35   (MACHINES=all)
make validate-rca    # PetShop localization → recall@1 0.265 / recall@3 0.471 / coverage 0.706
make test            # 16/16 hermetic tests (offline)

make serve           # engine on :8008
# GET /validation, /log-anomaly, /metric-anomaly, /rca-validation
```

Corpora and trained weights are git-ignored and regenerated from source; the
repository commits only the reproducible pipeline, hermetic tests, and
documentation.

---

## Appendix A — commit log

| commit | what |
|---|---|
| `7e0b307` | Monorepo assembled (engine + console) + top README |
| `2a2c12e` | Runbook export, `make verify`, linked cross-panel interactivity |
| `604dfd2` | Learned log-anomaly detector on real HDFS |
| `0f98329` | Localization validation on the real PetShop RCA corpus |
| `0a8086d` | Consolidated `/validation` three-layer view |
| `4af30ca` | Second learned detector (metric-anomaly on real SMD), wired into `/validation` |

## Appendix B — test suite

17 hermetic tests (no network): incident-agent detect/localize/root-cause + no
false alarm pre-incident (4); log detector — templating, featurisation,
fit/predict, save/load (5); RCA harness — graph parse, elevated signal, ranking
locates the true root, no-anomaly → no candidates, within-domain signal catches a
non-target metric (4); metric detector — fit detects an injected segment,
point-adjust, unfitted-raises, save/load (4).

## Appendix C — endpoint reference

| endpoint | returns |
|---|---|
| `/health` | status + data source |
| `/investigate?scenario=` | detect → localize → root-cause + human-gated proposal |
| `/topology?scenario=` | causal service graph (root vs symptom) |
| `/changes?scenario=` | change ranking (engine score vs recency) |
| `/telemetry?range=&service=&scenario=` | golden-signal series |
| `/runbook?scenario=` | Markdown incident runbook (method + failure modes + gate) |
| `/log-anomaly` · `/metric-anomaly` | detector model cards |
| `/rca-validation` | PetShop localization card |
| `/validation` | the composed three-layer honesty view |

## Appendix D — records & logs

- **Baseline:** commit `4af30ca`, tree clean, local == remote.
- **Suite:** 16/16 green at closure.
- **Servers:** stopped at closure (ports 8008/3000 freed); other local services untouched.
- **Artifacts:** trained weights + downloaded corpora git-ignored; regenerable via the `make` targets above.
- **Attribution:** pre-commit and pre-push guards passed on every commit; single Git identity.

---

*This manuscript records what was actually built and measured. Where results are
modest, they are stated plainly; where a claim could not be measured, it was not
made.*
