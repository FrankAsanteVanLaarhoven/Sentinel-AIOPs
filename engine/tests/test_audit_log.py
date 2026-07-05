"""Tamper-evident audit log — hash-chaining, idempotency, tamper detection, signing."""
from sentinel.action_proposal import build_action_proposal
from sentinel.audit_log import GENESIS, AuditLog

_INV = {
    "detected": True, "scenario": "flag_spike", "detectT": 15, "mttd": 3,
    "sloErrPct": 0.5, "root": "checkout", "confidence": 0.91,
    "evidence": {"p95Before": 120, "p95After": 940, "failingSpan": "POST /charge"},
    "change": {"service": "checkout", "change": "deploy v14", "t": 14},
    "blastRadius": [{"service": "checkout", "errorPct": 60}],
}


def _proposal(scenario="flag_spike", confidence=0.91):
    inv = dict(_INV, scenario=scenario, confidence=confidence)
    return build_action_proposal(inv).model_dump(mode="json")


def test_record_appends_and_chains(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    a = log.record(_proposal("s1"), now=1000.0)
    b = log.record(_proposal("s2"), now=1001.0)
    assert a["seq"] == 0 and a["prev_hash"] == GENESIS
    assert b["seq"] == 1 and b["prev_hash"] == a["entry_hash"]
    assert log.verify()["ok"] is True and log.verify()["length"] == 2


def test_record_is_idempotent_by_proposal_id(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    first = log.record(_proposal("s1"), now=1000.0)
    again = log.record(_proposal("s1"), now=9999.0)  # same deterministic proposal
    assert again["entry_hash"] == first["entry_hash"]
    assert log.verify()["length"] == 1  # no duplicate appended


def test_get_by_proposal_and_replay_id(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    p = _proposal("s1")
    log.record(p, now=1000.0)
    assert log.get(p["proposal_id"])["proposal_id"] == p["proposal_id"]
    assert log.get(p["reproducibility"]["replay_id"])["proposal_id"] == p["proposal_id"]
    assert log.get("nope") is None


def test_tampering_breaks_the_chain(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    log.record(_proposal("s1"), now=1000.0)
    log.record(_proposal("s2"), now=1001.0)
    assert log.verify()["ok"] is True
    # rewrite entry 0's proposal payload without recomputing its hash
    lines = path.read_text().splitlines()
    lines[0] = lines[0].replace('"checkout"', '"attacker"')
    path.write_text("\n".join(lines) + "\n")
    v = log.verify()
    assert v["ok"] is False and v["broken_at"] == 0


def test_signing_authenticates_and_detects_forgery(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(path, key="s3cr3t")
    e = log.record(_proposal("s1"), now=1000.0)
    assert e["signature"] is not None
    assert log.verify()["ok"] is True and log.verify()["signed"] is True
    # forge the signature -> verify fails
    lines = path.read_text().splitlines()
    lines[0] = lines[0].replace(e["signature"], "0" * 64)
    path.write_text("\n".join(lines) + "\n")
    assert log.verify()["ok"] is False and log.verify()["reason"] == "signature mismatch"
