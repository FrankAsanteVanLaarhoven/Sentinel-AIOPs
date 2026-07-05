"""VerdictPlane hand-off — Sentinel's client + a reference consumer (contract validation).

Sentinel *proposes*; a deterministic controller *governs*. This module exercises that
loop end-to-end:

  * ``Verdict`` — the typed response contract Sentinel expects back.
  * ``submit(proposal, governor)`` — the Sentinel-side **client**: hands an
    ``ActionProposal`` to a governor and returns its ``Verdict`` (over HTTP in
    production; the governor is injected here for local validation).
  * ``reference_governor(proposal)`` — a **minimal, deterministic reference consumer**
    used only to validate the contract. It is *not* a policy engine and keeps no
    ledger; the authoritative governor is the separate **VerdictPlane** project. Its
    job here is to prove the handoff works and that the fail-closed / human-gate
    semantics are honoured.

Boundary: this lives on the seam between the two systems. Sentinel does not enforce
policy or store verdicts — it emits a proposal and consumes a verdict.
"""
from __future__ import annotations

import hashlib
from enum import Enum
from typing import Callable

from pydantic import BaseModel

# Reference-policy thresholds — the action may only auto-proceed when evidence and
# confidence clear these AND no human gate is set. Sentinel proposals always set the
# gate, so a well-formed proposal resolves to requires_approval, never allowed.
GROUNDING_MIN = 0.95
CONFIDENCE_MIN = 0.5


class Decision(str, Enum):
    allowed = "allowed"
    denied = "denied"
    requires_approval = "requires_approval"


class Verdict(BaseModel):
    verdict_id: str
    proposal_id: str          # reference back to the ActionProposal
    decision: Decision
    policy_applied: str
    reason: str
    governor: str = "verdictplane-reference"
    deterministic: bool = True


def _verdict_id(proposal_id: str, decision: str, policy: str) -> str:
    return "vd_" + hashlib.sha256(f"{proposal_id}|{decision}|{policy}".encode()).hexdigest()[:16]


def reference_governor(proposal: dict) -> Verdict:
    """Minimal deterministic policy over an ActionProposal (a VerdictPlane stand-in):

    - deny when evidence-grounding or confidence is insufficient, or there is no action;
    - otherwise require human approval whenever the proposal is propose-only / gated
      (Sentinel proposals always are — so this is the normal path);
    - allow only when a proposal is explicitly not human-gated *and* well-grounded.
    """
    pid = proposal.get("proposal_id", "")
    policy = proposal.get("policy") or {}
    grounding = float((proposal.get("evidence_grounding") or {}).get("ratio", 0.0))
    conf = float(proposal.get("confidence", 0.0))
    action = (proposal.get("proposed_action") or {}).get("type", "none")

    if action == "none":
        decision, pol, reason = Decision.denied, "no-op", "proposal carries no actionable remediation"
    elif grounding < GROUNDING_MIN or conf < CONFIDENCE_MIN:
        decision, pol, reason = (
            Decision.denied, "min-evidence",
            f"evidence grounding {grounding:.2f} < {GROUNDING_MIN} or confidence {conf:.2f} < {CONFIDENCE_MIN}")
    elif policy.get("requires_human_approval", True) or policy.get("autonomy_level") == "propose_only":
        decision, pol, reason = (
            Decision.requires_approval, "human-gate",
            "well-grounded, but propose-only / human approval required by policy")
    else:
        decision, pol, reason = Decision.allowed, "auto", "well-grounded and not human-gated"

    return Verdict(
        verdict_id=_verdict_id(pid, decision.value, pol),
        proposal_id=pid, decision=decision, policy_applied=pol, reason=reason)


def submit(proposal: dict, governor: Callable[[dict], Verdict] = reference_governor) -> Verdict:
    """Sentinel-side client: hand a proposal to a governor and return its verdict.
    In production ``governor`` posts to the VerdictPlane service; here it defaults to
    the reference consumer so the loop is testable offline."""
    return governor(proposal)
