"""VerdictPlane hand-off — reference governor decision matrix + gate semantics (hermetic)."""
from sentinel.action_proposal import build_action_proposal
from sentinel.verdictplane import Decision, reference_governor, submit

_INV = {
    "detected": True, "scenario": "flag_spike", "detectT": 15, "mttd": 3,
    "sloErrPct": 0.5, "root": "checkout", "confidence": 0.91,
    "evidence": {"p95Before": 120, "p95After": 940, "failingSpan": "POST /charge"},
    "change": {"service": "checkout", "change": "deploy v14", "t": 14},
    "blastRadius": [{"service": "checkout", "errorPct": 60}],
}


def _proposal(**overrides):
    return build_action_proposal(dict(_INV, **overrides)).model_dump(mode="json")


def test_grounded_gated_proposal_requires_approval():
    # a normal Sentinel proposal: fully grounded but propose-only -> human gate
    v = submit(_proposal())
    assert v.decision == Decision.requires_approval and v.policy_applied == "human-gate"


def test_ungrounded_proposal_is_denied():
    # no correlated change -> grounding 0.75 < 0.95 -> denied
    v = submit(_proposal(change=None))
    assert v.decision == Decision.denied and v.policy_applied == "min-evidence"


def test_low_confidence_is_denied():
    v = submit(_proposal(confidence=0.2))
    assert v.decision == Decision.denied and v.policy_applied == "min-evidence"


def test_no_action_is_denied():
    p = _proposal()
    p["proposed_action"]["type"] = "none"
    assert reference_governor(p).decision == Decision.denied
    assert reference_governor(p).policy_applied == "no-op"


def test_ungated_grounded_proposal_is_allowed():
    # prove the human gate is what forces approval: remove it on a grounded proposal
    p = _proposal()
    p["policy"]["requires_human_approval"] = False
    p["policy"]["autonomy_level"] = "auto"
    assert reference_governor(p).decision == Decision.allowed


def test_verdict_references_proposal_and_is_deterministic():
    p = _proposal()
    a, b = submit(p), submit(p)
    assert a.proposal_id == p["proposal_id"] and a.verdict_id.startswith("vd_")
    assert a.verdict_id == b.verdict_id  # deterministic governance
