"""Train and evaluate the log-anomaly detector on real public HDFS logs.

Downloads the `logfit-project/HDFS_v1` corpus from Hugging Face, groups raw log
lines into per-block sessions, builds bag-of-events features from the shared
``event_template`` normaliser, fits the logistic detector, and reports
precision / recall / F1 / ROC-AUC on a held-out partition.

    make train-logdet                 # 1 shard (fast)
    SHARDS=5 make train-logdet        # full corpus

Outputs (git-ignored — reproducible, not committed):
    artifacts/log_anomaly.joblib       the trained detector
    artifacts/log_anomaly_card.json    the measured model card

Requires the ML extras: `pip install -r requirements-ml.txt`.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from huggingface_hub import hf_hub_download  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.isotonic import IsotonicRegression  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402

from sentinel.calibration import calibration_report  # noqa: E402
from sentinel.log_anomaly import LogAnomalyDetector, event_template  # noqa: E402

REPO = "logfit-project/HDFS_v1"
SHARDS = int(os.environ.get("SHARDS", "1"))
VOCAB_SIZE = int(os.environ.get("VOCAB_SIZE", "48"))
ART = Path(__file__).resolve().parents[1] / "artifacts"


def load_lines(n_shards: int) -> pd.DataFrame:
    frames = []
    for i in range(n_shards):
        fn = f"data/train-{i:05d}-of-00005.parquet"
        path = hf_hub_download(repo_id=REPO, repo_type="dataset", filename=fn)
        frames.append(pd.read_parquet(path, columns=["content", "block_id", "anomaly"]))
    return pd.concat(frames, ignore_index=True)


def main() -> int:
    t0 = time.time()
    print(f"HDFS log-anomaly training · {SHARDS} shard(s) · vocab {VOCAB_SIZE}")
    df = load_lines(SHARDS)
    print(f"  loaded {len(df):,} log lines")

    df["tpl"] = df["content"].map(event_template)
    top = df["tpl"].value_counts().head(VOCAB_SIZE).index
    det = LogAnomalyDetector(vocab_size=VOCAB_SIZE)
    det.set_vocab({t: i for i, t in enumerate(top)})
    k = len(det.vocab)  # OTHER bucket id

    df["tid"] = df["tpl"].map(lambda t: det.vocab.get(t, k))
    X = pd.crosstab(df["block_id"], df["tid"]).reindex(columns=range(k + 1), fill_value=0)
    y = df.groupby("block_id")["anomaly"].max().reindex(X.index).astype(int)
    print(f"  sessions {len(X):,} · anomaly rate {y.mean() * 100:.2f}% · templates {df['tpl'].nunique()}")

    Xtr, Xte, ytr, yte = train_test_split(
        X.values, y.values, test_size=0.30, random_state=42, stratify=y.values
    )
    det.fit_features(Xtr, ytr)
    proba = det.model.predict_proba(Xte)[:, 1]
    pred = (proba >= det.threshold).astype(int)

    # Calibration: is a 0.9 score right ~90% of the time? Measure ECE/Brier on the
    # held-out probabilities, then recalibrate with isotonic regression fit on a
    # DISJOINT half of the held-out set and evaluated on the other half (so the
    # before/after comparison is on identical, unseen data).
    uncal = calibration_report(yte, proba)
    p_fit, p_eval, y_fit, y_eval = train_test_split(
        proba, yte, test_size=0.50, random_state=42, stratify=yte
    )
    iso = IsotonicRegression(out_of_bounds="clip").fit(p_fit, y_fit)
    before = calibration_report(y_eval, p_eval)
    after = calibration_report(y_eval, iso.predict(p_eval))
    card = {
        "dataset": REPO,
        "shards_used": SHARDS,
        "sessions_total": int(len(X)),
        "sessions_heldout": int(len(yte)),
        "anomaly_rate": round(float(y.mean()), 4),
        "vocab_size": k,
        "model": "LogisticRegression(bag-of-events)",
        "metrics": {
            "precision": round(float(precision_score(yte, pred)), 3),
            "recall": round(float(recall_score(yte, pred)), 3),
            "f1": round(float(f1_score(yte, pred)), 3),
            "roc_auc": round(float(roc_auc_score(yte, proba)), 3),
        },
        "calibration": {
            "held_out": uncal,  # ECE/Brier of predict_proba on the full held-out set
            "isotonic_recalibration": {
                "eval_n": int(len(y_eval)),
                "before": before,
                "after": after,
            },
            "note": ("ECE/Brier on held-out predict_proba; isotonic fit on a disjoint "
                     "half of the held-out set, evaluated on the other half."),
        },
        "caveats": [
            "Bag-of-events discards intra-session order; sequence models "
            "(DeepLog, LogLLM) report higher F1 on complete sessions.",
            "Trained on streamed/partial sessions per shard, which caps recall.",
            "Detection layer only — does not touch localization or change ranking.",
        ],
    }

    ART.mkdir(exist_ok=True)
    det.save(ART / "log_anomaly.joblib")
    (ART / "log_anomaly_card.json").write_text(json.dumps(card, indent=2))

    m = card["metrics"]
    print(
        f"\nHELD-OUT (n={card['sessions_heldout']:,}): "
        f"precision {m['precision']} · recall {m['recall']} · "
        f"f1 {m['f1']} · roc_auc {m['roc_auc']}"
    )
    c = card["calibration"]
    print(
        f"CALIBRATION: held-out ECE {c['held_out']['ece']} · Brier {c['held_out']['brier']} "
        f"| isotonic ECE {c['isotonic_recalibration']['before']['ece']} -> "
        f"{c['isotonic_recalibration']['after']['ece']}"
    )
    print(f"  saved -> artifacts/log_anomaly.joblib · artifacts/log_anomaly_card.json")
    print(f"  done in {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
