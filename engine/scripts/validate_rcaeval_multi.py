"""Score Sentinel's metrics-only causal rule on RCAEval's RE2 / RE3 (multi-source) tiers.

Framing (A), stated up front: RE2/RE3 ship logs + traces that multi-source baselines
exploit; the verbatim ``causal_root`` rule consumes **only the metrics channel**
(``data.csv``), unchanged from RE1. We report how far a *metrics-only* inspectable rule
gets on the harder tier — and any baseline comparison is restricted to **metric-based**
methods (never trace/multi-source ones), so the comparison is signal-fair.

    TIER=RE2 python scripts/validate_rcaeval_multi.py     # default: RE2, all 3 systems
    TIER=RE3 python scripts/validate_rcaeval_multi.py

Outputs (git-ignored): artifacts/rcaeval/{RE2,RE3}-*/… corpus + artifacts/rcaeval_<tier>_card.json
"""
from __future__ import annotations

import io
import json
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sentinel.rca_rcaeval import FAULTS, SYSTEM_DEPS, evaluate_system  # noqa: E402

ZENODO = "https://zenodo.org/api/records/14590730/files/{name}.zip/content"
ART = Path(__file__).resolve().parents[1] / "artifacts"
CACHE = ART / "rcaeval"
TIER = os.environ.get("TIER", "RE2").upper()
# Fault sets differ by tier; RE2 adds socket, RE3 is code-level f1..f5.
TIER_FAULTS = {
    "RE2": FAULTS + ("socket",),
    "RE3": ("f1", "f2", "f3", "f4", "f5"),
}
SYSTEMS = {"OB": f"{TIER}-OB", "SS": f"{TIER}-SS", "TT": f"{TIER}-TT"}


def ensure(archive: str) -> str:
    out = CACHE / archive
    if not out.exists():
        print(f"downloading {archive}… (multi-source zip — larger than RE1)")
        data = urllib.request.urlopen(ZENODO.format(name=archive), timeout=600).read()
        zipfile.ZipFile(io.BytesIO(data)).extractall(out)
        print(f"  {len(data) / 1e6:.1f} MB")
    inner = out / archive
    return str(inner if inner.is_dir() else out)


def main() -> int:
    if TIER not in TIER_FAULTS:
        sys.exit(f"TIER must be RE2 or RE3 (got {TIER})")
    faults = TIER_FAULTS[TIER]
    CACHE.mkdir(parents=True, exist_ok=True)
    print(f"RCAEval {TIER} (multi-source) · Sentinel metrics-only causal_root · faults={faults}\n")
    card = {
        "benchmark": "RCAEval (Pham et al., TheWebConf 2025; DOI 10.1145/3701716.3715290)",
        "tier": f"{TIER} (multi-source: metrics+logs+traces)",
        "framing": ("Framing A — Sentinel consumes ONLY the metrics channel (data.csv), rule "
                    "unchanged from RE1; logs/traces are not used. Comparisons (elsewhere) are "
                    "restricted to metric-based baselines. Not a claim over trace/multi-source methods."),
        "systems": {},
    }
    agg = {"n": 0, "h1": 0, "h3": 0, "avg5_sum": 0.0}
    for code, archive in SYSTEMS.items():
        root = ensure(archive)
        # archives may nest one level (archive/archive/cases…)
        inner = os.path.join(root, archive)
        sysdir = inner if os.path.isdir(inner) else root
        best = None
        entry = {}
        for signal in ("within_domain", "within_domain_selective"):
            ev = evaluate_system(sysdir, code, signal=signal, faults=faults)
            row = {"n": ev.n, "ac_1": round(ev.ac(1), 3), "ac_3": round(ev.ac(3), 3),
                   "avg_5": round(ev.avg5, 3), "coverage": round(ev.detected / ev.n, 3) if ev.n else 0.0}
            entry["broad" if signal == "within_domain" else "selective"] = row
            if best is None or row["ac_1"] > best[1]:
                best = (signal, row["ac_1"], ev)
        card["systems"][code] = entry
        ev = best[2]
        agg["n"] += ev.n
        agg["h1"] += ev.hits[1]
        agg["h3"] += ev.hits[3]
        agg["avg5_sum"] += sum(ev.hits[k] for k in range(1, 6)) / 5
        print(f"{code}: broad AC@1 {entry['broad']['ac_1']} · selective AC@1 {entry['selective']['ac_1']} "
              f"· best-Avg@5 {max(entry['broad']['avg_5'], entry['selective']['avg_5'])} (n={ev.n})")
    if agg["n"]:
        card["aggregate_best_signal"] = {
            "cases": agg["n"], "ac_1": round(agg["h1"] / agg["n"], 3),
            "ac_3": round(agg["h3"] / agg["n"], 3), "avg_5": round(agg["avg5_sum"] / agg["n"], 3),
        }
        a = card["aggregate_best_signal"]
        print(f"\naggregate ({a['cases']} cases, best signal/system): "
              f"AC@1 {a['ac_1']} · AC@3 {a['ac_3']} · Avg@5 {a['avg_5']}")
    (ART / f"rcaeval_{TIER.lower()}_card.json").write_text(json.dumps(card, indent=2))
    print(f"card -> artifacts/rcaeval_{TIER.lower()}_card.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
