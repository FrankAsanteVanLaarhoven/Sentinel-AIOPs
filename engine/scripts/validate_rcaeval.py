"""Score Sentinel's deterministic causal rule on the public RCAEval benchmark.

Downloads RCAEval RE1 system archives (metrics-only tier) from Zenodo, runs the
verbatim `causal_root` rule over every case, and reports Top-1 / Top-3 / coverage
against the ground-truth root-cause service (encoded in each case directory name).

    make validate-rcaeval            # Online Boutique (RE1-OB)

Outputs (git-ignored — reproducible, not committed):
    artifacts/rcaeval/RE1-*/…        the downloaded corpus
    artifacts/rcaeval_card.json      the measured result card

No localization logic is modified or tuned. The elevated signal (z>=3, within-
domain) is the same one used for PetShop, fixed a priori — not swept on RCAEval.
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

from sentinel.rca_rcaeval import SYSTEM_DEPS, evaluate_system  # noqa: E402

ZENODO = "https://zenodo.org/api/records/14590730/files/{name}.zip/content"
ART = Path(__file__).resolve().parents[1] / "artifacts"
CACHE = ART / "rcaeval"
# RE1 (metrics-only) systems we have topology graphs for.
SYSTEMS = {"OB": "RE1-OB"}


def ensure(system_code: str, archive: str) -> str:
    out = CACHE / archive
    if not out.exists():
        print(f"downloading {archive}…")
        data = urllib.request.urlopen(ZENODO.format(name=archive), timeout=300).read()
        zipfile.ZipFile(io.BytesIO(data)).extractall(out)
        print(f"  {len(data) / 1e6:.1f} MB")
    # archives unzip to <archive>/<archive>/<cases…>
    inner = out / archive
    return str(inner if inner.is_dir() else out)


def main() -> int:
    CACHE.mkdir(parents=True, exist_ok=True)
    print("RCAEval RE1 localization · causal_root rule (reused verbatim) · z>=3\n")
    card = {
        "benchmark": "RCAEval (Pham et al., TheWebConf 2025; DOI 10.1145/3701716.3715290)",
        "tier": "RE1 (metrics-only)",
        "rule": "causal_root — deterministic, reused verbatim, not tuned",
        "metric_def": "Top-k = ground-truth root-cause service is within the top-k ranked candidates; coverage = fraction of cases with any candidate.",
        "signal_note": "within-domain elevated signal (z>=3), same as PetShop, fixed a priori.",
        "systems": {},
        "scope": "Online Boutique (RE1-OB, 125 cases) measured; Sock Shop / Train Ticket (RE1-SS/TT) and RE2/RE3 not yet included; no baseline comparison claimed yet.",
    }
    for code, archive in SYSTEMS.items():
        if code not in SYSTEM_DEPS:
            continue
        sysdir = ensure(code, archive)
        print(f"=== {archive} ({code}) ===")
        print(f"{'signal':26}{'n':>5}{'Top-1':>8}{'Top-3':>8}{'cov':>8}")
        sys_card = {}
        for sig in ("within_domain", "within_domain_selective"):
            e = evaluate_system(sysdir, system=code, signal=sig)
            print(f"{sig:26}{e.n:>5}{e.top1/e.n:>8.3f}{e.top3/e.n:>8.3f}{e.detected/e.n:>8.3f}")
            sys_card[sig] = {
                "n": e.n,
                "top_1": round(e.top1 / e.n, 3),
                "top_3": round(e.top3 / e.n, 3),
                "coverage": round(e.detected / e.n, 3),
                "per_fault_top_1": {f: round(d["top1"] / d["n"], 3) for f, d in sorted(e.per_fault.items())},
            }
        card["systems"][code] = sys_card
        print()
    (ART / "rcaeval_card.json").write_text(json.dumps(card, indent=2))
    print("card -> artifacts/rcaeval_card.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
