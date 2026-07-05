---
marp: true
paginate: true
size: 16:9
title: "Sentinel-AIOPs — Inspectable Core, Calibrated Detection, Governed Remediation"
author: "Frank Asante Van Laarhoven"
style: |
  :root {
    --bg: #0b0d12; --panel: #12151d; --ink: #e8e9ee; --dim: #98a0b0;
    --line: #232838; --crit: #ff5c6c; --ok: #4ade80; --ice: #7dd3fc;
    --warn: #fbbf24; --det: #22d3ee; --accent: #a5b4fc;
  }
  section {
    background: var(--bg); color: var(--ink);
    font-family: -apple-system, "Segoe UI", Inter, Helvetica, Arial, sans-serif;
    font-size: 26px; padding: 56px 64px; line-height: 1.4;
  }
  h1 { color: #fff; font-size: 46px; letter-spacing: -0.5px; margin-bottom: 8px; }
  h2 { color: var(--accent); font-size: 34px; letter-spacing: -0.3px; border-bottom: 1px solid var(--line); padding-bottom: 8px; }
  h3 { color: var(--ice); font-size: 24px; }
  strong { color: #fff; }
  em { color: var(--dim); font-style: normal; }
  a { color: var(--ice); }
  code { background: var(--panel); color: var(--det); padding: 1px 6px; border-radius: 4px; font-size: 0.86em; }
  table { font-size: 21px; border-collapse: collapse; margin-top: 6px; }
  th { color: var(--dim); font-weight: 600; border-bottom: 1px solid var(--line); text-align: left; padding: 6px 14px; }
  td { border-bottom: 1px solid var(--line); padding: 6px 14px; }
  blockquote { border-left: 3px solid var(--accent); color: var(--ink); padding-left: 18px; font-size: 24px; }
  .crit { color: var(--crit); } .ok { color: var(--ok); } .warn { color: var(--warn); } .det { color: var(--det); }
  .lead { font-size: 30px; }
  .small { font-size: 19px; color: var(--dim); }
  section.title { justify-content: center; }
  section.title h1 { font-size: 56px; }
  ul { margin-top: 4px; }
  li { margin: 3px 0; }
  footer { color: var(--dim); font-size: 15px; }
footer: "Sentinel-AIOPs · Frank Asante Van Laarhoven · ORCID 0009-0006-8931-0364"
---

<!-- _class: title -->
<!-- _paginate: false -->

# Sentinel-AIOPs

## Separating learned detection from deterministic causal localization for **accountable** incident diagnosis

<br>

**Frank Asante Van Laarhoven** · Newcastle University
frankleroyvan@gmail.com · ORCID 0009-0006-8931-0364

<span class="small">github.com/FrankAsanteVanLaarhoven/Sentinel-AIOPs · every number reproducible via <code>make</code></span>

---

## 1 · The problem

The most **consequential** step in incident response is the **least accountable** one.

- **Alert fatigue** — detectors fire often and imprecisely; operators discount them.
- **Opaque localization** — when a system names a root cause, it is usually the argmax of a model you cannot inspect, replay, or reason about at 3 a.m.
- **Structural flaw** — most learned RCA pipelines fold *"is there an anomaly?"* and *"where is the root?"* into one objective.

> After a miss, you cannot tell whether the system failed to **detect** or failed to **localize** — two failures with completely different fixes.

---

## 2 · Why it matters

When that opaque localization is wired into **automated remediation**, a detection error or a spurious root-cause call can trigger an **irreversible action**.

- The step that decides *what to change* is the one you can least audit.
- SRE practice (error budgets, runbooks, human review) exists precisely to keep consequential decisions reviewable — learned RCA rarely ships *with* that gate.

**Design commitment:** the reasoning that must be trusted in production stays **deterministic and inspectable**; only the **signal** that feeds it may be learned.

---

## 3 · Evidence of failure (measured)

On the public **PetShop** corpus (68 labelled incidents), the deterministic core misses ~29% of incidents at the detection stage — **not** the localization stage.

| test | result |
|---|---|
| Two-sided detection on the *target* metric | **no change** (0.265 → 0.265) |
| ⇒ the missing 29% never move the target metric | the anomaly is in a **different** metric |

<span class="lead">A *negative* experiment carried the most information: it **re-attributed the gap to detection**, not to the causal rule.</span>

---

## 4 · Metric → failure mapping

Each metric is defined to expose a specific failure — and to **bound** a specific claim.

| Metric | Failure it exposes | Claim it supports / limits |
|---|---|---|
| Precision | false-positive storms | *supports* "trustworthy when it fires" |
| **Recall@1 / AC@1** | error at the node the engine acts on | *the deployable localization claim* |
| Recall@3 / AC@3 | node-granularity confusion | *supports* region; *limits* exact node |
| Detection coverage | detector never fires | *attributes* the gap to detection |
| Avg #elevated | graph saturation | *explains* the coupling mechanism |
| ECE / Brier | mis-scaled confidence | *bounds* "the probabilities are trustworthy" |
| PA-F1 | *(optimistic)* | <span class="warn">oracle-flagged — never a deployable claim</span> |

---

## 5 · Method — the three-layer contract

```
telemetry ─► [1] DETECTION (learned)     ─► anomaly signal / "elevated" set
                    ▼                         standalone; own held-out data
             [2] LOCALIZATION (deterministic) ─► ranked roots
                    ▼   causal_root — no weights, reused verbatim
             [3] VALIDATION (empirical)   ─► recall@k, coverage on real corpora
                    ▼
             GOVERNED HAND-OFF — proposes, never acts
```

> **Layer 2 is fixed and inspectable; only the signal entering it may change.**
> `causal_root`: *root = elevated service none of whose dependencies are elevated.*

---

## 6 · Method — deployable vs. diagnostic

Separating the two axes is what makes failure **attributable** and the trade-off **improvable**.

| Component | Deployable | Diagnostic |
|---|:--:|:--:|
| detector score + **train-only** threshold | ✓ | ✓ |
| `causal_root` rank[0] (recall@1 / AC@1) | ✓ | ✓ |
| recall@3 · coverage · avg #elevated | | ✓ |
| point-adjusted F1 *(uses segment membership)* | | ✓ <span class="warn">oracle</span> |

**Oracle-leakage prevention:** thresholds fit on **train only**; every elevated-signal variant fixed **a priori**; variants judged on the **held-out** split.

---

## 7 · Experiment setup

| Corpus | Scale | Split |
|---|---|---|
| **HDFS** logs (Xu'09) | 108k sessions, 4.95% anom | 32,415 held-out |
| **SMD** metrics (Su'19) | 28 machines, 708k pts, 4.2% | train-only threshold |
| **PetShop** RCA (Hardt'24) | 4 scenarios, 68 incidents | test = 48 |
| **RCAEval RE1** (Pham'25) | 3 systems × 125 = **375** cases | metrics-only tier |
| synthetic | 5 scenarios | ground-truth roots |

<span class="small">CPU-only, offline. Robot/physical platform: N/A (software AIOps). Reproduce:</span>

```bash
make verify · train-logdet · train-metricdet · validate-rca · validate-rcaeval · compare-baselines · test   # 44/44
```

---

## 8 · Results — learned detection (held-out)

| Detector | Corpus | P | R | F1 | aux |
|---|---|---:|---:|---:|---|
| Log (logistic / templates) | HDFS | **0.992** | 0.564 | **0.719** | AUC 0.787 |
| Metric (PCA reconstruction) | SMD | 0.142 | 0.403 | **0.210** | PA-F1 0.35 |

- Log signal: **high-precision, trustworthy when it fires.**
- Metric F1 is *deliberately* modest — **train-only** threshold. PA-F1 0.35 shown only for comparability, flagged oracle-dependent (prior work selects thresholds on test → ~0.8–0.9).

---

## 9 · Results — detector calibration

*Does a 0.9 score mean ~90%?* One method (isotonic, fit on a disjoint half) — **two honest outcomes.**

| detector | ECE (raw → isotonic) | Brier (raw → isotonic) |
|---|---:|---:|
| Log (HDFS) — a real `predict_proba` | **0.0009** → 0.0010 | 0.021 → 0.021 |
| Metric (SMD) — a reconstruction *error* | 0.139 → **0.0002** | 0.114 → 0.038 |

- **Log detector is already well-calibrated** — recalibration is *unnecessary* (and hurts the tail). Trust its probabilities as-is.
- **Metric detector's raw score is not a probability** — miscalibrated, but isotonic **fixes it decisively**; recalibrate before use.

---

## 10 · Results — deterministic localization

**Synthetic:** 5/5 roots correct — a correctness floor on clean graphs.

**PetShop (verbatim `causal_root`, default target signal):**

| | recall@1 | recall@3 | coverage |
|---|---:|---:|---:|
| all (68) | **0.265** | **0.471** | 0.706 |
| held-out test (48) | 0.271 | 0.458 | 0.708 |

<span class="small">recall@3 ≈ 2× recall@1 because PetShop splits one service across several nodes — the *region* is found more often than the exact node.</span>

---

## 11 · Results — standardized benchmark (RCAEval RE1)

The **same verbatim** `causal_root`, thin adapter, **375** cases across three systems. AC@k = ground-truth service in top-k; Avg@5 = mean(AC@1…AC@5), RCAEval's headline.

| system | signal | AC@1 | AC@3 | Avg@5 |
|---|---|---:|---:|---:|
| Online Boutique | broad | **0.808** | 0.936 | 0.910 |
| Sock Shop | selective | **0.872** | 0.960 | 0.947 |
| Train Ticket | selective *(graph-free)* | **0.864** | 0.960 | 0.942 |
| **aggregate (375)** | selective | **0.845** | **0.912** | **0.900** |

<span class="small">Candidate set = injectable app/routing services (RCAEval's label granularity), fixed a priori. z / min_metrics not tuned on RCAEval.</span>

---

## 12 · Results — vs. baselines (same harness, same cases)

Reproduced in **our** harness on the **same** cases / candidate set / service-level AC@k, RCAEval's documented config.

| system | BARO AC@1 | ε-Diagnosis AC@1 | **Sentinel AC@1** |
|---|---:|---:|---:|
| Online Boutique | 0.720 | 0.056 | **0.808** |
| Sock Shop | 0.496 | 0.000 | **0.872** |
| Train Ticket | 0.224 | — | **0.864** |

<span class="lead">Sentinel beats BARO on AC@1 on **all three** systems (with *either* signal); the gap widens on the larger systems.</span>
<span class="small">Why: BARO's RobustScaler explodes on near-constant columns; our std-floor + per-service + multivariate evidence suppress it. Reproduced numbers, not BARO's published RE1 table; RE1 is metrics-only.</span>

---

## 13 · The core finding — detection ↔ localization coupling

Hold `causal_root` byte-identical; vary **only** the detection signal. *(PetShop; all / held-out test)*

| elevated signal | recall@1 | recall@3 | coverage | #elev |
|---|---:|---:|---:|---:|
| target · 1-sided (default) | **0.265 / 0.271** | 0.471 / 0.458 | 0.706 | 4.4 |
| within-domain **broad** (≥1) | 0.206 / 0.208 | 0.441 / 0.438 | **0.971 / 0.958** | 8.8 |
| within-domain **selective** (≥2) | 0.250 / 0.229 | 0.471 / 0.396 | 0.941 / 0.917 | 6.3 |

<span class="lead">Broadening detection **closes the coverage gap** (0.706 → 0.971) but **saturates the graph** (4.4 → 8.8 elevated) and **costs recall@1**.</span>

---

## 14 · Refinement — and the check that tempered it

**Idea:** genuine incidents perturb *correlated* metrics; noise is usually single-metric ⇒ require **multivariate evidence** (≥2 metrics).

- On the **combined** set: recall@1 recovers **0.206 → 0.250** at coverage 0.941.
- We ran the **held-out** check *because* we'd compared several variants (test-selection risk).

> On held-out test it does **not** reach target recall@1 (0.229 vs 0.271) and recall@3 **dips** (0.458 → 0.396). The combined-set win was propped up by the small train split.

**Lesson:** when you pick a variant after a sweep, the **held-out** number is the claim. *(On the richer-metric RE1 systems, selective is decisively best — §11.)*

---

## 15 · Insight

<span class="lead">Within-domain detection **closes the coverage gap** and multivariate selectivity **beats** the naive broad signal — but **no** within-domain signal restores full localization precision on held-out PetShop data.</span>

The tension is **mitigated, not eliminated.**

- The frontier will not move with cleverer thresholds on the *same* signals.
- It needs a **calibrated, learned** detector whose confidence feeds the causal rule as a **weight**, not a binary bit — and we now know each detector's calibration (§9).
- The architecture already admits this: Layer 2 is fixed, so a better detector drops in **without touching the trusted reasoning.**

---

## 16 · Governed hand-off — propose, never act

Diagnosis leaves Sentinel as a typed **`ActionProposal`** → recorded → governed by a **separate** control plane.

```
diagnose ─► ActionProposal ─► tamper-evident ─► VerdictPlane ─► (human) ─► act
            evidence-linked    audit log         allow / deny /   gate
            propose-only        (hash-chained)    require_human
```

- **Measured autonomy:** a well-grounded rollback → `require_human` (never auto-run); weak evidence → `deny`, **fail-closed**.
- Enforcement demo: the rollback **physically cannot run** until a reviewer approves — every decision in the tamper-evident ledger.
- **Boundary held:** Sentinel evaluates *no* policy and keeps *no* verdict ledger — those live in VerdictPlane.

---

## 17 · Three-paper PhD route

1. **Inspectable core** *(this work)* — deterministic, verbatim-reused localization; validated on PetShop **and** standardized RCAEval RE1 (beats BARO); the measured coupling; both-detector calibration.
2. **Calibrated detection** — a well-calibrated detector consumed as a **soft elevated-magnitude**, co-optimizing coverage and localization precision on held-out data.
3. **Governed remediation** — the `ActionProposal` → VerdictPlane hand-off with a human gate and tamper-evident ledger **already exists** (§16); adds learned-signal integration + a user study of trust.

> Through-line: **trusted reasoning stays inspectable; learning is confined to the signal that feeds it; every claim is measured on held-out data.**

---

## 18 · Next steps

- **RE2 / RE3 tiers + heavier baselines** — extend to logs+traces and to RCD / CIRCA / MicroCause under the same candidate set.
- **Soft-elevation calibration** — feed detector confidence into `causal_root` as a continuous magnitude (decouple coverage from binary saturation).
- **Restore held-out precision** under broad detection — per-node reconstruction / noise-down-weighting / learned within-domain detector.
- **User study** of the method/confidence/failure-mode trace on operator trust.

<span class="small">Paper 1 draft + this deck are the presentable artifact; Paper 2 (Calibrated Detection) uses the measured trade-off as its baseline.</span>

---

<!-- _class: title -->
<!-- _paginate: false -->

# Thank you

**Sentinel-AIOPs** — inspectable core, measured on real data, scoped claims, governed hand-off.

<span class="small">Paper: <code>docs/SENTINEL_PAPER.md</code> · Boundary: <code>docs/PROJECT_BOUNDARY.md</code> · Reproduce: <code>make validate-rcaeval</code></span>

<br>

### Backup — claim boundary

**We claim:** held-out HDFS F1 0.719 (well-calibrated, ECE 0.0009); train-only SMD F1 0.210; PetShop recall@1 0.265 / coverage 0.706; RCAEval RE1 AC@1 0.845 / Avg@5 0.900 (beats reproduced BARO + ε-Diagnosis); the measured coupling.
**We do not claim:** cross-domain transfer · simulation-as-deployment · any oracle-dependent deployable number · benchmark-wide result from a small split · published-BARO comparison (ours is reproduced) · "safety solved" · causal *inference* (it's an error-propagation heuristic).
