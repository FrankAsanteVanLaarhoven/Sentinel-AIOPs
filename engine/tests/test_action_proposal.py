"""ActionProposal contract — Sentinel proposes, never acts (hermetic)."""
from sentinel.action_proposal import ActionType, build_action_proposal

_INV = {
    "detected": True, "scenario": "flag_spike", "detectT": 15, "mttd": 3,
    "sloErrPct": 0.5, "root": "checkout", "confidence": 0.91,
    "evidence": {"p95Before": 120, "p95After": 940, "failingSpan": "POST /charge"},
    "change": {"service": "checkout", "change": "deploy v14", "t": 14},
    "blastRadius": [{"service": "checkout", "errorPct": 60}, {"service": "cart", "errorPct": 20}],
}


def test_proposal_is_propose_only_and_never_executed():
    p = build_action_proposal(_INV)
    assert p.policy.autonomy_level == "propose_only"
    assert p.policy.fail_closed is True and p.policy.requires_human_approval is True
    assert p.handoff.target == "verdictplane" and p.handoff.executed is False


def test_change_yields_typed_targeted_rollback():
    p = build_action_proposal(_INV)
    assert p.proposed_action.type == ActionType.rollback_change
    assert p.proposed_action.target_service == "checkout"
    assert p.root_service == "checkout" and p.confidence == 0.91


def test_evidence_grounding_is_measured():
    p = build_action_proposal(_INV)
    # every diagnosis claim is backed here -> full grounding
    assert p.evidence_grounding.ratio == 1.0
    assert p.evidence_grounding.claims_linked == p.evidence_grounding.claims_total
    kinds = {e.kind for e in p.evidence}
    assert {"metric", "topology", "trace", "change"} <= kinds


def test_no_correlated_change_downgrades_action_and_grounding():
    inv = dict(_INV, change=None)
    p = build_action_proposal(inv)
    assert p.proposed_action.type == ActionType.page_owner
    assert p.evidence_grounding.ratio < 1.0  # the change claim is unlinked


def test_replay_id_is_deterministic():
    a, b = build_action_proposal(_INV), build_action_proposal(dict(_INV))
    assert a.proposal_id == b.proposal_id and a.proposal_id.startswith("rp_")
    diff = build_action_proposal(dict(_INV, confidence=0.42))
    assert diff.proposal_id != a.proposal_id
