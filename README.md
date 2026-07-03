# Sentinel-AIOPs

**An honest, measurable AIOps system** built around a strict separation between *learned detection* and
*deterministic causal reasoning*. It detects an SLO breach, **causally localizes** it (root vs symptom), finds
the root-cause change, and *proposes* a fix **behind a human gate** — and renders it all in a dense, real-time
console. Every performance number comes from a real public dataset; trade-offs are **quantified, not hidden**.

```
Sentinel-AIOPs/
├─ engine/       Python · FastAPI · incident engine (detect → localize → correlate) + HTTP API
├─ console/      Next.js 16 · observability dashboard (BFF proxying the engine)
├─ docs/         MANUSCRIPT.md — the full technical report
└─ notebooks/    Sentinel_AIOPs_Grandmaster.ipynb — end-to-end reproduction
```

## The three-layer contract

1. **Detection (learned).** Statistical models on real public data may supply an anomaly signal:
   - **Logs** — anomaly detection on HDFS (`logfit-project/HDFS_v1`)
   - **Metrics** — PCA reconstruction on server metrics (NetManAIOps **SMD**)
2. **Localization (deterministic).** Root-service identification via error-propagation graph analysis
   (`causal_root`). **Never trained.** Fully inspectable and replayable — no model weights.
3. **Validation (empirical).** The deterministic rule is scored against the public **PetShop** RCA corpus,
   with detection coverage and localization precision **measured**, and their trade-off documented.

A single queryable interface — **`GET /validation`** — surfaces all three from committed cards, without
running any pipeline.

## Current baseline (commit `880880f`)

| Component | Status |
|---|---|
| Deterministic causal core (`causal_root`) | Untouched & reproducible · suite **17/17** green |
| Detection layer | **2** learned detectors on real public datasets |
| PetShop validation | recall@1 **0.265** / recall@3 **0.471**; within-domain **coverage 0.706 → 0.971** *(costs ~6 pts recall@1 — trade-off measured)* |
| Three-layer query interface | Live (`GET /validation`) |
| Documentation & notebook | Full manuscript + runnable notebook |

## Measured, on real public data

| Layer | Component | Dataset | Headline (held-out) |
|---|---|---|---|
| Detection (learned) | Log detector | HDFS | **F1 0.719** (P 0.992 · R 0.564 · AUC 0.787) |
| Detection (learned) | Metric detector | SMD | **F1 0.210** / PA-F1 0.35 *(honest train-only threshold)* |
| Localization (deterministic) | `causal_root` | synthetic | **5/5** ground-truth agreement |
| Validation (empirical) | `causal_root` | PetShop | **recall@1 0.265** / recall@3 0.471 · coverage 0.706 (→ 0.971 within-domain) |

No invented numbers; no cross-domain transfer is claimed (the detectors are standalone real-data capabilities).
The within-domain result closes the coverage gap **but** costs localization precision — reported as a
trade-off, not a win.

## Why the console is different
Beyond parity with modern AI-RCA dashboards, three differentiators — shown, not asserted:
1. **Causal service topology** — root pulses `crit`, symptoms `warn`; error edges animate.
2. **Change-correlation ranking** — the true cause ranked #1 by the engine's score
   (service-match × onset-proximity), with the *naive recency rank* shown beside it.
3. **Honest, human-gated investigation** — stepped timeline with method, confidence, and failure modes, and an
   explicit **Approve / Dismiss** gate. It proposes; it never acts.

## Getting started
```bash
# 1 · engine  → http://127.0.0.1:8008
cd engine && pip install -r requirements.txt && make serve

# 2 · console → http://localhost:3000
cd console && npm install && npm run dev
```
Or from `console/`: `./scripts/dev.sh` starts both.

## Reproduce the numbers
```bash
cd engine && pip install -r requirements-ml.txt
make verify          # 5/5 synthetic scenarios at 100% ground truth
make train-logdet    # HDFS log detector   → P 0.992 / R 0.564 / F1 0.719 / AUC 0.787
make train-metricdet # SMD metric detector → P 0.142 / R 0.403 / F1 0.210 / PA-F1 0.35
make validate-rca    # PetShop localization + within-domain trade-off (target vs all-metrics signal)
make test            # 17/17 hermetic tests (offline)
```
Corpora and trained weights are git-ignored and regenerated from source; the repo commits only the
reproducible pipeline.

## Demo scenarios
The console's scenario selector (deep-link `?scenario=<id>`) drives the whole board; each localizes to a
documented ground-truth root:

| id | root | shows |
|---|---|---|
| `flag_spike` | productcatalog | textbook propagation (MTTD 1m) |
| `gradual` | payment | slow burn, later detection (MTTD 2m) |
| `shared_infra` | productcatalog | wide blast radius |
| `symptom_louder` | productcatalog | a symptom louder than the root (confidence drops) |
| `noisy_multi_change` | payment | correlation picks the right change among four |

## Swap Demo → Prometheus
Point the engine at a live stack; the console needs no changes:
```bash
cd engine && DATA_SOURCE=prom PROM_URL=http://prometheus:9090 \
  TEMPO_URL=http://tempo:3200 uvicorn sentinel.api.engine_api:app --port 8008
```

## Learn more
- **[docs/MANUSCRIPT.md](docs/MANUSCRIPT.md)** — full technical report: hypotheses, methods, datasets & ground
  truth, results, the failure/mitigation log, decisions, honesty rails, and future work.
- **[notebooks/Sentinel_AIOPs_Grandmaster.ipynb](notebooks/Sentinel_AIOPs_Grandmaster.ipynb)** — a runnable,
  Grandmaster-style walkthrough that reproduces the three-layer pipeline end to end.
- `engine/README.md` · `console/README.md` — component detail.
- Endpoint reference and model cards: `GET /validation`, `/log-anomaly`, `/metric-anomaly`, `/rca-validation`.

---

*Sentinel-AIOPs prioritizes transparency and measurement over automation. Detection may be learned on real
public data; the causal reasoning that must be trusted in production stays deterministic, inspectable, and
validated against ground truth.*
