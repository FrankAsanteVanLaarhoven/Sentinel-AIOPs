"""Validate deterministic causal localization against the real PetShop RCA corpus.

Downloads the public Amazon-Science PetShop dataset, runs Sentinel's own causal
rule (``incident_agent.causal_root``, reused verbatim) over every labelled
incident, and reports recall@1 / recall@3 against the ground-truth root service.

    make install-ml && make validate-rca

Outputs (git-ignored — reproducible, not committed):
    artifacts/petshop/…                the downloaded corpus
    artifacts/rca_validation_card.json the measured result card

No localization logic is modified or tuned. The only domain adaptation is the
"elevated" signal (a fixed z>=3 test on the incident's target metric); it is not
swept to fit the benchmark — see docs/RCA_VALIDATION.md.
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sentinel.rca_petshop import Z_DEFAULT, evaluate_dir  # noqa: E402

ZIP_URL = "https://github.com/amazon-science/petshop-root-cause-analysis/archive/refs/heads/main.zip"
ART = Path(__file__).resolve().parents[1] / "artifacts"
CACHE = ART / "petshop"


def dataset_dir() -> str:
    if not CACHE.exists():
        print("downloading PetShop corpus…")
        t = time.time()
        data = urllib.request.urlopen(ZIP_URL, timeout=90).read()
        zipfile.ZipFile(io.BytesIO(data)).extractall(CACHE)
        print(f"  {len(data) / 1e6:.1f} MB in {time.time() - t:.1f}s")
    root = next(CACHE.iterdir())
    return str(root / "dataset")


def main() -> int:
    ds = dataset_dir()
    z = float(os.environ.get("Z_THRESHOLD", Z_DEFAULT))
    print(f"PetShop localization validation · z>={z} · causal_root rule (reused verbatim)\n")

    full = evaluate_dir(ds, z_thr=z, splits=("train", "test"), signal="target")
    test = evaluate_dir(ds, z_thr=z, splits=("test",), signal="target")
    within = evaluate_dir(ds, z_thr=z, splits=("train", "test"), signal="within_domain")

    print(f"{'scenario':20} {'n':>4} {'recall@1':>9} {'recall@3':>9}")
    print("-" * 46)
    for sc, s in full.per_scenario.items():
        print(f"{sc:20} {s['n']:>4} {s['hit1'] / s['n']:>9.3f} {s['hit3'] / s['n']:>9.3f}")
    print("-" * 46)
    print(f"{'ALL (train+test)':20} {full.n:>4} {full.hit1 / full.n:>9.3f} {full.hit3 / full.n:>9.3f}")
    print(f"{'test split only':20} {test.n:>4} {test.hit1 / test.n:>9.3f} {test.hit3 / test.n:>9.3f}")
    print(f"\ndetection coverage (some node flagged): {full.detected / full.n:.3f}")

    def _line(name, ev):
        return (f"  {name:30} recall@1={ev.hit1/ev.n:.3f}  recall@3={ev.hit3/ev.n:.3f}  "
                f"coverage={ev.detected/ev.n:.3f}")
    print("\nelevated-signal trade-off (same causal_root rule, only the detection signal changes):")
    print(_line("target metric (default)", full))
    print(_line("within-domain (all metrics)", within))
    print("  -> within-domain closes the coverage gap; the larger elevated set costs localization precision.")

    card = {
        "dataset": "amazon-science/petshop-root-cause-analysis",
        "rule": "causal_root (elevated service with no elevated dependency) — reused verbatim",
        "elevated_signal": f"z>={z} vs no-issue baseline on the incident's target metric (window mean)",
        "incidents": full.n,
        "recall_at_1": round(full.hit1 / full.n, 3),
        "recall_at_3": round(full.hit3 / full.n, 3),
        "detection_coverage": round(full.detected / full.n, 3),
        "within_domain": {
            "elevated_signal": "all metrics per node, two-sided |z| >= z_thr (within-domain detection)",
            "recall_at_1": round(within.hit1 / within.n, 3),
            "recall_at_3": round(within.hit3 / within.n, 3),
            "detection_coverage": round(within.detected / within.n, 3),
            "note": "Closes the coverage gap on PetShop's own signals; the larger elevated set trades ~6pt recall@1 (detection<->localization tension).",
        },
        "test_split": {
            "incidents": test.n,
            "recall_at_1": round(test.hit1 / test.n, 3),
            "recall_at_3": round(test.hit3 / test.n, 3),
        },
        "failure_modes": [
            "Detection gap (target signal): ~29% of incidents show no node above "
            "z>=3 on the target metric. The within-domain signal (all metrics, two-"
            "sided) closes most of it (coverage ~0.97) at the cost of localization precision.",
            "Node granularity: PetShop splits one logical service into several nodes "
            "(…_AWS::Lambda, …::Function, the API Gateway stage); the rule may pick a "
            "co-elevated sibling, so recall@3 (>recall@1) better reflects the region found.",
            "Dense co-elevation: real AWS graphs elevate many nodes at once, so "
            "'no elevated dependency' admits several candidates.",
        ],
        "boundary": "Localization rule is deterministic and unchanged; only the elevated signal is adapted, and it is not tuned to the benchmark.",
    }
    ART.mkdir(exist_ok=True)
    (ART / "rca_validation_card.json").write_text(json.dumps(card, indent=2))
    print(f"  card -> artifacts/rca_validation_card.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
