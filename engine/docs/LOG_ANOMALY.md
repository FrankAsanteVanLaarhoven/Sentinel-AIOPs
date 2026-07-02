# Log-anomaly detector — model card

The **one** learned component in Sentinel. It scores whether a log session is
anomalous. Everything downstream — root-service localization and change
correlation — stays deterministic graph analysis and is **not** trained.

## Task & data
- **Dataset:** [`logfit-project/HDFS_v1`](https://huggingface.co/datasets/logfit-project/HDFS_v1)
  — real Hadoop DFS logs with per-block anomaly labels (public, ungated).
- **Sessions:** raw log lines grouped by `block_id`; a block is anomalous if any
  of its lines is labelled anomalous.
- **Features:** each line is reduced to an **event template** by masking volatile
  tokens (`blk_…`→`<BLK>`, ip:port→`<IP>`, paths→`<PATH>`, numbers→`<NUM>`); a
  session is the **bag-of-events** count vector over the top-48 templates plus a
  shared `OTHER` bucket.
- **Model:** `LogisticRegression` — interpretable, fast, inspectable coefficients.

## Measured performance (held-out)
Reproduce with `make train-logdet` (1 shard; `SHARDS=5` for the full corpus).

| metric | value |
|---|---|
| precision | **0.992** |
| recall | **0.564** |
| F1 | **0.719** |
| ROC-AUC | **0.787** |

_Configuration:_ 1 shard → 108,047 sessions, 4.95 % anomaly rate, 44 distinct
templates; evaluated on a 32,415-session held-out split (30 %, stratified,
`random_state=42`). Numbers are the honest output of the shipped pipeline, not a
tuned upper bound.

## When this is wrong (failure modes)
- **Bag-of-events discards intra-session order.** Sequence models (DeepLog,
  LogLLM) report materially higher F1 on *complete* sessions; this representation
  trades that recall for interpretability and speed.
- **Streamed / partial sessions** (per-shard grouping) cap recall — a block split
  across shards is seen incompletely.
- **High precision, modest recall:** at the default threshold it rarely
  false-alarms but misses roughly a third of anomalies. Calibrate the decision
  threshold (and any fusion weight with a burn-rate rule) to the operating point
  you need.

## Boundary (why this is safe)
This detector produces a scalar anomaly probability **only**. It never sees the
service topology, never picks a root cause, and never ranks changes. Those
remain rule-based and replayable, so an operator can audit *why* Sentinel
localized an incident without interpreting model weights. Detection may be
learned; causal reasoning that must be trusted in production stays deterministic.
