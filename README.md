# Sentinel-AIOPs

Honest, human-gated AIOps: an OpenTelemetry-native **incident engine** that
detects an SLO breach, **causally localizes** it (root vs symptom), finds the
root-cause change, and *proposes* a fix behind a human gate — and a dense,
real-time **console** that renders it in a Palantir/Tesla "velvet" aesthetic.

```
Sentinel-AIOPs/
├─ engine/    Python · FastAPI · the incident engine (detect → localize → correlate) + HTTP API
└─ console/   Next.js 16 · the observability dashboard (BFF proxying the engine)
```

## Why it's different
Beyond parity with modern AI-RCA dashboards, three differentiators — shown, not asserted:
1. **Causal service topology** — root pulses `crit`, symptoms `warn`; error edges animate.
2. **Change-correlation ranking** — the true cause ranked #1 by the engine's score
   (service-match × onset-proximity), with the *naive recency rank* shown beside it.
3. **Honest, human-gated investigation** — stepped timeline with method, confidence,
   and failure modes, and an explicit **Approve / Dismiss** gate. It proposes; it never acts.

Root identification is **error-propagation graph analysis — not formal causal
inference**, and the UI says so. No panel shows invented numbers; demo data is labelled **DEMO**.

## Quick start (two processes)
```bash
# 1 · engine  → http://127.0.0.1:8008
cd engine && pip install -r requirements.txt
PYTHONPATH=src DATA_SOURCE=demo uvicorn sentinel.api.engine_api:app --port 8008 --reload

# 2 · console → http://localhost:3000
cd console && npm install && npm run dev
```
Or from `console/`: `./scripts/dev.sh` starts both.

## Demo scenarios
The console's scenario selector (deep-link `?scenario=<id>`) drives the whole board;
each localizes to a documented ground-truth root:

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

See `engine/README.md` and `console/README.md` for details.
