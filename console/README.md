# Sentinel Console

Engineer-grade, real-time observability UI for the **Sentinel** incident-triage
engine — a Palantir/Tesla "velvet" dashboard that matches a modern AI-RCA
competitor panel-for-panel and beats it with three things they lack:

- **Causal service topology** — root vs symptom, coloured and animated.
- **Change-correlation ranking** — the true cause ranked #1 by the engine's
  score, with the naive *recency* rank shown beside it to make the difference
  legible.
- **Honest, human-gated investigation** — a stepped timeline that shows its
  method, confidence, and failure modes, and an explicit **Approve / Dismiss**
  gate. It proposes; it never acts.

## Honesty rails (non-negotiable)
1. **Assistive, human-gated.** No auto-remediation. Every action is gated.
2. **Method + failure modes are visible.** Root-service identification is
   *error-propagation graph analysis — not formal causal inference*, and the UI
   says so.
3. **Charts are driven by real logic.** Every panel reads the Sentinel engine;
   nothing is hard-coded. Demo data is labelled **DEMO** in the command bar.

## Architecture

```
Browser (dashboard, SSE live)
   ⇅ TanStack Query / EventSource
Next.js route handlers (BFF: /api/telemetry /stream /incident /topology /changes /panels)
   └─▶ Sentinel FastAPI engine  (real detect → localize → correlate; source of truth)
          └─ DataProvider:  DemoProvider (seeded sim)  |  PrometheusProvider (query_range) + Tempo + change feed
```

Next.js is a **backend-for-frontend**: it composes engine output and streams it
to the UI. It never re-implements detection/localization/correlation — that all
lives in the Python engine (`../engine`), which stays green (`make test`).

## Run it (two processes)

**1 · the engine** (`../engine`):
```bash
cd ../engine
pip install -r requirements.txt
PYTHONPATH=src DATA_SOURCE=demo \
  uvicorn sentinel.api.engine_api:app --port 8008 --reload
```

**2 · the console**:
```bash
npm install
npm run dev            # http://localhost:3000
```

Or start both at once: `./scripts/dev.sh`.

## Demo scenarios
The command bar's **scenario** selector drives the whole board (deep-linkable via
`?scenario=<id>`). Each exercises the engine on a different incident *shape*;
every one localizes to its documented ground-truth root:

| id | shape | ground-truth root | what it proves |
|---|---|---|---|
| `flag_spike` | step failure on a leaf | productcatalog | textbook propagation, MTTD 1m |
| `gradual` | slow error-budget burn | payment | later detection (MTTD 2m) |
| `shared_infra` | shared backend fails | productcatalog | wide blast radius |
| `symptom_louder` | a symptom louder than the root | productcatalog | **cause, not symptom** (conf drops to 70%) |
| `noisy_multi_change` | four changes near onset | payment | correlation picks the right change |

## Swap Demo → Prometheus
Point the engine at a live stack (the Console needs no changes):
```bash
cd ../engine
DATA_SOURCE=prom PROM_URL=http://prometheus:9090 \
  TEMPO_URL=http://tempo:3200 CHANGES_URL=http://…/changes \
  uvicorn sentinel.api.engine_api:app --port 8008
```
Then set `NEXT_PUBLIC_DATA_SOURCE=prom` so the command bar drops the DEMO badge.

## Environment (`.env.local`)
| var | meaning |
|---|---|
| `SENTINEL_ENGINE_URL` | engine base URL (server-side only) — default `http://127.0.0.1:8008` |
| `DATA_SOURCE` | `demo` or `prom` (mirrors the engine) |
| `NEXT_PUBLIC_DATA_SOURCE` | public mirror so the DEMO badge renders without a round-trip |

## Stack
Next.js 16 (App Router, RSC, route handlers) · TypeScript · Tailwind v4 · TanStack
Query v5 · SSE · Apache ECharts · @xyflow/react (topology) · custom SVG
(host grid + trace waterfall) · Motion.

## Deploy
Deploy the Console on Vercel (Next-native). Run the Sentinel engine as a
sidecar/service (Vercel supports FastAPI via Fluid Compute) and point
`SENTINEL_ENGINE_URL` at it; set `PROM_URL`/`TEMPO_URL` for real data.
