"""Calibration metrics for probabilistic predictions — ECE, MCE, Brier, reliability curve.

A detector can be accurate yet *miscalibrated*: a 0.9 score should be right ~90% of the
time. These functions measure that gap on held-out (label, probability) pairs. Pure numpy,
no model — so they apply equally to the log detector's `predict_proba`, a recalibrated
variant, or any other scored, labelled predictions.

- **Brier score** — mean squared error of the probability; proper scoring rule, lower better.
- **ECE** — expected calibration error: bin by predicted probability, average |accuracy −
  confidence| weighted by bin population. Lower better; 0 = perfectly calibrated.
- **MCE** — the worst single-bin gap (max calibration error).
- **reliability_curve** — per-bin (confidence, accuracy, count) for a reliability diagram.
"""
from __future__ import annotations

import numpy as np


def _as_arrays(y_true, y_prob) -> tuple[np.ndarray, np.ndarray]:
    y = np.asarray(y_true, dtype=float).ravel()
    p = np.asarray(y_prob, dtype=float).ravel()
    if y.shape != p.shape:
        raise ValueError(f"y_true and y_prob must align: {y.shape} vs {p.shape}")
    if y.size == 0:
        raise ValueError("empty inputs")
    return y, p


def brier_score(y_true, y_prob) -> float:
    """Mean squared error between probability and outcome (proper scoring rule)."""
    y, p = _as_arrays(y_true, y_prob)
    return float(np.mean((p - y) ** 2))


def reliability_curve(y_true, y_prob, n_bins: int = 10) -> list[tuple[float, float, int]]:
    """Per-bin (mean confidence, empirical accuracy, count) over equal-width probability
    bins; empty bins are omitted."""
    y, p = _as_arrays(y_true, y_prob)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    # bin index in [0, n_bins-1]; the right edge (p==1) belongs to the last bin
    idx = np.clip(np.digitize(p, edges[1:-1], right=False), 0, n_bins - 1)
    out = []
    for b in range(n_bins):
        mask = idx == b
        count = int(mask.sum())
        if count:
            out.append((float(p[mask].mean()), float(y[mask].mean()), count))
    return out


def expected_calibration_error(y_true, y_prob, n_bins: int = 10) -> float:
    """ECE: population-weighted mean of |accuracy − confidence| across bins."""
    y, p = _as_arrays(y_true, y_prob)
    n = y.size
    return float(sum(abs(acc - conf) * count / n
                     for conf, acc, count in reliability_curve(y, p, n_bins)))


def max_calibration_error(y_true, y_prob, n_bins: int = 10) -> float:
    """MCE: the largest |accuracy − confidence| over any populated bin."""
    curve = reliability_curve(y_true, y_prob, n_bins)
    return float(max((abs(acc - conf) for conf, acc, _ in curve), default=0.0))


def calibration_report(y_true, y_prob, n_bins: int = 10) -> dict:
    """Bundle the headline calibration metrics for a model card."""
    return {
        "brier": round(brier_score(y_true, y_prob), 4),
        "ece": round(expected_calibration_error(y_true, y_prob, n_bins), 4),
        "mce": round(max_calibration_error(y_true, y_prob, n_bins), 4),
        "n_bins": n_bins,
    }
