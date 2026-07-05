"""Measure the effect of the RE2-derived Train Ticket call graph on `causal_root`.

TT runs graph-free by default. This scores TT with the graph-free candidate set vs the
verified topology derived from RE2-TT traces (`TT_DEPS_DERIVED`, symptom demotion on),
on RE1-TT and RE2-TT. It reproduces the measured trade-off: the graph helps RE2-TT AC@1
but degrades the RE1-TT headline (two injected roots — ts-order, ts-travel — are mid-tier
callers whose downstream deps co-elevate and get the true root wrongly demoted). Hence
graph-free stays the default. Needs the RE1-TT / RE2-TT corpora already downloaded.

    make tt-graph-delta
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import sentinel.rca_rcaeval as R  # noqa: E402
from sentinel.rca_rcaeval import FAULTS, TT_APP_SERVICES, TT_DEPS_DERIVED, evaluate_system  # noqa: E402

ART = Path(__file__).resolve().parents[1] / "artifacts" / "rcaeval"
GRAPH_FREE = {s: [] for s in TT_APP_SERVICES}
DERIVED = {**GRAPH_FREE, **TT_DEPS_DERIVED}


def _case_dir(*cands: str) -> str | None:
    for c in cands:
        if os.path.isdir(c) and any("_" in x and os.path.isdir(os.path.join(c, x)) for x in os.listdir(c)):
            return c
    return None


def best(sysdir: str, faults: tuple, deps: dict) -> tuple[float, float, float, int]:
    R.SYSTEM_DEPS["TT"] = deps
    top = None
    for sig in ("within_domain", "within_domain_selective"):
        ev = evaluate_system(sysdir, "TT", signal=sig, faults=faults)
        if top is None or ev.ac(1) > top[0]:
            top = (ev.ac(1), ev.ac(3), ev.avg5, ev.n)
    return top


def main() -> int:
    print("Train Ticket · graph-free (default) vs RE2-derived call graph · best signal per row\n")
    print(f"{'tier':9}{'variant':16}{'AC@1':>8}{'AC@3':>8}{'Avg@5':>8}{'n':>6}")
    rows = [
        ("RE1-TT", _case_dir(str(ART / "RE1-TT" / "RE1-TT"), str(ART / "RE1-TT")), FAULTS),
        ("RE2-TT", _case_dir(str(ART / "RE2-TT" / "RE2-TT"), str(ART / "RE2-TT")), FAULTS + ("socket",)),
    ]
    for tier, d, faults in rows:
        if not d:
            print(f"{tier}: corpus not found (run the RE1/RE2 harness first)")
            continue
        gf = best(d, faults, GRAPH_FREE)
        gr = best(d, faults, DERIVED)
        for name, r in (("graph-free", gf), ("derived-graph", gr)):
            print(f"{tier:9}{name:16}{r[0]:>8.3f}{r[1]:>8.3f}{r[2]:>8.3f}{r[3]:>6}")
        print(f"{'':9}{'Δ AC@1':16}{gr[0] - gf[0]:>+8.3f}   (derived − graph-free)\n")
    print("Finding: graph helps RE2-TT AC@1, degrades RE1-TT → graph-free retained as default.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
