"""End-to-end enforcement demo: a Sentinel rollback that *physically cannot run* until approved.

The decision path (`/handoff`) proves what VerdictPlane *would* decide. This proves the
whole loop under real enforcement: Sentinel diagnoses -> proposes a rollback -> VerdictPlane's
`govern()` intercepts it. Because policy makes `incident.rollback` `require_human`, the
rollback side effect is blocked on a human gate and recorded in VerdictPlane's tamper-evident
ledger. Three outcomes, all provable:

  1. no reviewer -> times out -> DENIED (fail-closed): the rollback never runs.
  2. reviewer approves -> the rollback runs, exactly once, only after approval.
  3. weak evidence -> policy DENY before the gate: the rollback never runs, no human asked.

Run: `make enforce-demo`  (needs the `verdictplane` package installed).
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import verdictplane as vp  # noqa: E402  (in-path, zero-egress governance library)
from verdictplane import ApprovalDenied, PolicyDenied  # noqa: E402

from sentinel.action_proposal import build_action_proposal  # noqa: E402
from sentinel.verdictplane import DEFAULT_POLICY, proposal_to_action  # noqa: E402

# A real Sentinel investigation result (what /investigate produces): checkout is the
# localized root, a deploy is the correlated change, evidence fully grounds the diagnosis.
INCIDENT = {
    "detected": True, "scenario": "flag_spike", "detectT": 15, "mttd": 3, "sloErrPct": 0.5,
    "root": "checkout", "confidence": 0.91,
    "evidence": {"p95Before": 120, "p95After": 940, "failingSpan": "POST /charge"},
    "change": {"service": "checkout", "change": "deploy checkout@v128", "t": 14},
    "blastRadius": [{"service": "checkout", "errorPct": 60}, {"service": "cart", "errorPct": 20}],
}


def _rollback(executed: list, incident: dict) -> str:
    executed.append(incident["change"]["change"])
    return f"rolled back {incident['change']['change']} on {incident['root']}"


def _scene(title: str) -> None:
    print(f"\n{'=' * 68}\n{title}\n{'=' * 68}")


def main() -> int:
    policy = vp.load_policy(DEFAULT_POLICY)
    proposal = build_action_proposal(INCIDENT).model_dump(mode="json")
    action = proposal_to_action(proposal)
    print(f"Sentinel proposal {proposal['proposal_id']}: {proposal['proposed_action']['type']} "
          f"on {proposal['root_service']} (grounding {proposal['evidence_grounding']['ratio']}, "
          f"confidence {proposal['confidence']})")
    print(f"VerdictPlane action: {action['tool']} / effect={action['effect']}")

    demo_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("artifacts/enforce_demo")
    gate = vp.Gate(root=str(demo_dir / "gate"))
    ledger = vp.Ledger(path=str(demo_dir / "ledger.jsonl"))

    # --- Scene 1: no reviewer -> fail-closed timeout ---
    _scene("1. No reviewer approves — fail-closed")
    executed: list = []
    try:
        vp.govern(action, lambda: _rollback(executed, INCIDENT),
                  policy=policy, ledger=ledger, gate=gate, gate_timeout=0.3)
    except ApprovalDenied:
        print("BLOCKED: gate timed out -> DENIED. Rollback did NOT run.")
    print(f"rollback executed? {bool(executed)}  (expected False)")

    # --- Scene 2: reviewer approves -> runs exactly once, after approval ---
    _scene("2. On-call SRE approves — the rollback runs, only now")
    executed = []
    result: dict = {}

    def run():
        try:
            result["out"] = vp.govern(action, lambda: _rollback(executed, INCIDENT),
                                      policy=policy, ledger=ledger, gate=gate)
        except Exception as e:  # noqa: BLE001
            result["err"] = e

    t = threading.Thread(target=run, daemon=True)
    t.start()
    while not gate.list_pending():  # wait until govern() is blocked on the gate
        time.sleep(0.02)
    token = gate.list_pending()[0]["token"]
    print(f"pending approval {token[:12]}… — rollback is blocked, waiting for a human.")
    print(f"rollback executed while pending? {bool(executed)}  (expected False)")
    gate.approve(token, by="sre-oncall")
    t.join(timeout=5)
    print(f"reviewer approved -> {result.get('out')}")
    print(f"rollback executed after approval? {bool(executed)}  (expected True)")

    # --- Scene 3: weak evidence -> policy deny before any gate ---
    _scene("3. Weak evidence — denied by policy, no human asked")
    weak_proposal = dict(proposal, evidence_grounding={"ratio": 0.5})
    weak_action = proposal_to_action(weak_proposal)
    executed = []
    try:
        vp.govern(weak_action, lambda: _rollback(executed, INCIDENT),
                  policy=policy, ledger=ledger, gate=gate, gate_timeout=0.3)
    except PolicyDenied:
        print("BLOCKED: grounding 0.5 < 0.95 -> policy DENY (fail-closed). No gate, no run.")
    print(f"rollback executed? {bool(executed)}  (expected False)")

    # --- The ledger: every decision, tamper-evident ---
    _scene("VerdictPlane ledger — every decision, hash-chained")
    for e in ledger.entries():
        r = e["record"]
        print(f"  {r['decision']:<13} {r['outcome']:<16} {r['action']['tool']}")
    ok, bad = ledger.verify()
    print(f"\nledger.verify() -> ok={ok} (first bad index: {bad})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
