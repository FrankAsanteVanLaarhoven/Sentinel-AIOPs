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
import os
from enum import Enum
from pathlib import Path
from typing import Callable

from pydantic import BaseModel

# Shipped default hand-off policy (operator-overridable via VERDICTPLANE_POLICY).
DEFAULT_POLICY = str(Path(__file__).resolve().parents[2] / "policies" / "verdictplane_handoff.yaml")

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


# --- real VerdictPlane governor (in-path, zero-egress library — not a remote service) ---

# VerdictPlane decision (allow/deny/require_human) -> Sentinel Verdict decision.
_VP_DECISION = {"allow": Decision.allowed, "deny": Decision.denied,
                "require_human": Decision.requires_approval}

# Sentinel proposed_action.type -> a VerdictPlane (tool, effect). A remediation that
# would mutate the system is an ``execute`` on ``incident.rollback``; assistive outputs
# are ``notify`` / ``propose`` and carry no side effect.
_TOOL = {
    "rollback_change": ("incident.rollback", "execute"),
    "disable_feature_flag": ("incident.rollback", "execute"),
    "scale_service": ("incident.rollback", "execute"),
    "restart_service": ("incident.rollback", "execute"),
    "page_owner": ("incident.page", "notify"),
    "open_incident": ("incident.open", "notify"),
    "none": ("incident.noop", "propose"),
}


def proposal_to_action(proposal: dict) -> dict:
    """Map a Sentinel ``ActionProposal`` onto a VerdictPlane ``Action`` dict."""
    pa = proposal.get("proposed_action") or {}
    tool, effect = _TOOL.get(pa.get("type", "none"), ("incident.rollback", "execute"))
    return {
        "tool": tool,
        "effect": effect,
        "agent": "sentinel",
        "args": {
            "service": proposal.get("root_service"),
            "action_type": pa.get("type"),
            "change": (pa.get("params") or {}).get("change"),
            "confidence": float(proposal.get("confidence", 0.0)),
            "grounding": float((proposal.get("evidence_grounding") or {}).get("ratio", 0.0)),
            "proposal_id": proposal.get("proposal_id"),
        },
        "context": {"scenario": (proposal.get("incident") or {}).get("scenario")},
    }


def verdictplane_governor(proposal: dict, policy_path: str | None = None) -> Verdict:
    """The authoritative governor: delegates to the real VerdictPlane engine in-process.

    Sentinel supplies the action + a policy document and calls ``verdictplane.evaluate``;
    VerdictPlane owns the decision. Requires the ``verdictplane`` package (in-path,
    zero-egress). Raises ImportError if it is not installed — callers fall back via
    ``submit``."""
    import verdictplane as vp  # local, in-process — no network egress
    policy_path = policy_path or os.environ.get("VERDICTPLANE_POLICY", DEFAULT_POLICY)
    decision, rule = vp.evaluate(proposal_to_action(proposal), vp.load_policy(policy_path))
    pid = proposal.get("proposal_id", "")
    pol = f"verdictplane:{os.path.basename(policy_path)}"
    mapped = _VP_DECISION.get(decision, Decision.requires_approval)
    return Verdict(
        verdict_id=_verdict_id(pid, mapped.value, pol), proposal_id=pid, decision=mapped,
        policy_applied=pol, governor="verdictplane",
        reason=(f"matched rule {rule['match']} -> {decision}" if rule else f"policy default -> {decision}"))


def _default_governor() -> Callable[[dict], Verdict]:
    """Prefer the real VerdictPlane engine; fall back to the reference consumer offline."""
    try:
        import verdictplane  # noqa: F401
        return verdictplane_governor
    except Exception:
        return reference_governor


def submit(proposal: dict, governor: Callable[[dict], Verdict] | None = None) -> Verdict:
    """Sentinel-side client: hand a proposal to a governor and return its verdict.

    Defaults to the real VerdictPlane engine when installed (in-process, zero-egress),
    else the reference consumer so the loop stays testable offline. The ``Verdict.governor``
    field records which one decided."""
    return (governor or _default_governor())(proposal)
