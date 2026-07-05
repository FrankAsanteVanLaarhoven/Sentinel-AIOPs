"""Calibration metrics — ECE / MCE / Brier / reliability curve (hermetic, synthetic)."""
import numpy as np
import pytest

from sentinel.calibration import (
    brier_score,
    calibration_report,
    expected_calibration_error,
    max_calibration_error,
    reliability_curve,
)


def test_perfectly_calibrated_has_near_zero_ece():
    # 10 groups; in the group with confidence c, a c-fraction are positive -> ECE ~ 0
    rng = np.random.default_rng(0)
    probs, labels = [], []
    for c in np.linspace(0.05, 0.95, 10):
        n = 2000
        probs += [c] * n
        labels += list((rng.random(n) < c).astype(int))
    ece = expected_calibration_error(labels, probs, n_bins=10)
    assert ece < 0.02
    assert brier_score(labels, probs) < 0.26  # ~p(1-p) for balanced-ish mix


def test_overconfident_predictions_have_large_ece_and_mce():
    # always predict 0.99 but only 50% are positive -> ~0.49 gap
    y = [0, 1] * 500
    p = [0.99] * 1000
    assert expected_calibration_error(y, p) > 0.45
    assert max_calibration_error(y, p) > 0.45
    assert abs(brier_score(y, p) - np.mean((0.99 - np.array(y)) ** 2)) < 1e-9


def test_brier_is_zero_for_perfect_hard_predictions():
    y = [0, 1, 1, 0, 1]
    assert brier_score(y, y) == 0.0
    assert expected_calibration_error(y, y) == 0.0


def test_reliability_curve_bins_and_skips_empties():
    curve = reliability_curve([0, 1, 1], [0.1, 0.9, 0.95], n_bins=10)
    assert len(curve) == 2  # only the 0.1 bin and the 0.9–0.95 bin are populated
    confs = [c for c, _, _ in curve]
    assert confs == sorted(confs)
    assert sum(cnt for _, _, cnt in curve) == 3


def test_report_bundles_metrics_and_validates_shape():
    rep = calibration_report([0, 1, 0, 1], [0.2, 0.8, 0.3, 0.7])
    assert set(rep) == {"brier", "ece", "mce", "n_bins"}
    with pytest.raises(ValueError):
        brier_score([0, 1], [0.5])  # misaligned
