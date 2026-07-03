# Metric-anomaly detector — model card

The **second** learned detection-layer model (the first is the log detector, see
`docs/LOG_ANOMALY.md`). It scores whether a point in a multivariate metric
time-series is anomalous. Everything downstream stays deterministic; this touches
only the detection layer.

Reproduce: `make install-ml && make train-metricdet` (`MACHINES=machine-1-1,…`
for a quick subset).

## Task & data
- **Dataset:** the public **Server Machine Dataset (SMD)** from
  [NetManAIOps/OmniAnomaly](https://github.com/NetManAIOps/OmniAnomaly) — 28
  machines, 38 metrics each, an anomaly-free **train** window and a **labelled
  test** window (per-timestamp 0/1).
- **Setting:** *unsupervised* — "normal" is learned from train; test labels are
  used **only to score**, never to fit or to pick the threshold.
- **Model:** PCA reconstruction error. Fit PCA on the standardised normal window
  (enough components for 90 % variance); a point's score is the energy outside
  that normal subspace, smoothed over 5 steps (anomalies are contiguous).
- **Threshold:** the **99.9th percentile of the training** reconstruction error —
  a fixed, train-only rule. No best-F1-on-test selection.

## Measured performance (full corpus, held-out test)
Pooled over all 28 machines · 708,420 test points · 4.2 % anomalous.

| metric | value |
|---|---|
| precision | **0.142** |
| recall | **0.403** |
| F1 (point-wise) | **0.210** |
| F1 (point-adjusted) | **0.350** |

These are deliberately conservative, honest figures.

## When this is wrong / how to read it
- **Point-wise vs the literature.** SMD papers almost always report
  *point-adjusted* F1 with a threshold **selected on the test set**, reaching
  0.8–0.9. That protocol uses the labels it is scored against. Here the threshold
  is fixed from training alone, so the point-wise F1 (0.21) and even the
  point-adjusted F1 (0.35) are far lower — and far more honest.
- **Low precision** at a fixed train threshold: SMD's test window drifts from
  train, so a fixed cut over-flags. Calibrate the threshold (and any fusion with
  a rule) to your operating point.
- **PCA is linear.** It captures correlated normal structure; nonlinear normal
  regimes need a richer model.

## Boundary
Like the log detector, this is a **standalone real-data capability** in the
detection layer. SMD machine metrics are a different domain from the microservice
demo and from PetShop, so it is **not** wired into the causal engine — it
demonstrates learned metric-anomaly detection on real data with honest held-out
numbers. Localization stays deterministic. Its card is served through
`GET /metric-anomaly` and composed into `GET /validation`.
