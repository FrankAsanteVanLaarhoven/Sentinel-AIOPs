"""VerdictPlane hand-off — reference consumer + the real in-path VerdictPlane engine."""
import pytest

from sentinel.action_proposal import build_action_proposal
from sentinel.verdictplane import (
    Decision, reference_governor, submit, verdictplane_governor,
)

_INV = {
    "detected": True, "scenario": "flag_spike", "detectT": 15, "mttd": 3,
    "sloErrPct": 0.5, "root": "checkout", "confidence": 0.91,
    "evidence": {"p95Before": 120, "p95After": 940, "failingSpan": "POST /charge"},
    "change": {"service": "checkout", "change": "deploy v14", "t": 14},
    "blastRadius": [{"service": "checkout", "errorPct": 60}],
}


def _proposal(**overrides):
    return build_action_proposal(dict(_INV, **overrides)).model_dump(mode="json")


# --- reference consumer (offline stand-in) ---

def test_reference_grounded_gated_requires_approval():
    v = reference_governor(_proposal())
    assert v.decision == Decision.requires_approval and v.policy_applied == "human-gate"


def test_reference_ungrounded_is_denied():
    v = reference_governor(_proposal(change=None))  # grounding 0.75 < 0.95
    assert v.decision == Decision.denied and v.policy_applied == "min-evidence"


def test_reference_ungated_grounded_is_allowed():
    p = _proposal()
    p["policy"]["requires_human_approval"] = False
    p["policy"]["autonomy_level"] = "auto"
    assert reference_governor(p).decision == Decision.allowed


# --- the real VerdictPlane engine (in-path, zero-egress) ---

pytest.importorskip("verdictplane")


def test_vp_grounded_rollback_requires_approval():
    v = verdictplane_governor(_proposal())
    assert v.decision == Decision.requires_approval and v.governor == "verdictplane"
    assert v.policy_applied.startswith("verdictplane:")


def test_vp_fails_closed_on_weak_evidence():
    # a rollback whose evidence grounding is below threshold is DENIED by policy
    weak = {"proposal_id": "rp_weak", "root_service": "checkout", "confidence": 0.9,
            "evidence_grounding": {"ratio": 0.5},
            "proposed_action": {"type": "rollback_change", "params": {}},
            "incident": {"scenario": "s"}}
    assert verdictplane_governor(weak).decision == Decision.denied


def test_submit_defaults_to_real_verdictplane():
    v = submit(_proposal())
    assert v.governor == "verdictplane"
    assert v.proposal_id == _proposal()["proposal_id"] and v.verdict_id.startswith("vd_")
