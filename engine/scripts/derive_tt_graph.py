"""Derive a verified Train Ticket call graph from RCAEval RE2-TT traces.

TT is graph-free in RE1 (no verified topology). RE2-TT ships per-case ``traces.csv``
with (spanID, parentSpanID, serviceName); a span's parent service is the caller and
its own service the callee, so parent_service -> child_service is a real dependency
edge. We aggregate edges across a handful of cases into a static caller->callees graph
that ``causal_root`` can use for symptom demotion — turning TT from graph-free into
topology-based. Only metrics still drive detection; the graph only orders candidates.

Streams RE2-TT.zip to a temp file, extracts a few traces.csv (not the 22 GB corpus),
builds + prints the graph, deletes the zip. Run with MODE=inspect to just dump schema.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sentinel.rca_rcaeval import TT_APP_SERVICES  # noqa: E402

import pandas as pd  # noqa: E402

URL = "https://zenodo.org/api/records/14590730/files/RE2-TT.zip/content"
N_CASES = int(os.environ.get("N_CASES", "6"))  # cases to sample for topology coverage
MODE = os.environ.get("MODE", "build")
OUT = Path(__file__).resolve().parents[1] / "artifacts" / "tt_graph_derived.py"


def fetch_traces(dest: Path, n: int) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.gettempdir()) / "RE2-TT.zip"
    if not tmp.exists() or tmp.stat().st_size < 1_000_000:
        print(f"streaming RE2-TT.zip -> {tmp} …")
        with urllib.request.urlopen(URL, timeout=900) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f, length=1 << 20)
        print(f"  {tmp.stat().st_size / 1e6:.0f} MB")
    z = zipfile.ZipFile(tmp)
    members = [m for m in z.namelist() if m.endswith("traces.csv")]
    # spread the sample across distinct fault types for better path coverage
    picked, seen = [], set()
    for m in sorted(members):
        fault = m.split("/")[-4].rsplit("_", 1)[-1] if len(m.split("/")) >= 4 else ""
        key = fault if fault not in seen else None
        if key is not None or len(picked) < n:
            picked.append(m)
            seen.add(fault)
        if len(picked) >= n:
            break
    out = []
    for m in picked:
        p = dest / m.replace("/", "__")
        with z.open(m) as src, open(p, "wb") as f:
            shutil.copyfileobj(src, f)
        out.append(p)
    z.close()
    print(f"extracted {len(out)} traces.csv; keeping zip for reuse at {tmp}")
    return out


def build_graph(files: list[Path]) -> tuple[dict, Counter, set]:
    edges: Counter = Counter()
    services: set = set()
    for f in files:
        df = pd.read_csv(f, usecols=lambda c: c in {"spanID", "parentSpanID", "serviceName"})
        span_svc = dict(zip(df["spanID"], df["serviceName"]))
        services.update(df["serviceName"].dropna().unique())
        parent_svc = df["parentSpanID"].map(span_svc)  # caller service per span
        mask = parent_svc.notna() & (parent_svc != df["serviceName"])
        for a, b in zip(parent_svc[mask], df["serviceName"][mask]):  # caller -> callee
            edges[(a, b)] += 1
    graph: dict = defaultdict(list)
    for (a, b), _ in edges.most_common():
        if b not in graph[a]:
            graph[a].append(b)
    return dict(graph), edges, services


def main() -> int:
    work = Path(tempfile.gettempdir()) / "tt_traces"
    files = fetch_traces(work, N_CASES)
    if MODE == "inspect":
        df = pd.read_csv(files[0], nrows=5)
        print("columns:", list(df.columns))
        svc = pd.read_csv(files[0], usecols=["serviceName"])["serviceName"].dropna().unique()
        print(f"{len(svc)} serviceName values (sample): {sorted(svc)[:12]}")
        return 0
    graph, edges, services = build_graph(files)
    known = set(TT_APP_SERVICES)
    mapped = {s for s in services if s in known}
    print(f"trace services: {len(services)} | matching TT_APP_SERVICES: {len(mapped)}/{len(known)}")
    unknown = sorted(services - known)[:10]
    print(f"unmatched trace services (sample): {unknown}")
    print(f"edges (distinct): {len(edges)} | callers with deps: {len(graph)}")
    for a in sorted(graph)[:8]:
        print(f"  {a} -> {graph[a][:6]}{' …' if len(graph[a]) > 6 else ''}")
    # emit a committable graph module (only edges among known app services)
    clean = {a: [b for b in bs if b in known] for a, bs in graph.items() if a in known}
    clean = {a: bs for a, bs in clean.items() if bs}
    OUT.write_text(
        '"""Train Ticket call graph derived from RCAEval RE2-TT traces (parent->child spans).\n'
        f'Reproduce with scripts/derive_tt_graph.py ({len(files)} sampled cases); review before embedding."""\n'
        f"TT_DEPS_DERIVED = {clean!r}\n"
    )
    print(f"\n{len(clean)} app-service callers with edges -> artifacts/tt_graph_derived.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
