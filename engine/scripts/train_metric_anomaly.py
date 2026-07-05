"""Train and evaluate the metric-anomaly detector on the real public SMD corpus.

Downloads the Server Machine Dataset (NetManAIOps/OmniAnomaly), fits a PCA
reconstruction detector on each machine's anomaly-free training window, scores
its labelled test window, and reports point-wise precision / recall / F1 (plus
the SMD-standard point-adjusted F1) pooled across machines.

    make install-ml && make train-metricdet          # default machine subset
    MACHINES=all make train-metricdet                # full 28-machine corpus

Outputs (git-ignored — reproducible, not committed):
    artifacts/smd/…                       the downloaded corpus
    artifacts/metric_anomaly_card.json    the measured model card

Threshold comes from the training error distribution only — test labels are used
solely to score. Config is fixed a priori (see docs/METRIC_ANOMALY.md); it is
not selected to maximise test F1.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
from sklearn.isotonic import IsotonicRegression  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402

from sentinel.calibration import calibration_report  # noqa: E402
from sentinel.metric_anomaly import (  # noqa: E402
    QUANTILE_DEFAULT,
    SMOOTH_DEFAULT,
    VAR_DEFAULT,
    MetricAnomalyDetector,
    point_adjust,
    prf,
)

BASE = "https://raw.githubusercontent.com/NetManAIOps/OmniAnomaly/master/ServerMachineDataset"
ART = Path(__file__).resolve().parents[1] / "artifacts"
SMD = ART / "smd"
ALL = ([f"machine-1-{i}" for i in range(1, 9)]
       + [f"machine-2-{i}" for i in range(1, 10)]
       + [f"machine-3-{i}" for i in range(1, 12)])


def machines() -> list[str]:
    # Default to the full corpus so the committed number is subset-free.
    # MACHINES=machine-1-1,machine-2-1 runs a quick subset.
    env = os.environ.get("MACHINES", "").strip()
    if env and env != "all":
        return env.split(",")
    return ALL


def fetch(sub: str, m: str) -> str:
    SMD.mkdir(parents=True, exist_ok=True)
    p = SMD / f"{sub}_{m}.txt"
    if not p.exists():
        urllib.request.urlretrieve(f"{BASE}/{sub}/{m}.txt", p)
    return str(p)


def main() -> int:
    t0 = time.time()
    ms = machines()
    print(f"SMD metric-anomaly · {len(ms)} machine(s) · PCA(var={VAR_DEFAULT}) "
          f"smooth={SMOOTH_DEFAULT} thr=train-q{QUANTILE_DEFAULT}\n")

    preds, labels, escores = [], [], []
    for m in ms:
        train = np.loadtxt(fetch("train", m), delimiter=",")
        test = np.loadtxt(fetch("test", m), delimiter=",")
        label = np.loadtxt(fetch("test_label", m)).astype(int)
        det = MetricAnomalyDetector().fit(train)
        preds.append(det.predict(test))
        labels.append(label)
        escores.append(det.score(test) / det.threshold)  # error / train threshold (1.0 at boundary)

    pred = np.concatenate(preds)
    label = np.concatenate(labels)
    p, r, f = prf(pred, label)
    _, _, paf = prf(point_adjust(pred, label), label)

    # Calibration: unlike the log detector, this model emits a reconstruction ERROR,
    # not a probability. Read its own decision boundary as a pseudo-probability
    # p = e/(1+e), e = error/threshold (p = 0.5 exactly at the threshold), measure its
    # calibration, then test whether isotonic recalibration (error/threshold -> label,
    # fit on a disjoint half of the pooled test points) helps.
    e = np.concatenate(escores)
    e_fit, e_eval, y_fit, y_eval = train_test_split(
        e, label, test_size=0.50, random_state=42, stratify=label
    )
    iso = IsotonicRegression(out_of_bounds="clip").fit(e_fit, y_fit)
    raw = calibration_report(y_eval, e_eval / (1.0 + e_eval))
    isot = calibration_report(y_eval, iso.predict(e_eval))

    card = {
        "dataset": "NetManAIOps/OmniAnomaly · Server Machine Dataset (SMD)",
        "model": "PCA reconstruction-error (unsupervised)",
        "machines": len(ms),
        "test_points": int(len(label)),
        "anomaly_rate": round(float(label.mean()), 4),
        "config": f"PCA var={VAR_DEFAULT}, smooth={SMOOTH_DEFAULT}, threshold=train q{QUANTILE_DEFAULT}",
        "metrics": {
            "precision": round(p, 3),
            "recall": round(r, 3),
            "f1": round(f, 3),
            "f1_point_adjusted": round(paf, 3),
        },
        "calibration": {
            "starts_from": ("PCA reconstruction error (not a probability); pseudo-prob "
                            "p = e/(1+e), e = smoothed error / train threshold (0.5 at the boundary)"),
            "eval_n": int(len(y_eval)),
            "raw_pseudo_prob": raw,
            "after_isotonic": isot,
            "note": ("isotonic (error/threshold -> label) fit on a disjoint half of the "
                     "pooled test points, evaluated on the other half"),
        },
        "caveats": [
            "Unsupervised: threshold set from the training error distribution, "
            "never from test labels — no best-F1-on-test selection.",
            "SMD papers report point-adjusted F1 with a test-selected threshold "
            "(0.8-0.9); this honest train-only setting is far more conservative.",
            "Detection layer only — standalone real-data capability; not wired "
            "into the causal engine.",
        ],
    }
    ART.mkdir(exist_ok=True)
    (ART / "metric_anomaly_card.json").write_text(json.dumps(card, indent=2))

    mt = card["metrics"]
    print(f"POOLED ({card['test_points']:,} points, {card['anomaly_rate']*100:.1f}% anomalous):")
    print(f"  precision {mt['precision']} · recall {mt['recall']} · F1 {mt['f1']} "
          f"· point-adjusted F1 {mt['f1_point_adjusted']}")
    cal = card["calibration"]
    print(f"CALIBRATION (pseudo-prob from recon-error): raw ECE {cal['raw_pseudo_prob']['ece']} "
          f"· Brier {cal['raw_pseudo_prob']['brier']} -> isotonic ECE {cal['after_isotonic']['ece']} "
          f"· Brier {cal['after_isotonic']['brier']}")
    print(f"  card -> artifacts/metric_anomaly_card.json · {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
