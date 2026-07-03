"""Learned metric-anomaly detection — the second detection-layer model.

Multivariate server metrics are unsupervised: "normal" is learned from an
anomaly-free training window, and a test point is anomalous when it no longer
fits that normal subspace. We fit **PCA on the normal data** and score a point by
its **reconstruction error** — the energy it carries outside the learned normal
subspace — smoothed over a short window (anomalies are contiguous) and compared
to a threshold taken from the *training* error distribution. The threshold never
sees test labels.

Trained and evaluated on the real, public Server Machine Dataset (SMD) — see
``scripts/train_metric_anomaly.py`` and ``docs/METRIC_ANOMALY.md``.

Like the log detector, this is a standalone real-data capability in the
detection layer. It never touches localization or change ranking. sklearn is
imported lazily in ``fit`` only; scoring is pure numpy.
"""
from __future__ import annotations

import numpy as np

VAR_DEFAULT = 0.9
SMOOTH_DEFAULT = 5
QUANTILE_DEFAULT = 0.999


def _smooth(x: np.ndarray, w: int) -> np.ndarray:
    if w <= 1:
        return x
    return np.convolve(x, np.ones(w) / w, mode="same")


class MetricAnomalyDetector:
    """PCA reconstruction-error detector for multivariate metric time-series."""

    def __init__(self, var: float = VAR_DEFAULT, smooth: int = SMOOTH_DEFAULT,
                 train_quantile: float = QUANTILE_DEFAULT):
        self.var = var
        self.smooth = smooth
        self.train_quantile = train_quantile
        self.mu: np.ndarray | None = None
        self.sd: np.ndarray | None = None
        self.components: np.ndarray | None = None  # PCA components_ (Vt)
        self.threshold: float | None = None

    def _standardize(self, X: np.ndarray) -> np.ndarray:
        return (np.asarray(X, dtype=float) - self.mu) / self.sd

    def _recon_error(self, Xs: np.ndarray) -> np.ndarray:
        proj = Xs @ self.components.T
        recon = proj @ self.components
        return _smooth(((Xs - recon) ** 2).sum(axis=1), self.smooth)

    def fit(self, X_train: np.ndarray) -> "MetricAnomalyDetector":
        """Fit on an anomaly-free training window; set the threshold from its own
        reconstruction-error distribution (never from test labels)."""
        from sklearn.decomposition import PCA

        X = np.asarray(X_train, dtype=float)
        self.mu = X.mean(axis=0)
        self.sd = X.std(axis=0) + 1e-8
        Xs = self._standardize(X)
        pca = PCA(n_components=self.var, random_state=0).fit(Xs)
        self.components = pca.components_
        self.threshold = float(np.quantile(self._recon_error(Xs), self.train_quantile))
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        """Per-timestamp anomaly score (smoothed reconstruction error)."""
        self._require_fit()
        return self._recon_error(self._standardize(X))

    def predict(self, X: np.ndarray) -> np.ndarray:
        self._require_fit()
        return (self.score(X) >= self.threshold).astype(int)

    def _require_fit(self) -> None:
        if self.components is None:
            raise RuntimeError("MetricAnomalyDetector is not fitted; call fit() or load().")

    def save(self, path) -> None:
        import joblib

        joblib.dump(
            {"var": self.var, "smooth": self.smooth, "train_quantile": self.train_quantile,
             "mu": self.mu, "sd": self.sd, "components": self.components, "threshold": self.threshold},
            path,
        )

    @classmethod
    def load(cls, path) -> "MetricAnomalyDetector":
        import joblib

        b = joblib.load(path)
        d = cls(b["var"], b["smooth"], b["train_quantile"])
        d.mu, d.sd, d.components, d.threshold = b["mu"], b["sd"], b["components"], b["threshold"]
        return d


def point_adjust(pred: np.ndarray, label: np.ndarray) -> np.ndarray:
    """SMD's standard point-adjustment: if any point inside a true anomaly
    segment is flagged, the whole segment counts as detected. Reported alongside
    (not instead of) the raw point-wise score."""
    pred = np.asarray(pred).copy()
    label = np.asarray(label)
    i, n = 0, len(label)
    while i < n:
        if label[i] == 1:
            j = i
            while j < n and label[j] == 1:
                j += 1
            if pred[i:j].any():
                pred[i:j] = 1
            i = j
        else:
            i += 1
    return pred


def prf(pred: np.ndarray, label: np.ndarray) -> tuple[float, float, float]:
    """Point-wise precision, recall, F1."""
    pred, label = np.asarray(pred), np.asarray(label)
    tp = int(((pred == 1) & (label == 1)).sum())
    fp = int(((pred == 1) & (label == 0)).sum())
    fn = int(((pred == 0) & (label == 1)).sum())
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f
