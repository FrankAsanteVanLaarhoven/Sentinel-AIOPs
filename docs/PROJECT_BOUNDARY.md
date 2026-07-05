# Sentinel-AIOPs — Project Boundary

**One line.** Evidence-grounded operational **diagnosis**: detect an SLO breach, localize the
root cause with a deterministic, inspectable rule, link every claim to evidence, and emit a
**typed `ActionProposal`** — which it never executes.

**Place in the stack.** Sentinel is the *diagnosis* stage of an **Autonomous Systems
Governance Stack**:

```
Sentinel-AIOPs   →   VerdictPlane        (DriftGuardAI runs the same pattern for ML promotion)
evidence-grounded    deterministic
operational          action control
diagnosis            (executes/blocks)
```

**The moat: measured autonomy.** Sentinel diagnoses — and proposes action — **only when
evidence, benchmarks, and policy agree**. The differentiator is *not* "more AI"; it is that
every diagnosis is reproducible, benchmark-validated, and evidence-linked, and every action
is a typed proposal handed to a separate deterministic controller. We do not try to win on
breadth against Datadog/Dynatrace/New Relic; we win on **reproducibility and evidence-linked
RCA**.

---

## Does

- **Detect** an SLO/RED breach from OpenTelemetry-native signals (metrics; logs/traces where present).
- **Localize** the root cause with `causal_root` — a training-free, byte-identical, replayable
  rule (root = elevated service with no elevated dependency). Never tuned to a benchmark.
- **Ground every claim in evidence** — each diagnosis statement links to evidence IDs
  (metric/trace/log/change references); grounding completeness is measured, not asserted.
- **Validate on public benchmarks** — RCAEval RE1 (375 cases; AC@1 0.845 / Avg@5 0.900),
  PetShop (68 incidents), synthetic (5/5). Reproducible via `make validate-rca` / `validate-rcaeval`.
- **Emit a typed `ActionProposal`** (`sentinel.action_proposal`) — root, confidence, evidence,
  a typed remediation, and a **fail-closed, human-gated, propose-only** policy — for hand-off
  to **VerdictPlane**.
- **Record every proposal** to a **tamper-evident, hash-chained, optionally-signed** provenance
  log (`sentinel.audit_log`, queried at `GET /audit` / `GET /audit/verify`) — replayable by
  `proposal_id` / `replay_id`, alteration of any past entry is detectable.
- **Report honestly** — measured numbers only; trade-offs and failure modes disclosed.

## Does NOT

- **Execute remediation.** Sentinel proposes; it never mutates a production system. All actions
  route to VerdictPlane, which decides execution deterministically.
- **Replace your observability stack.** It integrates with Prometheus/Tempo/Loki/OTel; it is not
  a metrics store, dashboarding suite, or APM.
- **Do AI-governance enforcement.** Policy *enforcement* and in-path action control are
  **VerdictPlane's** job; drift-safe model promotion is **DriftGuardAI's**. Sentinel stays in
  diagnosis.
- **Invent numbers or claim cross-domain transfer.** Detectors are standalone real-data
  capabilities; no benchmark-wide claim is made from a small split; no oracle metric backs a
  deployable claim.
- **Become Datadog.** Breadth is out of scope by design — see the moat above.

---

## Integration contract (typed)

Sentinel's output to the rest of the stack is the **`ActionProposal`** (see
`engine/src/sentinel/action_proposal.py`, served at `GET /action-proposal`). Key invariants:

- `policy.autonomy_level = "propose_only"`, `policy.fail_closed = true`,
  `policy.requires_human_approval = true` — Sentinel is assistive by construction.
- `handoff.target = "verdictplane"`, `handoff.executed = false` — Sentinel never sets `executed`.
- `evidence_grounding.ratio` — fraction of diagnosis claims linked to evidence IDs (target ≥ 0.95).
- `reproducibility.deterministic = true` with a `replay_id` — same incident input ⇒ same proposal.
- Every proposal is appended to a **hash-chained** provenance log
  (`entry_hash = sha256(prev_hash + core)`), optionally **HMAC-signed** (`SENTINEL_AUDIT_KEY`);
  `GET /audit/verify` re-walks the chain and reports the first altered entry. The log stores
  proposals only — no telemetry, no execution, no policy evaluation.

VerdictPlane consumes an `ActionProposal` and returns a typed **`Verdict`**
(`allowed` / `denied` / `requires_approval`, referencing the `proposal_id`); it, not
Sentinel, performs or blocks the action. `GET /handoff` runs the full loop
(investigate → propose → record → govern) and, when the `verdictplane` package is
installed, delegates to the **real VerdictPlane engine in-process** — `verdictplane.evaluate`,
which is *in-path and zero-egress* (no network call, by VerdictPlane's design). Sentinel
maps the proposal to a VerdictPlane `Action` and supplies a policy document
(`engine/policies/verdictplane_handoff.yaml`, operator-overridable via `VERDICTPLANE_POLICY`);
**VerdictPlane owns the decision** — Sentinel does not evaluate policy. A minimal
`reference_governor` is the offline fallback for contract validation; `Verdict.governor`
records which decided. Because Sentinel proposals are always human-gated, a well-grounded
rollback resolves to `require_human` → `requires_approval` (never auto-`allowed`);
weak-evidence rollbacks are `denied` (fail-closed). Sentinel keeps no verdict ledger —
that is VerdictPlane's.

## Benchmark harness

`make verify` (synthetic) · `make validate-rca` (PetShop) · `make validate-rcaeval` (RCAEval RE1)
· `make compare-baselines` (vs BARO, ε-Diagnosis). Independent evaluation targets: RCAEval,
Cloud-OpsBench, AIOps2025/RCA100. Integrated evaluation: the `ActionProposal` → VerdictPlane path.

## Enterprise-readiness (staged, not scope-creep)

Commercial-grade requirements are adopted **incrementally**, newest-value first, without
diluting the diagnosis core:

| Layer | Status | Note |
|---|---|---|
| Observability | **partial** | OTel-native signals; engine is instrumentable |
| Docs / benchmark repro | **done** | MANUSCRIPT, SENTINEL_PAPER, RCAEVAL, reproducible `make` |
| Audit | **done** | hash-chained, optionally-signed provenance log of every `ActionProposal` (`/audit`, `/audit/verify`); SIEM export next |
| Reliability | **next** | health checks, retries, fail-closed (already the policy default), rollback via VerdictPlane |
| Security (SSO/RBAC/tenant) | later | open-core: free local engine, paid enterprise console |
| Deployment (Helm/Terraform/air-gap) | later | Docker exists; packaging later |
| SDKs (Python→TS/Go), connectors | later | Python engine first |

The rule: **each addition must preserve the boundary above.** If a feature would make Sentinel
execute actions, store telemetry, or enforce policy, it belongs in VerdictPlane or the
observability layer — not here.
