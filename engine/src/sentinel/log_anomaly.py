"""Learned log-anomaly detection — the one place ML is allowed in Sentinel.

A lightweight, interpretable detector. Raw log lines are grouped into sessions
(for HDFS, per block id); each session's event-template counts form a
bag-of-events vector; a logistic-regression model scores the session's anomaly
probability. Trained and evaluated on the real, public `logfit-project/HDFS_v1`
corpus via ``scripts/train_log_anomaly.py`` — see ``docs/LOG_ANOMALY.md`` for the
measured held-out performance envelope and its caveats.

Architectural boundary: this component lives ONLY in the detection layer. It
scores logs; it never participates in topology traversal, root-service
identification, or change ranking. Those stay deterministic graph analysis so
they remain inspectable and replayable — no model weights touch them.

Heavy dependencies (scikit-learn, joblib) are imported lazily inside methods so
that importing this module — e.g. for ``event_template`` — stays dependency-free.
"""
from __future__ import annotations

import re
from typing import Iterable, Sequence

import numpy as np

# Volatile tokens are normalised away so that structurally identical log lines
# collapse to a single event template (block ids, ip:port, paths, bare numbers).
_SUBS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"blk_-?\d+"), "<BLK>"),
    (re.compile(r"/?\d+\.\d+\.\d+\.\d+(:\d+)?"), "<IP>"),
    (re.compile(r"/[\w./:-]+"), "<PATH>"),
    (re.compile(r"\b\d+\b"), "<NUM>"),
]
_WS = re.compile(r"\s+")


def event_template(line: str) -> str:
    """Reduce a raw log line to its event template by masking volatile tokens.

    Deterministic and dependency-free — the same function is used at train and
    inference time, so session features are identical in both paths.
    """
    s = line
    for rx, rep in _SUBS:
        s = rx.sub(rep, s)
    return _WS.sub(" ", s).strip()


class LogAnomalyDetector:
    """Bag-of-events logistic detector over per-session event templates.

    Typical use::

        det = LogAnomalyDetector().fit(sessions, labels)   # sessions: iterables of lines
        det.score(session)                                 # -> anomaly probability in [0, 1]

    For large corpora the training script builds the feature matrix in a
    vectorised pass and calls :meth:`fit_features` directly.
    """

    def __init__(self, vocab_size: int = 48):
        self.vocab_size = vocab_size
        self.vocab: dict[str, int] = {}
        self.model = None  # sklearn LogisticRegression, set by fit / fit_features
        self.threshold = 0.5

    @property
    def n_features(self) -> int:
        return len(self.vocab) + 1  # + shared OTHER bucket

    # -- vocabulary / featurisation --------------------------------------
    def fit_vocab(self, sessions: Iterable[Sequence[str]]) -> "LogAnomalyDetector":
        from collections import Counter

        counts: Counter[str] = Counter()
        for session in sessions:
            for line in session:
                counts[event_template(line)] += 1
        self.vocab = {t: i for i, (t, _) in enumerate(counts.most_common(self.vocab_size))}
        return self

    def set_vocab(self, vocab: dict[str, int]) -> "LogAnomalyDetector":
        self.vocab = dict(vocab)
        return self

    def featurize(self, session: Sequence[str]) -> np.ndarray:
        """One session -> bag-of-events count vector (last slot = OTHER)."""
        vec = np.zeros(self.n_features, dtype=np.float64)
        other = len(self.vocab)
        for line in session:
            vec[self.vocab.get(event_template(line), other)] += 1.0
        return vec

    def transform(self, sessions: Sequence[Sequence[str]]) -> np.ndarray:
        if len(sessions) == 0:
            return np.empty((0, self.n_features), dtype=np.float64)
        return np.vstack([self.featurize(s) for s in sessions])

    # -- learning --------------------------------------------------------
    def fit(self, sessions, labels, **kwargs) -> "LogAnomalyDetector":
        if not self.vocab:
            self.fit_vocab(sessions)
        return self.fit_features(self.transform(sessions), labels, **kwargs)

    def fit_features(self, X: np.ndarray, y, **kwargs) -> "LogAnomalyDetector":
        """Fit the classifier on a pre-built feature matrix (columns aligned to
        ``vocab`` ids 0..K-1 plus the OTHER bucket at K)."""
        from sklearn.linear_model import LogisticRegression

        params = {"max_iter": 1000, **kwargs}
        self.model = LogisticRegression(**params).fit(X, np.asarray(y, dtype=int))
        return self

    # -- inference -------------------------------------------------------
    def score(self, session: Sequence[str]) -> float:
        """Anomaly probability in [0, 1] for a single session."""
        self._require_model()
        return float(self.model.predict_proba(self.featurize(session).reshape(1, -1))[0, 1])

    def predict_proba(self, sessions: Sequence[Sequence[str]]) -> np.ndarray:
        self._require_model()
        return self.model.predict_proba(self.transform(sessions))[:, 1]

    def predict(self, sessions: Sequence[Sequence[str]]) -> np.ndarray:
        return (self.predict_proba(sessions) >= self.threshold).astype(int)

    def _require_model(self) -> None:
        if self.model is None:
            raise RuntimeError("LogAnomalyDetector is not trained; call fit() or load().")

    # -- persistence -----------------------------------------------------
    def save(self, path) -> None:
        import joblib

        joblib.dump(
            {
                "vocab": self.vocab,
                "vocab_size": self.vocab_size,
                "model": self.model,
                "threshold": self.threshold,
            },
            path,
        )

    @classmethod
    def load(cls, path) -> "LogAnomalyDetector":
        import joblib

        blob = joblib.load(path)
        det = cls(blob["vocab_size"])
        det.vocab = blob["vocab"]
        det.model = blob["model"]
        det.threshold = blob.get("threshold", 0.5)
        return det
