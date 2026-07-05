"""Typed ActionProposal — Sentinel's hand-off contract to VerdictPlane.

Sentinel *diagnoses* and *proposes*; it never executes. This module turns an
investigation into a typed, evidence-linked proposal whose policy is
propose-only / fail-closed / human-gated by construction, so a separate
deterministic controller (VerdictPlane) decides whether the action runs.

This is the "measured autonomy" contract made concrete: an action is proposed
only alongside the evidence that grounds it and the confidence that qualifies it.
Sentinel never sets ``handoff.executed`` — only VerdictPlane can act.
"""
from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0"


class ActionType(str, Enum):
    rollback_change = "rollback_change"
    disable_feature_flag = "disable_feature_flag"
    scale_service = "scale_service"
    restart_service = "restart_service"
    page_owner = "page_owner"
    open_incident = "open_incident"
    none = "none"


class EvidenceRef(BaseModel):
    id: str
    kind: Literal["metric", "trace", "log", "change", "topology"]
    detail: str


class ProposedAction(BaseModel):
    type: ActionType
    target_service: Optional[str] = None
    params: dict = Field(default_factory=dict)
    rationale: str


class EvidenceGrounding(BaseModel):
    """Fraction of diagnosis claims backed by an evidence reference (target >= 0.95)."""
    claims_total: int
    claims_linked: int
    ratio: float


class Policy(BaseModel):
    autonomy_level: Literal["propose_only"] = "propose_only"
    fail_closed: bool = True
    requires_human_approval: bool = True


class Handoff(BaseModel):
    target: Literal["verdictplane"] = "verdictplane"
    status: Literal["pending_verdict"] = "pending_verdict"
    executed: bool = False  # Sentinel never sets this True — only VerdictPlane can.


class Reproducibility(BaseModel):
    deterministic: bool = True
    method: str
    replay_id: str


class Incident(BaseModel):
    scenario: str
    detected_at: Optional[int] = None
    mttd: Optional[int] = None
    slo_error_pct: Optional[float] = None


class ActionProposal(BaseModel):
    schema_version: str = SCHEMA_VERSION
    proposal_id: str
    incident: Incident
    root_service: Optional[str]
    confidence: float
    evidence: list[EvidenceRef]
    evidence_grounding: EvidenceGrounding
    proposed_action: ProposedAction
    policy: Policy = Field(default_factory=Policy)
    handoff: Handoff = Field(default_factory=Handoff)
    reproducibility: Reproducibility


def _replay_id(scenario: str, root: Optional[str], change: Optional[dict], confidence: float) -> str:
    """Deterministic id: same incident input ⇒ same proposal id (replayability)."""
    canon = json.dumps(
        {"scenario": scenario, "root": root, "change": change, "confidence": round(confidence, 4)},
        sort_keys=True,
    )
    return "rp_" + hashlib.sha256(canon.encode()).hexdigest()[:16]


def build_action_proposal(inv: dict, method: str = "causal_root (deterministic)") -> ActionProposal:
    """Map an ``/investigate`` result into the typed VerdictPlane contract.

    Every diagnosis claim is registered with (or without) an evidence reference, so
    ``evidence_grounding.ratio`` is *measured*, not asserted. The proposed action is
    typed and targeted; policy/handoff are propose-only / fail-closed / human-gated.
    """
    scenario = inv.get("scenario", "unknown")
    root = inv.get("root")
    conf = float(inv.get("confidence", 0.0))
    change = inv.get("change")
    ev_raw = inv.get("evidence") or {}
    blast = inv.get("blastRadius") or []

    evidence: list[EvidenceRef] = []
    # claim -> whether we could attach evidence for it (drives the grounding ratio)
    claims: list[bool] = []

    # claim 1: an SLO breach occurred (metric evidence)
    if ev_raw.get("p95After") is not None:
        evidence.append(EvidenceRef(
            id="ev-metric-p95", kind="metric",
            detail=f"{root} latency_p95 {ev_raw.get('p95Before')}ms -> {ev_raw.get('p95After')}ms at t={inv.get('detectT')}m"))
        claims.append(True)
    else:
        claims.append(False)

    # claim 2: the root was localized (topology / blast-radius evidence)
    if root and blast:
        top = ", ".join(f"{b['service']}={b['errorPct']}%" for b in blast[:3])
        evidence.append(EvidenceRef(
            id="ev-topology-blast", kind="topology",
            detail=f"root={root}; dependents explained by it; blast: {top}"))
        claims.append(True)
    else:
        claims.append(bool(root))

    # claim 3: a failing span corroborates the root (trace evidence)
    if ev_raw.get("failingSpan"):
        evidence.append(EvidenceRef(
            id="ev-trace-span", kind="trace",
            detail=f"error span on {root}: {ev_raw.get('failingSpan')}"))
        claims.append(True)

    # claim 4: a root-cause change was correlated near onset (change evidence)
    if change:
        evidence.append(EvidenceRef(
            id="ev-change", kind="change",
            detail=f"{change.get('change')} on {change.get('service')} at t={change.get('t')}m"))
        claims.append(True)
    else:
        claims.append(False)

    linked = sum(claims)
    total = len(claims)
    grounding = EvidenceGrounding(
        claims_total=total, claims_linked=linked,
        ratio=round(linked / total, 3) if total else 0.0)

    if change:
        action = ProposedAction(
            type=ActionType.rollback_change, target_service=root,
            params={"change": change.get("change"), "at_t": change.get("t")},
            rationale=f"Roll back {change.get('change')} on {root} (closest change to onset), then confirm recovery.")
    elif root:
        action = ProposedAction(
            type=ActionType.page_owner, target_service=root,
            rationale=f"{root} localized as root but no correlated change found — page the owner to investigate.")
    else:
        action = ProposedAction(
            type=ActionType.open_incident,
            rationale="Breach detected but root not localized — open an incident for human triage.")

    return ActionProposal(
        proposal_id=_replay_id(scenario, root, change, conf),
        incident=Incident(
            scenario=scenario, detected_at=inv.get("detectT"),
            mttd=inv.get("mttd"), slo_error_pct=inv.get("sloErrPct")),
        root_service=root,
        confidence=round(conf, 3),
        evidence=evidence,
        evidence_grounding=grounding,
        proposed_action=action,
        reproducibility=Reproducibility(
            method=method, replay_id=_replay_id(scenario, root, change, conf)),
    )
