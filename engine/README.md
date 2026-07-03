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

## Detection may be learned; causal reasoning stays deterministic
Sentinel draws a hard line. **Localization and change correlation are rule-based graph analysis** — inspectable
and replayable, no model weights involved. **Only the detection layer may learn.** A logistic **log-anomaly
detector** trained on the real, public [`logfit-project/HDFS_v1`](https://huggingface.co/datasets/logfit-project/HDFS_v1)
corpus scores whether a log session is anomalous:

| metric (held-out) | precision | recall | F1 | ROC-AUC |
|---|---|---|---|---|
| bag-of-events · logistic | **0.992** | **0.564** | **0.719** | **0.787** |

_108,047 sessions (1 shard, 4.95% anomaly), 32,415 held-out._ High precision, modest recall — bag-of-events
discards intra-session order (sequence models score higher on complete sessions). Reproduce and read the full
model card:
```bash
make install-ml && make train-logdet   # SHARDS=5 for the full corpus
```
→ `docs/LOG_ANOMALY.md` · `GET /log-anomaly` returns the live card. The detector produces a scalar probability
only; it never sees the topology, picks a root, or ranks changes.

A second detector covers the **metric** modality: a PCA reconstruction detector trained unsupervised on the real
[Server Machine Dataset](https://github.com/NetManAIOps/OmniAnomaly) (SMD), 28 machines / 708k labelled points:

| metric (held-out, train-only threshold) | precision | recall | F1 | F1 (point-adjusted) |
|---|---|---|---|---|
| PCA reconstruction-error | **0.142** | **0.403** | **0.210** | **0.350** |

Deliberately conservative: SMD papers report point-adjusted F1 with a *test-selected* threshold (0.8–0.9); ours
never touches test labels to set the cut. `make train-metricdet` · `docs/METRIC_ANOMALY.md` · `GET /metric-anomaly`.
Both detectors are composed into `GET /validation` and the console's Validation panel.

## The deterministic localizer, validated on real incidents
The causal rule isn't just asserted — it's scored against a real labelled RCA corpus, the public
[PetShop dataset](https://github.com/amazon-science/petshop-root-cause-analysis). The **same**
`causal_root` function that runs live is applied to 68 real incidents; recall@1 = the engine's single answer.

| corpus | incidents | recall@1 | recall@3 |
|---|---:|---:|---:|
| PetShop (all) | 68 | **0.265** | **0.471** |

Honest and untuned — PetShop is a hard benchmark, and the harness also documents *why* it misses (a ~29%
detection gap; service-vs-node granularity, so recall@3 ≈ 2× recall@1). Reproduce with `make validate-rca`;
`GET /rca-validation` serves the card; full method + failure modes in `docs/RCA_VALIDATION.md`. **No
localization logic is modified or tuned to the benchmark** — only the "elevated" signal is re-expressed for
PetShop's latency metric.

## Quickstart
```bash
make install
make test      # 16 passed — detect/localize/root-cause + two learned detectors + RCA harness (offline)
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
