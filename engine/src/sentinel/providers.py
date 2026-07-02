"""Telemetry providers — assemble the engine's ``store`` (metrics / changes /
traces) from a data source. The incident engine operates purely on that store,
so swapping the provider swaps Demo <-> real infrastructure without touching any
detection, localization, or correlation logic.

  DATA_SOURCE=demo  -> DemoProvider       (deterministic simulator; the default)
  DATA_SOURCE=prom  -> PrometheusProvider (Prometheus query_range + Tempo + feed)

The Prometheus path uses standard OpenTelemetry/Prometheus metric conventions;
override the metric names via env if your instrumentation differs. It requires a
live stack (PROM_URL) and is therefore not exercised by the demo tests.
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request

import numpy as np

from .telemetry_sim import SERVICES, DEPS, N
from .scenarios import build as build_scenario


class DemoProvider:
    name = "demo"

    def build_store(self, scenario: str = "flag_spike"):
        return build_scenario(scenario, seed=int(os.environ.get("SENTINEL_SEED", "7")))


class PrometheusProvider:
    """Reads the last N minutes of golden signals from Prometheus and assembles
    the same store shape the simulator produces. Metric names follow common OTel
    conventions and are overridable via env vars."""

    name = "prom"

    def __init__(self, prom_url: str, tempo_url: str | None = None,
                 changes_url: str | None = None):
        self.prom = prom_url.rstrip("/")
        self.tempo = (tempo_url or "").rstrip("/") or None
        self.changes_url = changes_url or None
        self.m_requests = os.environ.get("PROM_METRIC_REQUESTS", "http_server_requests_total")
        self.m_duration = os.environ.get("PROM_METRIC_DURATION_BUCKET",
                                         "http_server_request_duration_seconds_bucket")
        self.label_service = os.environ.get("PROM_LABEL_SERVICE", "service")
        self.label_status = os.environ.get("PROM_LABEL_STATUS", "status_code")

    def _query_range(self, query: str) -> list[float]:
        end = int(time.time())
        start = end - N * 60
        qs = urllib.parse.urlencode(
            {"query": query, "start": start, "end": end, "step": 60}
        )
        url = f"{self.prom}/api/v1/query_range?{qs}"
        with urllib.request.urlopen(url, timeout=10) as r:  # noqa: S310 (trusted infra URL)
            payload = json.load(r)
        result = payload.get("data", {}).get("result", [])
        vals = np.zeros(N)
        if result:
            # take the first series; align its samples onto the N-minute grid
            series = {int((ts - start) // 60): float(v) for ts, v in result[0]["values"]}
            for i in range(N):
                vals[i] = series.get(i, series.get(i - 1, 0.0))
        return vals.tolist()

    def build_store(self, scenario: str = "flag_spike"):
        # scenario is a demo-only concept; real telemetry is whatever Prometheus has.
        svc, sts = self.label_service, self.label_status
        metrics = {}
        for s in SERVICES:
            err = self._query_range(
                f'sum(rate({self.m_requests}{{{svc}="{s}",{sts}=~"5.."}}[1m]))'
                f' / clamp_min(sum(rate({self.m_requests}{{{svc}="{s}"}}[1m])), 1e-9)'
            )
            p95 = self._query_range(
                f'histogram_quantile(0.95, sum(rate({self.m_duration}{{{svc}="{s}"}}[1m])) by (le)) * 1000'
            )
            rps = self._query_range(f'sum(rate({self.m_requests}{{{svc}="{s}"}}[1m]))')
            metrics[s] = {
                "error_rate": np.array(err),
                "latency_p95": np.array(p95),
                "rps": np.array(rps),
            }
        return {"metrics": metrics, "changes": self._changes(), "traces": self._traces()}

    def _changes(self):
        """Deploy/flag events from a change feed (deploy webhook or Prometheus
        annotations). Expected JSON: [{"t": <minute>, "service": ..., "change": ...}]."""
        if not self.changes_url:
            return []
        try:
            with urllib.request.urlopen(self.changes_url, timeout=10) as r:  # noqa: S310
                return json.load(r)
        except Exception:
            return []

    def _traces(self):
        """Failing traces from Tempo search; empty if Tempo is not configured
        (the engine degrades gracefully — it just omits the failing-span line)."""
        if not self.tempo:
            return []
        try:
            url = f"{self.tempo}/api/search?tags=" + urllib.parse.quote("status=error")
            with urllib.request.urlopen(url, timeout=10) as r:  # noqa: S310
                data = json.load(r)
            out = []
            for tr in data.get("traces", [])[:5]:
                out.append({
                    "trace_id": tr.get("traceID", "?"),
                    "root": tr.get("rootServiceName", "?"),
                    "error_span": tr.get("rootTraceName", "?"),
                    "status": "ERROR",
                    "t": N - 1,
                })
            return out
        except Exception:
            return []


def get_provider():
    if os.environ.get("DATA_SOURCE", "demo").lower() == "prom":
        prom = os.environ.get("PROM_URL")
        if not prom:
            raise RuntimeError("DATA_SOURCE=prom requires PROM_URL")
        return PrometheusProvider(
            prom,
            tempo_url=os.environ.get("TEMPO_URL"),
            changes_url=os.environ.get("CHANGES_URL"),
        )
    return DemoProvider()
