"""End-to-end enforcement — a governed rollback cannot run unless policy + a human allow it."""
import threading
import time

import pytest

pytest.importorskip("verdictplane")
import verdictplane as vp  # noqa: E402
from verdictplane import ApprovalDenied, PolicyDenied  # noqa: E402

from sentinel.action_proposal import build_action_proposal  # noqa: E402
from sentinel.verdictplane import DEFAULT_POLICY, proposal_to_action  # noqa: E402

_INC = {
    "detected": True, "scenario": "flag_spike", "detectT": 15, "mttd": 3, "sloErrPct": 0.5,
    "root": "checkout", "confidence": 0.91,
    "evidence": {"p95Before": 120, "p95After": 940, "failingSpan": "POST /charge"},
    "change": {"service": "checkout", "change": "deploy v128", "t": 14},
    "blastRadius": [{"service": "checkout", "errorPct": 60}],
}


def _env(tmp_path):
    return (vp.Gate(root=str(tmp_path / "gate")),
            vp.Ledger(path=str(tmp_path / "ledger.jsonl")),
            vp.load_policy(DEFAULT_POLICY))


def _rollback_action():
    return proposal_to_action(build_action_proposal(_INC).model_dump(mode="json"))


def test_timeout_denies_and_rollback_never_runs(tmp_path):
    gate, ledger, policy = _env(tmp_path)
    ran = []
    with pytest.raises(ApprovalDenied):
        vp.govern(_rollback_action(), lambda: ran.append(1),
                  policy=policy, ledger=ledger, gate=gate, gate_timeout=0.2)
    assert ran == []
    ok, _ = ledger.verify()
    assert ok


def test_approval_lets_the_rollback_run_exactly_once(tmp_path):
    gate, ledger, policy = _env(tmp_path)
    ran, out = [], {}

    def run():
        try:
            out["r"] = vp.govern(_rollback_action(), lambda: (ran.append(1), "rolled-back")[1],
                                 policy=policy, ledger=ledger, gate=gate)
        except Exception as e:  # noqa: BLE001
            out["e"] = e

    t = threading.Thread(target=run, daemon=True)
    t.start()
    for _ in range(250):  # wait until govern() is blocked on the gate
        if gate.list_pending():
            break
        time.sleep(0.02)
    assert ran == []  # blocked while pending — the side effect has NOT run
    gate.approve(gate.list_pending()[0]["token"], by="reviewer")
    t.join(timeout=5)
    assert ran == [1] and out.get("r") == "rolled-back"


def test_weak_evidence_is_denied_by_policy_before_any_gate(tmp_path):
    gate, ledger, policy = _env(tmp_path)
    action = _rollback_action()
    action["args"]["grounding"] = 0.5  # below the fail-closed threshold
    ran = []
    with pytest.raises(PolicyDenied):
        vp.govern(action, lambda: ran.append(1),
                  policy=policy, ledger=ledger, gate=gate, gate_timeout=0.2)
    assert ran == []
