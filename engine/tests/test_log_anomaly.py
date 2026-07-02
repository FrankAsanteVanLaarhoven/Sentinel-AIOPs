"""Hermetic tests for the learned log-anomaly detector.

No network or dataset download — these exercise the deterministic templating,
featurisation, and a tiny in-memory fit/predict so the full suite stays fast
and offline. The real HDFS evaluation lives in scripts/train_log_anomaly.py.
"""
import numpy as np
import pytest

from sentinel.log_anomaly import LogAnomalyDetector, event_template


def test_event_template_masks_volatile_tokens():
    a = event_template("Receiving block blk_-1608999687919862906 src: /10.250.19.102:54106")
    b = event_template("Receiving block blk_42 src: /10.1.2.3:50010")
    # structurally identical lines collapse to one template
    assert a == b
    assert "<BLK>" in a and "<IP>" in a
    # bare numbers are masked too
    assert event_template("PacketResponder 1 for block terminating") == event_template(
        "PacketResponder 7 for block terminating"
    )


def test_featurize_counts_and_other_bucket():
    det = LogAnomalyDetector().set_vocab({"a <NUM>": 0, "b <NUM>": 1})
    # n_features = vocab (2) + OTHER (1)
    assert det.n_features == 3
    vec = det.featurize(["a 1", "a 2", "b 3", "zzz 9"])
    assert vec[0] == 2  # two "a <NUM>"
    assert vec[1] == 1  # one "b <NUM>"
    assert vec[2] == 1  # "zzz <NUM>" falls in OTHER


def test_untrained_detector_raises():
    with pytest.raises(RuntimeError):
        LogAnomalyDetector().set_vocab({"x": 0}).score(["x"])


def _synthetic():
    normal = [["Receiving block blk_1", "PacketResponder blk_1 terminating"]] * 30
    anomalous = [
        ["Receiving block blk_1", "ERROR got exception for blk_1", "PacketResponder blk_1 terminating"]
    ] * 30
    sessions = normal + anomalous
    labels = [0] * 30 + [1] * 30
    return sessions, labels


def test_fit_predict_separates_obvious_classes():
    sessions, labels = _synthetic()
    det = LogAnomalyDetector().fit(sessions, labels)
    # separable synthetic data -> near-perfect recovery
    preds = det.predict(sessions)
    assert (preds == np.asarray(labels)).mean() >= 0.9
    # a session with the error template scores higher than a clean one
    assert det.score(sessions[-1]) > det.score(sessions[0])


def test_save_load_roundtrip(tmp_path):
    sessions, labels = _synthetic()
    det = LogAnomalyDetector().fit(sessions, labels)
    p = tmp_path / "det.joblib"
    det.save(p)
    loaded = LogAnomalyDetector.load(p)
    assert loaded.vocab == det.vocab
    assert loaded.score(sessions[-1]) == pytest.approx(det.score(sessions[-1]))
