"""Hermetic tests for the metric-anomaly detector.

No download — a small synthetic multivariate series (normal training window, then
a test window with an injected anomalous segment) exercises fit / score / predict,
the point-adjust helper, and save/load. The real SMD evaluation lives in
scripts/train_metric_anomaly.py.
"""
import numpy as np
import pytest

from sentinel.metric_anomaly import MetricAnomalyDetector, point_adjust, prf


def _data(seed=0):
    rng = np.random.default_rng(seed)
    # 5 correlated normal metrics
    base = rng.normal(0, 1, size=(600, 2))
    mix = rng.normal(0, 1, size=(2, 5))
    train = base @ mix + rng.normal(0, 0.05, size=(600, 5))
    tb = rng.normal(0, 1, size=(400, 2))
    test = tb @ mix + rng.normal(0, 0.05, size=(400, 5))
    label = np.zeros(400, dtype=int)
    # inject a contiguous anomaly: break the correlation structure
    test[200:230] += rng.normal(0, 6, size=(30, 5))
    label[200:230] = 1
    return train, test, label


def test_fit_detects_injected_segment():
    train, test, label = _data()
    det = MetricAnomalyDetector().fit(train)
    pred = det.predict(test)
    p, r, f = prf(pred, label)
    # the injected segment should be largely caught, with the normal region mostly clean
    assert r >= 0.7
    assert p >= 0.3


def test_point_adjust_fills_segment():
    label = np.array([0, 0, 1, 1, 1, 0, 1, 1, 0])
    pred = np.array([0, 0, 0, 1, 0, 0, 0, 0, 0])  # one hit inside the first segment only
    adj = point_adjust(pred, label)
    assert list(adj) == [0, 0, 1, 1, 1, 0, 0, 0, 0]  # first segment filled, second untouched


def test_unfitted_raises():
    with pytest.raises(RuntimeError):
        MetricAnomalyDetector().score(np.zeros((3, 5)))


def test_save_load_roundtrip(tmp_path):
    train, test, _ = _data()
    det = MetricAnomalyDetector().fit(train)
    p = tmp_path / "metric.joblib"
    det.save(p)
    loaded = MetricAnomalyDetector.load(p)
    assert loaded.threshold == det.threshold
    assert np.array_equal(loaded.predict(test), det.predict(test))
