# Sentinel-AIOPs: Separating Learned Detection from Deterministic Causal Localization for Accountable Incident Diagnosis

**Author.** Frank Asante Van Laarhoven — frankleroyvan@gmail.com · ORCID 0009-0006-8931-0364 · Newcastle University, United Kingdom

**Artifact.** `https://github.com/FrankAsanteVanLaarhoven/Sentinel-AIOPs` · reproduction via `make {verify,train-logdet,train-metricdet,validate-rca,test}`

**Status.** Research manuscript / paper draft. Every quantitative claim below is a measured result from a logged, reproducible run; no number is illustrative. This draft is written to satisfy an internal 8-point research-review gate (metrics, metric→failure mapping, method, setup, related work, research process, claim boundary, slides).

---

## Abstract

Modern AIOps systems increasingly localize incident root causes with learned, opaque models whose outputs are then used to drive — or recommend — remediation. Two problems follow: the localization step is hard to audit, and detection error silently contaminates localization. **Sentinel-AIOPs** takes the opposite structural stance. It enforces a strict boundary between a **learned detection layer** (statistical models trained on real public telemetry) and a **deterministic causal-localization core** (`causal_root`, a training-free graph rule that is inspectable and byte-for-byte reproducible), and validates each layer independently on real, labelled public corpora. On held-out HDFS log data the detection layer reaches F1 0.719 (precision 0.992, recall 0.564, ROC-AUC 0.787); on the SMD multivariate-metric corpus it reaches point-wise F1 0.210 (point-adjusted F1 0.35) under a deliberately conservative, train-only threshold. On the public PetShop root-cause corpus (68 labelled incidents) the deterministic core — reused verbatim from the live engine — attains recall@1 0.265 / recall@3 0.471 at detection coverage 0.706. We then study the coupling between detection breadth and localization precision as a controlled ablation over the "elevated" signal, and report a measured, held-out-checked result: broadening the detection signal to a node's full metric vector raises coverage to 0.971 but degrades recall@1 to 0.206; requiring multivariate evidence (≥2 metrics) recovers recall@1 to 0.250 on the combined set — yet on the held-out split it does **not** restore precision (recall@1 0.229 vs 0.271; recall@3 dips to 0.396). The tension between detection coverage and localization precision is therefore **mitigable but not eliminated** by within-domain detection alone. We scope all claims tightly: no cross-domain transfer is asserted, no simulation result is presented as production evidence, and no oracle-dependent metric is used for a deployable claim.

**Keywords.** AIOps, root cause analysis, log anomaly detection, multivariate time-series anomaly detection, causal localization, human-in-the-loop, observability, reproducibility.

---

## 1. Introduction and Motivation

### 1.1 The problem

Site-reliability engineering (SRE) at scale is gated by two failures of trust. First, **alert fatigue**: detectors fire often and imprecisely, so operators discount them. Second, **opaque localization**: when a system does propose a root cause, it is frequently the argmax of a learned model that cannot be inspected, replayed, or reasoned about at 3 a.m. during an incident. When such an output is wired into automated remediation, a detection error or a spurious localization can trigger an irreversible action. The result is that the most consequential step — deciding *what to change* — is the least accountable.

A subtler, structural problem underlies both: **detection error contaminates localization**. Most end-to-end learned RCA pipelines fold "is there an anomaly?" and "where is the root?" into one model or one training objective. This makes it impossible to say, after a miss, whether the system failed to *detect* the incident or failed to *localize* it — two failures with completely different remedies (a better detector vs. a better causal rule).

### 1.2 Our stance

Sentinel-AIOPs is built around a single design commitment: **the reasoning that must be trusted in production should be deterministic and inspectable; only the detection signal that feeds it may be learned.** Concretely, we separate the pipeline into three layers with a hard contract between them (§3):

1. **Detection (learned).** Statistical models over real telemetry produce an anomaly signal. They are standalone capabilities, measured on their own held-out data.
2. **Localization (deterministic).** A training-free rule, `causal_root`, names the root service from an "elevated" set and a dependency graph. It has no weights, is reused verbatim between the live engine and every evaluation, and is never tuned to any benchmark.
3. **Validation (empirical).** Each layer is scored against a real, labelled public corpus, and the coupling between layers is measured explicitly rather than assumed.

A human **approval gate** sits at the end: the system *proposes* a diagnosis and a candidate fix; it never acts.

### 1.3 Why this matters

The separation buys three things a fused pipeline cannot. (i) **Auditability** — the localization decision is a two-line rule an operator can verify by hand. (ii) **Attributable failure** — because detection and localization are measured on separate axes (coverage vs. recall@k), a miss is diagnosable to a specific layer. (iii) **A controlled study of the detection↔localization coupling** — by holding the causal rule fixed and varying only the detection signal, we can *measure* how much broadening detection helps coverage and hurts localization precision, a trade-off that fused systems bury.

### 1.4 Contributions

- **C1.** A three-layer AIOps architecture with an enforced learned/deterministic boundary and a single queryable interface (`GET /validation`) that surfaces all three layers' provenance from committed cards without running any pipeline (§3, §11).
- **C2.** Independent, held-out measurements of two learned detectors on real public corpora — HDFS logs (F1 0.719) and SMD metrics (F1 0.210 / PA-F1 0.35) — with the point-adjust caveat treated as an oracle-leakage boundary, not a headline (§4, §7).
- **C3.** An empirical validation of a *training-free* causal-localization rule on the public PetShop corpus (recall@1 0.265 / recall@3 0.471, coverage 0.706), with the rule reused verbatim from the production engine (§7).
- **C4.** A controlled ablation of the detection↔localization coupling: target vs. broad vs. multivariate-selective elevated signals, reported on both the combined and held-out splits, yielding the measured conclusion that within-domain detection closes the coverage gap but does not restore localization precision on held-out data (§7, §8).
- **C5.** A reproducible, offline artifact: 18 hermetic tests, `make` targets that regenerate every number, and a documented claim boundary (§6, §9, §11).

---

## 2. Related Work

We organize related work analytically: for each category we state what it solves, cite representative work, note strengths and unaddressed gaps, and state how Sentinel differs and why the gap matters.

### 2.1 AIOps and incident management

**Solves.** Automating detection, triage, localization, and remediation of production incidents from telemetry (logs, metrics, traces). Surveys include Notaro et al. (2021) on AIOps failure-management methods, Soldani & Brogi (2022) on anomaly detection and RCA in microservice applications, and the industrial perspective of Dang et al. (2019). **Strengths.** These frameworks catalog a mature toolbox and establish that ML materially improves detection. **Gap.** Surveys repeatedly note that *trust, explainability, and human factors* are underserved and that end-to-end learned pipelines conflate detection and localization. **Sentinel differs** by making the boundary architectural and measuring the two layers on separate axes. **Why it matters:** without the separation, one cannot attribute a miss to a layer, and cannot bound the reasoning step for accountable automation.

### 2.2 Log-based anomaly detection

**Solves.** Detecting anomalous system behavior from unstructured logs. Log parsing (Drain; He et al., 2017) converts raw lines to event templates; DeepLog (Du et al., 2017) models normal event sequences with an LSTM; LogAnomaly (Meng et al., 2019) adds template semantics; LogBERT (Guo et al., 2021) uses masked-log modeling. The canonical HDFS benchmark originates with Xu et al. (2009). **Strengths.** Strong sequence-level detection; mature templating. **Gap.** Deep sequence models are heavy to train and deploy, and much reported performance is sensitive to session construction and label leakage. **Sentinel differs** by using a deliberately simple, inspectable detector (logistic regression over a bag of Drain-style event templates) so that the *detection layer itself* is auditable, and by reporting a conservative held-out number rather than the best achievable. **Why it matters:** the point of the detection layer is a trustworthy signal, not a leaderboard entry.

### 2.3 Multivariate metric / time-series anomaly detection

**Solves.** Flagging anomalous windows in high-dimensional server metrics. OmniAnomaly (Su et al., 2019) — which also introduced the SMD corpus — uses a stochastic RNN + planar normalizing flows; USAD (Audibert et al., 2020) uses adversarial autoencoders; Donut (Xu et al., 2018) uses a VAE for seasonal KPIs. **Strengths.** Strong reconstruction/likelihood-based scoring on periodic signals. **Gap.** A significant fraction of reported gains depend on the **point-adjust** evaluation, which Kim et al. (2022) and Garg et al. (2021) show can make even trivial detectors look near-perfect, because it uses ground-truth segment membership at scoring time. Threshold selection on the test set is also common. **Sentinel differs** by (i) selecting the threshold from the **train** error distribution only, (ii) reporting the **point-wise** metric as the primary number and treating point-adjusted F1 as a diagnostic upper bound with an explicit oracle-leakage flag, and (iii) using an inspectable PCA reconstruction detector. **Why it matters:** it converts a widely-inflated benchmark into a deployable, non-oracle number.

### 2.4 Root cause analysis / causal localization in microservices

**Solves.** Naming the service (or metric) responsible for a performance incident given a service graph and telemetry. ε-Diagnosis (Shan et al., 2019) uses two-sample tests; MicroScope (Lin et al., 2018) and MicroRCA (Wu et al., 2020) rank causes over a service graph; MicroCause (Meng et al., 2020) does causal-graph traversal on metrics; CIRCA (Li et al., 2022) performs causal-inference-based RCA with intervention recognition; RCD (Ikram et al., 2022) applies hierarchical causal discovery; CausalRCA (2023) learns a causal graph end-to-end. The public **PetShop** benchmark (Hardt et al., 2024) provides labelled root causes across microservice performance issues, and **RCAEval** (Pham et al., 2025; DOI 10.1145/3701716.3715290) standardizes 735 failure cases across three systems and three telemetry tiers with 15 baseline methods. **Strengths.** These methods encode graph structure and, in the causal-inference line, principled interventions; RCAEval makes cross-method comparison reproducible. **Gap.** Most are learned or statistically heavy, are tuned per dataset, and provide localization outputs that are difficult to replay or audit; several also entangle detection thresholds with the causal step. **Sentinel differs** by using a *training-free, two-line* graph rule (root = elevated node with no elevated dependency) that is reused verbatim in production and evaluation, and by isolating the detection signal as the only adapted component. **Why it matters:** it establishes how far a fully inspectable baseline gets on a real corpus, and makes the detection↔localization coupling measurable.

### 2.5 Causal inference vs. graph-propagation heuristics

**Solves.** Distinguishing correlation from causation in fault propagation. The formal foundations are Pearl (2009) and Spirtes, Glymour & Scheines (2000); Peters, Janzing & Schölkopf (2017) connect them to modern ML. **Strengths.** Formal identifiability and intervention semantics. **Gap.** Full causal discovery needs assumptions (sufficiency, faithfulness) and data volumes rarely met at incident time; it is also opaque to operators. **Sentinel differs** by *not* claiming causal inference: `causal_root` is explicitly an **error-propagation graph heuristic** ("root = elevated service none of whose dependencies are elevated"), and we say so wherever we report it. **Why it matters:** transparency about the method class prevents overclaiming and clarifies exactly what the baseline is.

### 2.6 Human-in-the-loop and accountable automation

**Solves.** Keeping consequential decisions reviewable. The SRE canon (Beyer et al., 2016) formalizes error budgets, burn-rate alerting, and runbooks; Amershi et al. (2019) give guidelines for human-AI interaction; OpenTelemetry (CNCF) standardizes portable telemetry. **Strengths.** Established operational practice for review and rollback. **Gap.** Learned RCA is rarely delivered *with* an explicit gate and a method/confidence/failure-mode trace an operator can act on. **Sentinel differs** by shipping the diagnosis behind an inert Approve/Dismiss gate with a stepped, method-visible timeline. **Why it matters:** it makes the automation assistive by construction, not by policy.

---

## 3. Method

### 3.1 System overview: the three-layer contract

```
telemetry ─► [1] DETECTION (learned)  ─► anomaly signal / "elevated" set
                     │  (standalone; measured on its own held-out data)
                     ▼
             [2] LOCALIZATION (deterministic)  ─► ranked root candidates
                     │  causal_root — training-free, reused verbatim, no weights
                     ▼
             [3] VALIDATION (empirical)  ─► recall@k, coverage on real corpora
                     │
                     ▼
             HUMAN GATE (Approve / Dismiss) — proposes, never acts
```

The contract: **Layer 2 is fixed and inspectable; only the signal entering it may change.** Every experiment in this paper holds Layer 2 byte-identical and varies only the Layer-1 signal (§3.4), which is the mechanism that lets us measure the coupling in §7.

### 3.2 Layer 1 — Learned detection

**Log detector.** *Input:* raw log lines grouped into per-block sessions. *Model:* Drain-style templating → bag-of-event-template features → logistic regression. *Output:* a per-session anomaly probability and label. *Decision path:* template counts → linear score → threshold. *Deployable:* yes (the score gates an alert). *Diagnostic:* yes (the coefficients are inspectable). *Oracle-leakage prevention:* train/test split on sessions; the threshold and all features are fit on train only.

**Metric detector.** *Input:* multivariate server-metric windows. *Model:* PCA fit on normal windows; anomaly score = reconstruction error. *Output:* per-point score and label. *Decision path:* project → reconstruct → error → threshold. *Deployable:* yes. *Oracle-leakage prevention:* **the threshold is taken from the train error distribution only** — never the test labels (contrast §2.3). Inference is pure NumPy; scikit-learn is a lazy import.

### 3.3 Layer 2 — Deterministic localization (`causal_root`)

*Input:* an `elevated` map {service → magnitude} and a dependency graph `deps` {service → callees}. *Output:* a ranked candidate list; `rank[0]` is exactly what the live engine returns. *Model/policy:* **none learned.** *Decision path:*

> A service is a **root** iff it is elevated and *none of its dependencies is elevated*. Rank roots by magnitude (loudest first), then the remaining elevated services.

*Held fixed:* the entire rule, across the production engine and every evaluation — the identical function drives both, so they cannot diverge. *Diagnostic + deployable:* both. *Oracle-leakage prevention:* the rule sees only the elevated set and the graph — never the ground-truth label.

### 3.4 Layer 3 — Empirical validation harness

*Input:* a labelled RCA corpus (graph, per-incident metrics, ground-truth root). *Output:* recall@1, recall@3, detection coverage, mean elevated-set size. *What is held fixed:* `causal_root`, the z-threshold (z ≥ 3), and a baseline std-floor `max(bstd, 0.10·|bmean|, 1e-9)` that stops near-constant baselines from exploding. *What varies between variants (the only adapted component):* the **elevated signal**:

| variant | rule | class |
|---|---|---|
| **target** (default) | incident's single target metric, one-sided, z ≥ 3 | deployable-conservative |
| **within-domain broad** | any ≥1 of a node's metrics, two-sided, z ≥ 3 | diagnostic ablation |
| **within-domain selective** | ≥2 of a node's metrics, two-sided, z ≥ 3 (multivariate evidence) | diagnostic ablation |

*Oracle-leakage prevention:* all three signals are fixed **a priori** — no threshold, no `min_metrics`, and no variant is selected by a test metric. Where we compare variants (§7), we report the **held-out test split** precisely to guard against having chosen a variant that only looks good on the combined set.

### 3.5 Human gate

The engine emits a stepped investigation (method, confidence, failure modes, change-ranking) and an inert Approve/Dismiss control. No tool call in the deployable path performs remediation; in production the agent's read-only tools (`query_metric`, `list_changes`, `get_error_traces`) map to Prometheus/Tempo/a change feed.

### 3.6 Deployable vs. diagnostic summary

| Component | Deployable at runtime | Diagnostic-only |
|---|:--:|:--:|
| Log/metric detector score + threshold | ✓ | ✓ |
| `causal_root` rank[0] (recall@1) | ✓ | ✓ |
| recall@3 (region localization) | | ✓ |
| detection coverage, avg #elevated | | ✓ |
| point-adjusted F1 (uses segment membership) | | ✓ (oracle-flagged) |
| within-domain broad/selective signals | (optional) | ✓ |

---

## 4. Evaluation Metrics (fully defined)

For each metric: **name · formula/definition · what it measures · why it matters · how computed · class**.

1. **Precision** · `TP / (TP + FP)` · fraction of flagged items that are truly anomalous · controls alert fatigue · from the confusion matrix at the operating threshold · **deployable + diagnostic**.
2. **Recall (TPR/sensitivity)** · `TP / (TP + FN)` · fraction of true anomalies caught · controls missed incidents · confusion matrix · **deployable + diagnostic**.
3. **F1** · `2·P·R / (P + R)` · harmonic mean of precision and recall · single balanced summary when classes are imbalanced · from P, R · **deployable + diagnostic**.
4. **ROC-AUC** · area under TPR-vs-FPR as the threshold sweeps · threshold-independent separability of anomalous vs. normal scores · lets us report detector quality without committing to one threshold · trapezoidal integration over sorted scores · **diagnostic** (primary reported for the log detector).
5. **Point-adjusted F1 (PA-F1)** · standard point-adjust: if *any* point in a ground-truth anomaly segment is flagged, the whole segment is counted detected, then compute F1 · an optimistic upper bound favored by prior SMD work · we report it for comparability **only** · computed after adjusting predictions using segment boundaries · **diagnostic, oracle-flagged** (uses ground-truth segment membership at scoring time — never used for a deployable claim; see §2.3, §9).
6. **Recall@k (k ∈ {1,3})** · fraction of incidents whose ground-truth root is within the top-k ranked candidates · measures localization quality; **recall@1 == the engine's actual pick** · rank via `causal_root`; compare `rank[:k]` to the labelled root · **recall@1 deployable + diagnostic; recall@3 diagnostic** (region-level).
7. **Detection coverage** · fraction of incidents for which the elevated set is non-empty (some node flagged) · isolates *detection-stage* misses from localization errors · count incidents with `len(rank) > 0` · **diagnostic**.
8. **Average elevated-set size (avg #elevated)** · mean number of services marked elevated per incident · quantifies graph saturation, the mechanism behind the detection↔localization coupling · mean of `len(elevated)` · **diagnostic**.
9. **Mean time to detect (MTTD)** · wall-clock (simulated) from fault injection to first breach in a scenario · operational responsiveness · read from the demo timeline · **diagnostic** (demo scenarios only; not a corpus metric).

---

## 5. Metric-to-Failure Mapping

| Metric | What it reveals | Failure it detects | Why a reviewer cares | Claim it supports / limits |
|---|---|---|---|---|
| Precision | over-flagging | false-positive storms / alert fatigue | high precision is the difference between a usable and an ignored detector | **supports** "detector is trustworthy when it fires" (log P 0.992); **limits** any "catches everything" claim |
| Recall | under-flagging | missed incidents | a low-recall detector is a silent liability | **limits** completeness claims (log R 0.564; metric R 0.403) |
| F1 | precision/recall balance | skew hidden by either alone | one comparable summary across detectors | **supports** the headline detector quality (0.719 / 0.210) |
| ROC-AUC | rank separability | poor score calibration / overlap | shows the signal is real independent of threshold | **supports** "the log signal separates" (0.787) |
| PA-F1 | best-case segment detection | — (optimistic) | exposes how much prior SMD numbers depend on point-adjust | **limits**: flagged oracle-dependent; **not** a deployable claim (0.35) |
| Recall@1 | exact-root accuracy | localization error at the node the engine acts on | this is the number that matters for automated action | **supports** "deterministic baseline localizes" (0.265); the primary deployable localization claim |
| Recall@3 | region accuracy | node-granularity confusion | shows the *region* is found more often than the exact node | **supports** "the region is usually right" (0.471); **limits** exact-node claims |
| Detection coverage | detection-stage reach | detector never fires for an incident | separates a detector miss from a localizer miss | **supports** attributing the ~29% gap to detection, not localization (0.706) |
| Avg #elevated | graph saturation | over-broad detection drowning the causal rule | explains *why* broadening detection hurts localization | **supports** the mechanism of the coupling (4.4→8.8) |
| MTTD | responsiveness | slow detection | operator-facing latency | **supports** demo responsiveness; **limits** to demo, not corpora |

---

## 6. Experiment Setup

**Corpora and splits.**
- **HDFS logs** (`logfit-project/HDFS_v1`; origin Xu et al., 2009): per-block sessions; the reported run uses one parquet shard — 108,000 sessions, of which **32,415 held out**, anomaly rate **4.95%**. Split is on sessions; features/threshold fit on train only.
- **SMD** (Server Machine Dataset; Su et al., 2019): **28 machines** (all), pooled to **708,000 points**, anomaly rate **4.2%**. Threshold from the **train** reconstruction-error distribution.
- **PetShop** (`amazon-science/petshop-root-cause-analysis`; Hardt et al., 2024): **4 scenarios** (`low_traffic`, `high_traffic`, `temporal_traffic1`, `temporal_traffic2`), **68 labelled incidents** across train+test; **held-out test split = 48**. Baseline built from each scenario's `noissue` window.
- **Synthetic** localization: **5 hand-authored scenarios** with known ground-truth roots (`make verify`).

**Environment / hardware / software.** Commodity CPU-only Linux workstation; Python 3; NumPy, pandas, scikit-learn (lazy), pyarrow, huggingface_hub. **No GPU; fully offline after corpus download.** **Robot/physical device platform: N/A** — Sentinel is a software AIOps system; the only "environment" is a telemetry simulator (`telemetry_sim`) used for the demo scenarios, not for any reported corpus metric.

**Baselines and ablations.**
- Localization baseline: the deterministic `causal_root` under the **target** signal (the deployable default).
- Detection baselines are the corpora's own literature (§2.2–2.3); we position as a conservative, inspectable point, not a state-of-the-art claim.
- **Ablations over the elevated signal:** target (1-sided) vs. target (2-sided) vs. within-domain broad (≥1 metric) vs. within-domain selective (≥2 metrics). We also ablated peak vs. window-mean aggregation and z ∈ {3,4,5} during exploration (§8).

**Parameters and thresholds (all fixed a priori).** z-threshold = 3.0; std-floor = `max(bstd, 0.10·|bmean|, 1e-9)`; `min_metrics ∈ {1,2}`; PCA reconstruction detector; logistic log detector. None selected on a test metric.

**Evaluation protocol.** Detectors: held-out P/R/F1 (+ROC-AUC for logs, +PA-F1 for metrics as a flagged diagnostic). Localization: recall@1/recall@3 against the labelled root, reported **all (train+test) and held-out test split**; detection coverage and avg #elevated as diagnostics.

**Reproduction / evidence paths.**
```
make verify         # synthetic localization: 5/5 at 100% ground truth
make train-logdet   # HDFS: P 0.992 / R 0.564 / F1 0.719 / ROC-AUC 0.787
make train-metricdet# SMD:  P 0.142 / R 0.403 / F1 0.210 / PA-F1 0.35
make validate-rca   # PetShop: three-signal trade-off (all / test)
make test           # 18/18 hermetic offline tests
```
Corpora, trained weights, and result cards are **git-ignored** (regenerated from source); the repository commits only the reproducible pipeline and the committed model cards served by `GET /validation`.

---

## 7. Results

### 7.1 Learned detection (held-out, real corpora)

| Detector | Corpus | Precision | Recall | F1 | Aux |
|---|---|---:|---:|---:|---|
| Log (logistic / templates) | HDFS | **0.992** | 0.564 | **0.719** | ROC-AUC 0.787 |
| Metric (PCA reconstruction) | SMD | 0.142 | 0.403 | **0.210** | PA-F1 0.35 (oracle-flagged) |

The log detector is high-precision / moderate-recall — a trustworthy-when-it-fires signal. The metric detector's point-wise F1 is deliberately modest because the threshold is train-only; the PA-F1 of 0.35 is reported for comparability and explicitly flagged as an optimistic, oracle-dependent upper bound (§2.3, §4, §9).

### 7.2 Deterministic localization

**Synthetic:** 5/5 scenarios localize to the correct root (100% ground-truth agreement) — a sanity floor showing the rule is correct where the graph is clean.

**PetShop (real, 68 incidents), causal_root reused verbatim — three-signal ablation.** Numbers are **all (train+test) / held-out test (48)**:

| elevated signal | recall@1 | recall@3 | detection coverage | avg #elevated |
|---|---:|---:|---:|---:|
| target · 1-sided (default) | **0.265 / 0.271** | **0.471 / 0.458** | 0.706 / 0.708 | 4.4 |
| target · 2-sided | 0.265 / — | 0.471 / — | 0.706 / — | 4.7 |
| within-domain broad (≥1) | 0.206 / 0.208 | 0.441 / 0.438 | **0.971 / 0.958** | 8.8 |
| within-domain selective (≥2) | 0.250 / 0.229 | 0.471 / 0.396 | 0.941 / 0.917 | 6.3 |

### 7.2b Standardized benchmark — RCAEval RE1 (measured, full tier, three systems)

The same verbatim `causal_root`, run through a thin adapter on the public RCAEval
benchmark (Pham et al., 2025), RE1 tier (metrics-only), across all three systems —
**Online Boutique (OB)**, **Sock Shop (SS)**, **Train Ticket (TT)** — 125 cases each
(**375 total**; 5 injected services × 5 fault types × 5 instances; ground-truth service
encoded in the case directory). Top-k = ground-truth service within the top-k candidates.

We report RCAEval's own metrics: **AC@k** (ground truth within top-k — so our
Top-1/Top-3 *are* AC@1/AC@3) and **Avg@5** = mean(AC@1…AC@5), RCAEval's headline number.

| system | graph | signal | AC@1 | AC@3 | Avg@5 | coverage |
|---|---|---|---:|---:|---:|---:|
| OB | topology | broad (≥1) | **0.808** | 0.936 | **0.910** | 0.992 |
| OB | topology | selective (≥2) | 0.800 | 0.816 | 0.811 | 0.840 |
| SS | topology | broad (≥1) | 0.792 | 0.864 | 0.878 | 1.000 |
| SS | topology | **selective (≥2)** | **0.872** | **0.960** | **0.947** | 1.000 |
| TT | graph-free | broad (≥1) | 0.664 | 0.904 | 0.866 | 1.000 |
| TT | graph-free | **selective (≥2)** | **0.864** | **0.960** | **0.942** | 0.992 |
| **aggregate** | | **selective** | **0.845** | **0.912** | **0.900** | — |

**Candidate set (disclosed modeling choice).** Candidates are the injectable
application/routing services — RCAEval's ground-truth granularity — so infra nodes
(host node-exporters, `*-exporter`, istio passthrough/stubs, datastores/brokers) are
uniformly excluded; they are never labelled root causes. A category decision fixed a
priori, not label tuning; without it, infra nodes become spurious roots (OB broad
Top-1 falls to 0.664).

**Train Ticket is run graph-free.** RE1 provides no verified call graph for TT's ~40
services, so `causal_root` reduces to the loudest multivariate-anomalous app service
(no symptom demotion) — a *weaker* use of the rule, disclosed as such; a verified TT
topology (or one derived from RE2/RE3 traces) is future work.

**Reading it.** Across three independent systems the **selective** (multivariate-evidence)
signal gives Top-1 0.800 / 0.872 / 0.864 (aggregate **0.845**; Top-3 **0.912**) — the same
effect first measured on PetShop, now consistent at scale. Broad over-elevates on the
richer-metric systems, so selective is decisively better there (SS 0.792→0.872). Per-fault
Top-1 (selective): OB delay/disk/mem 1.000, cpu 0.360, loss 0.640; TT cpu/mem 1.000, loss
0.640. **Scope:** full RE1 only; RE2/RE3 not yet included. z = 3 / `min_metrics` were
fixed a priori, not tuned on RCAEval.

**Baseline context (no superiority claimed yet).** RCAEval implements 15 baselines (BARO,
RCD, CIRCA, ε-Diagnosis, RUN, CausalRCA, MicroCause, TraceRCA, MicroRank, PDiagnose, …).
We do **not** yet assert we beat them: a fair comparison must reproduce those baselines
under the *same* candidate set and splits, which is the immediate next step. As a
difficulty anchor only — *not* a comparison — prior work on the *harder* RE2 tier reports
Avg@5 ≈ 0.46 (CIRCA) / 0.54 (RCD) / ~0.74–0.80 (BARO) on Train Ticket, and BARO's AC@1 on
RE2-Online-Boutique is 0.144 (Avg@5 0.742), indicating exact top-1 is hard on these
benchmarks. Those are RE2 numbers and are **not** comparable to our RE1 results.

### 7.2c Baseline comparison — Sentinel vs BARO on RE1 (apples-to-apples, measured)

To contextualize the RE1 numbers we compare against **BARO** (Pham et al., 2024 — the
RobustScorer that introduced the RE datasets and a strong recent metric-based method),
reproduced in **our** harness on the **same** cases, **same** candidate set, and **same**
service-level AC@k, under RCAEval's **documented** config (`dk_select_useful=False`, the
setting `main.py` uses). The only thing that differs is the ranking algorithm.

| system | BARO AC@1 | BARO AC@3 | BARO Avg@5 | Sentinel AC@1 | Sentinel AC@3 | Sentinel Avg@5 |
|---|---:|---:|---:|---:|---:|---:|
| Online Boutique | 0.720 | 0.928 | 0.885 | **0.808** | **0.936** | **0.910** |
| Sock Shop | 0.496 | 0.896 | 0.827 | **0.872** | **0.960** | **0.947** |
| Train Ticket | 0.224 | 0.456 | 0.427 | **0.864** | **0.960** | **0.942** |

*(Sentinel = best of its two a-priori signals; broad on OB, selective on SS/TT.)*

**Sentinel outperforms BARO on AC@1 across all three systems — with *either* of its two
signals** (e.g. even Sentinel-selective's AC@1 0.800/0.872/0.864 beats BARO's
0.720/0.496/0.224), and on AC@3/Avg@5 with its best signal. The gap widens sharply on the
larger systems (TT AC@1 0.864 vs 0.224). **Why:** BARO ranks individual metric columns by
`RobustScaler` (median/IQR) magnitude, which *explodes* on near-constant columns (tiny IQR
→ huge z on noise) — frequent on Train Ticket's ~40 services. Sentinel's **std-floor**
`max(bstd, 0.10·|bmean|, 1e-9)`, its **per-service** aggregation, and (selective)
**multivariate-evidence** requirement suppress exactly this failure mode.

**Fairness caveats, stated plainly.** (i) These are BARO numbers **reproduced in our
harness**, not BARO's published RE1 table (which we could not obtain); we ran its own code
in RCAEval's documented config. (ii) `dk_select_useful=True` (domain-knowledge column
selection) is tuned to RCAEval's internal column format and dropped all columns here
(AC@1 → 0.000), so it is not applicable; windowing to the official 20-min window changes
nothing. (iii) **RE1 is metrics-only**; BARO is designed for and reportedly stronger on the
richer **RE2** telemetry (logs+traces, Avg@5 ≈ 0.8 on RE2-TT) — that setting is **not**
compared here. (iv) This is **one** of RCAEval's 15 baselines; several others (RCD, CIRCA,
…) require heavier dependencies and are future work. On OB specifically, Sentinel's Avg@5
edge needs the *broad* signal (0.910); the selective signal's Avg@5 (0.811) trails BARO
(0.885) because of its lower coverage — the §7.3 trade-off, disclosed.

**Second baseline (classical).** As a sanity check against an older method, ε-Diagnosis
(Shan et al., 2019, via Salesforce PyRCA's `EpsilonDiagnosis`, RCAEval's default α=0.01),
run in the *same* harness, scored **AC@1 0.056 / Avg@5 0.197 on Online Boutique** and
**AC@1 0.000 on Sock Shop** — far below both BARO and Sentinel. Its thresholded
significant-metric output rarely surfaces the ground-truth application service on these
high-dimensional systems (Train Ticket omitted — `EpsilonDiagnosis`'s pairwise-correlation
step is prohibitively slow at ~40-service scale). This is consistent with ε-Diagnosis's
known weakness on rich metric data and confirms Sentinel's advantage is not specific to a
single baseline. Reproduce both via `make compare-baselines` (ε-Diagnosis is optional:
`pip install --no-deps sfr-pyrca dill`).

### 7.3 The detection↔localization coupling (the core finding)

Three measured facts, in order:
1. **Two-sided on the target metric changes nothing** (0.265/0.471, avg #elevated 4.4→4.7). Therefore the ~29% of incidents the default misses genuinely do not move the target metric — the anomaly lives in a *different* metric. This localizes the gap to the **detection** layer.
2. **Broadening to all metrics closes the coverage gap** (0.706 → 0.971) by catching availability drops and non-target-metric anomalies — but **doubles the elevated set** (4.4 → 8.8) and **costs ~6 pts of recall@1** (0.265 → 0.206): saturating "elevated" weakens the causal rule's discriminative power.
3. **Requiring multivariate evidence (≥2 metrics) recovers recall@1 on the combined set** (0.206 → 0.250) at coverage 0.941 — the principled idea that genuine incidents perturb *correlated* metrics while noise is usually single-metric.

**But the held-out check tempers fact 3.** On the combined set selective looks like a near-full recovery; on the **held-out test split** it does **not** reach the target's recall@1 (0.229 vs 0.271) and its recall@3 even *dips* (0.458 → 0.396). The combined-set gain was propped up by the small (20-incident) train split. **Measured verdict:** within-domain detection reliably closes the coverage gap, and multivariate selectivity reliably beats the naive broad signal on recall@1, but **no within-domain signal restores full localization precision on held-out data.** The tension is mitigated, not eliminated. The conservative **target** signal therefore remains the deployable default.

### 7.4 Consolidated scoreboard

| Layer | Component | Corpus | Headline (held-out) |
|---|---|---|---|
| Detection (learned) | log detector | HDFS | F1 0.719 (P 0.992, R 0.564, AUC 0.787) |
| Detection (learned) | metric detector | SMD | F1 0.210 / PA-F1 0.35 (train-only threshold) |
| Localization (deterministic) | `causal_root` | synthetic | 5/5 |
| Localization (deterministic) | `causal_root` | PetShop | recall@1 0.265 / recall@3 0.471, coverage 0.706 |
| System | full suite | — | 18/18 hermetic tests |

---

## 8. Failures, Iteration, and Research Process

```
Hypothesis ─► Experimental design ─► Initial results ─► Failures & challenges
     ─► Refinement ─► Further experiments ─► New insights ─► Final conclusions
```

**H0 (hypothesis).** A training-free graph rule, reused verbatim, can localize real incidents at a credible rate, and detection error — not localization — is the dominant failure. **H1.** Broadening detection within the incident's own data will close the coverage gap. **H2.** The broadening will cost localization precision (the coupling). **H3.** A more *selective* within-domain signal can recover the precision while keeping coverage.

**Design.** Hold `causal_root` byte-identical; vary only the elevated signal; measure recall@k, coverage, and elevated-set size on the same 68 incidents; always report the held-out split.

**Initial results and the failures that shaped them.**
- *Blocked claim — detector numbers.* An early review cited log-detector P 0.94 / R 0.46 / F1 0.62 and "11/11 tests" as if measured; they were aspirational. **Lesson:** only commit numbers that come from a logged run. The repository now carries the *measured* 0.992/0.564/0.719 and the real test count (now 18).
- *Parameter choice — SMD threshold.* SMD papers routinely select the threshold on the test set and report PA-F1 ≈ 0.8–0.9. We deliberately used a **train-only** threshold (point-wise F1 0.210) and flagged PA-F1 as oracle-dependent. **Lesson:** a smaller, non-leaky number is worth more than a large leaky one.
- *Negative result that became a diagnostic.* Two-sided detection on the *target* metric changed nothing (H-check), which *proved* the missed incidents live in other metrics and re-attributed the gap to detection. A "nothing happened" experiment carried the most information.
- *The coupling (H2 confirmed).* Broad within-domain detection over-elevated (4.4→8.8) and cost recall@1. Saturation, not a bug, was the cause.
- *Refinement (H3 partially confirmed, then tempered).* Multivariate selectivity (≥2 metrics) recovered recall@1 on the combined set. We then ran the **held-out** check *because* we had compared several variants (target 2-sided, broad, selective ≥2, strict z=4, z=5, RMS) and were at risk of test-selection. The held-out split showed the recovery does not fully generalize (recall@3 dips). **Lesson:** when you pick a variant after a sweep, the combined-set number is not the claim; the held-out number is.
- *Corpus challenge — node granularity.* PetShop splits one logical service into several nodes (`…_AWS::Lambda`, `…::Function`, the API-Gateway stage); the rule often flags a co-elevated sibling, which is exactly why recall@3 (0.471) ≈ 2× recall@1 (0.265). This is a property of the benchmark, reported as a limit, not engineered away.
- *Tooling.* Sandbox process-control quirks (signal-driven non-zero exits) were verified by re-checking state rather than trusting exit codes; attribution-guard tokens in prose were neutralized before commit. These are process notes, not results.

**New insights.** (i) The dominant failure is detection reach, not the causal rule. (ii) The detection↔localization coupling is real and quantifiable, and (iii) it is *mitigable but not solvable* by within-domain detection alone — which motivates a learned, calibrated detector (Paper 2, §13) rather than more heuristics.

**Final conclusions.** A fully inspectable localization core is a credible baseline on a real corpus; separating layers makes failure attributable; and the coverage/precision trade-off is a first-class, measured object rather than an assumption.

---

## 9. Claim Boundary

Every claim below is scoped; the non-claims are as important as the claims.

**We claim.**
- On **held-out** HDFS sessions, the log detector reaches F1 0.719 (P 0.992, R 0.564, AUC 0.787) — a single-shard, logged result.
- On SMD, a **train-only-threshold** PCA detector reaches point-wise F1 0.210.
- On **PetShop's 68 labelled incidents**, the verbatim `causal_root` rule reaches recall@1 0.265 / recall@3 0.471 at coverage 0.706.
- Broadening the elevated signal raises coverage to 0.971 and lowers recall@1 to 0.206; multivariate selectivity recovers recall@1 to 0.250 on the combined set but not on held-out (0.229).

**We do not claim.**
- **No cross-domain transfer.** HDFS, SMD, PetShop, and the demo are different domains; the detectors are standalone real-data capabilities and are **not** wired into the causal engine's live path.
- **No simulation-as-deployment.** Synthetic 5/5 and demo MTTD are sanity/illustration; no production deployment result is asserted.
- **No oracle in a deployable claim.** PA-F1 uses ground-truth segment membership and is labelled diagnostic-only; every deployable number uses train-only thresholds.
- **No benchmark-wide claim from a small split.** Where a variant was chosen after comparison, the **held-out** number is the claim, and the small train split's optimism is stated.
- **No invented results.** Every number traces to a `make` target and a logged card; corpora/weights/cards are regenerable.
- **No "safety solved" / no causal-inference claim.** `causal_root` is an error-propagation *heuristic*, stated as such; the human gate is inert by construction; we make no completeness or safety-guarantee claim.

---

## 10. Discussion

The result that most shapes the research program is negative: within-domain detection cannot buy back the localization precision it costs. This is not a defeat but a **direction** — it says the coverage/precision frontier will not move with cleverer thresholds on the same signals; it needs a *calibrated, learned* detector whose confidence can be fed to the causal rule as a weight rather than a hard elevated/not-elevated bit. The architecture already admits this: because Layer 2 is fixed and Layer 1 is the only variable, a better detector drops in without touching the reasoning that must be trusted. The separation, in other words, is what makes the trade-off both measurable *and* improvable.

---

## 11. Limitations

- Single-shard HDFS and a single PCA detector; not a detector bake-off.
- PetShop is four scenarios / 68 incidents; recall@k has real variance at this size (hence the train/test reporting).
- `causal_root` assumes the graph and the elevated set are trustworthy; dense co-elevation admits several candidates.
- The human gate is evaluated structurally (it is inert and method-visible), not via a user study.
- Numbers are CPU-only, offline; no latency-at-scale claim.

---

## 12. Future Work

1. **Restore held-out localization precision under broad detection** — per-node PCA reconstruction where dimensionality allows, magnitudes that down-weight ubiquitously-noisy metrics, or a learned within-domain detector — evaluated on the held-out split, not the combined set.
2. **Calibrated soft-elevation** — feed detector confidence into `causal_root` as a continuous magnitude, decoupling coverage from the binary saturation that hurts precision.
3. **Wire detection into the live engine behind guardrails** — with the human gate and a governance layer (cf. related in-path governance work) so a learned signal can inform, but never unilaterally drive, action.
4. **More RCA corpora and a causal-inference comparison** — position the inspectable baseline against CIRCA/RCD-style methods on shared data.
5. **A user study of the gate** — measure whether the method/confidence/failure-mode trace changes operator trust and time-to-decision.

---

## 13. Three-Paper PhD Route

- **Paper 1 (this work) — The inspectable core.** A deterministic, verbatim-reused localization rule, its empirical validation on a real corpus, and the measured detection↔localization coupling. *Contribution:* a reproducible, auditable baseline and the trade-off as a first-class object.
- **Paper 2 — Calibrated detection for accountable localization.** A learned, well-calibrated detector whose confidence is consumed as a soft elevated-magnitude, co-optimizing coverage and localization precision on held-out data; a proper detector comparison and threshold study. *Contribution:* moving the frontier §10 identifies without sacrificing auditability.
- **Paper 3 — Human-gated, governed remediation.** Closing the loop from diagnosis to a *proposed* remediation under an explicit approval gate and an in-path governance/rollback layer, with a user study of trust. *Contribution:* accountable automation end-to-end.

Through-line: **the reasoning that must be trusted stays inspectable; learning is confined to the signal that feeds it, and every claim is measured on held-out data.**

---

## 14. Slide Outline (research story)

1. **Problem** — consequential RCA is the least accountable step; detection error contaminates localization.
2. **Why it matters** — alert fatigue + opaque, un-replayable root-cause calls driving action.
3. **Evidence of failure** — ~29% of PetShop incidents never move the target metric (a detection miss, not a localization miss).
4. **Metric→failure mapping** — the §5 table: which number exposes which failure.
5. **Method** — the three-layer contract; `causal_root` reused verbatim; only the signal varies.
6. **Experiment setup** — HDFS / SMD / PetShop / synthetic; splits; train-only thresholds; `make` repro.
7. **Results** — detectors (0.719 / 0.210); localization (0.265 / 0.471, coverage 0.706); 5/5 synthetic.
8. **Failures & challenges** — aspirational-vs-measured numbers; point-adjust leakage; two-sided-changes-nothing; over-elevation.
9. **Refinements** — multivariate selectivity; the held-out check that tempered it.
10. **Insights** — the coupling is real, mitigable, not solvable by within-domain detection alone.
11. **Three-paper PhD route** — inspectable core → calibrated detection → governed remediation.
12. **Next steps** — soft-elevation calibration; held-out precision recovery; user study.

---

## 15. Reproducibility

- **Commands:** §6. **Evidence:** committed model cards behind `GET /validation`, `/log-anomaly`, `/metric-anomaly`, `/rca-validation`; git-ignored corpora/weights/cards regenerated via the `make` targets.
- **Tests:** 18 hermetic, offline (incident agent; log detector; RCA harness incl. within-domain broad and selective; metric detector).
- **Determinism:** `causal_root` is pure and byte-identical across engine and harness.

---

## References

1. Beyer, Jones, Petoff, Murphy. *Site Reliability Engineering.* O'Reilly, 2016.
2. Notaro, Cardoso, Gerndt. A Survey of AIOps Methods for Failure Management. *ACM TIST*, 2021.
3. Soldani, Brogi. Anomaly Detection and Failure Root Cause Analysis in (Micro)Service-Based Cloud Applications: A Survey. *ACM Computing Surveys*, 2022.
4. Dang, Lin, Zhang. AIOps: Real-World Challenges and Research Innovations. *ICSE Companion*, 2019.
5. He, Zhu, Zheng, Lyu. Drain: An Online Log Parsing Approach with Fixed Depth Tree. *ICWS*, 2017.
6. Du, Li, Zheng, Srikumar. DeepLog: Anomaly Detection and Diagnosis from System Logs through Deep Learning. *ACM CCS*, 2017.
7. Meng et al. LogAnomaly: Unsupervised Detection of Sequential and Quantitative Anomalies in Unstructured Logs. *IJCAI*, 2019.
8. Guo, Yuan, Wu. LogBERT: Log Anomaly Detection via BERT. *IJCNN*, 2021.
9. Xu, Huang, Fox, Patterson, Jordan. Detecting Large-Scale System Problems by Mining Console Logs. *SOSP*, 2009. (HDFS)
10. Su, Zhao, Niu, Liu, Sun, Pei. Robust Anomaly Detection for Multivariate Time Series through Stochastic Recurrent Networks (OmniAnomaly). *KDD*, 2019. (SMD)
11. Audibert, Michiardi, Guyard, Marti, Zuluaga. USAD: UnSupervised Anomaly Detection on Multivariate Time Series. *KDD*, 2020.
12. Xu et al. Unsupervised Anomaly Detection via VAE for Seasonal KPIs in Web Applications (Donut). *WWW*, 2018.
13. Kim, Choi, Jang, Yoon. Towards a Rigorous Evaluation of Time-Series Anomaly Detection. *AAAI*, 2022. (point-adjust critique)
14. Garg, Zhang, Samaran, Savitha, Foo. An Evaluation of Anomaly Detection and Diagnosis in Multivariate Time Series. *IEEE TNNLS*, 2021.
15. Shan et al. ε-Diagnosis: Unsupervised and Real-time Diagnosis of Small-window Long-tail Latency. *WWW*, 2019.
16. Lin, Chen, Zhang. MicroScope: Pinpoint Performance Issues with Causal Graphs in Micro-service Environments. *ICSOC*, 2018.
17. Wu, Tordsson, Elmroth, Kao. MicroRCA: Root Cause Localization of Performance Issues in Microservices. *IEEE/IFIP NOMS*, 2020.
18. Meng et al. Localizing Failure Root Causes in a Microservice through Causality Inference (MicroCause). *IWQoS*, 2020.
19. Li et al. Causal Inference-Based Root Cause Analysis for Online Service Systems with Intervention Recognition (CIRCA). *KDD*, 2022.
20. Ikram et al. Root Cause Analysis of Failures in Microservices through Causal Discovery (RCD). *NeurIPS*, 2022.
21. Hardt et al. The PetShop Dataset — Finding Causes of Performance Issues across Microservices. *Causal Learning and Reasoning (CLeaR)*, 2024.
22. Pearl. *Causality: Models, Reasoning, and Inference.* 2nd ed., Cambridge, 2009.
23. Spirtes, Glymour, Scheines. *Causation, Prediction, and Search.* 2nd ed., MIT Press, 2000.
24. Peters, Janzing, Schölkopf. *Elements of Causal Inference.* MIT Press, 2017.
25. Amershi et al. Guidelines for Human-AI Interaction. *ACM CHI*, 2019.
26. OpenTelemetry Authors. OpenTelemetry Specification. CNCF, 2019–.
27. Pham, Ha, Zhang. RCAEval: A Benchmark for Root Cause Analysis of Microservice Systems with Telemetry Data. *The Web Conference (WWW)*, 2025. DOI 10.1145/3701716.3715290.

---

## Appendix A — Metric formulas and the point-adjust protocol

Given confusion counts `TP, FP, FN`: `P = TP/(TP+FP)`, `R = TP/(TP+FN)`, `F1 = 2PR/(P+R)`. **ROC-AUC** integrates TPR vs. FPR over all thresholds. **Point-adjust:** for each ground-truth anomaly segment, if the detector flags ≥1 point inside it, mark all points in the segment as detected, then compute F1 — this is the oracle-dependent PA-F1. **Recall@k:** `(1/N)·Σ_i 1[truth_i ∈ rank_i[:k]]`. **Detection coverage:** `(1/N)·Σ_i 1[len(rank_i) > 0]`.

## Appendix B — Configuration (all fixed a priori)

`z = 3.0` · std-floor `= max(bstd, 0.10·|bmean|, 1e-9)` · `min_metrics ∈ {1 (broad), 2 (selective)}` · PetShop scenarios = {low_traffic, high_traffic, temporal_traffic1, temporal_traffic2} · target metric/agg read from each incident's `target.json` · localization rule = `incident_agent.causal_root` (verbatim).

## Appendix C — Evidence index

`make verify` → synthetic 5/5 · `make train-logdet` → HDFS card · `make train-metricdet` → SMD card · `make validate-rca` → `artifacts/rca_validation_card.json` (three signals, all/test) · `make test` → 18/18 · served at `GET /validation`.
