"""SIEM export — ECS + CEF renderings of the audit log (hermetic)."""
import json

import pytest

from sentinel.action_proposal import build_action_proposal
from sentinel.audit_log import AuditLog
from sentinel.siem_export import entry_to_cef, export

_INV = {
    "detected": True, "scenario": "flag_spike", "detectT": 15, "mttd": 3,
    "sloErrPct": 0.5, "root": "checkout", "confidence": 0.91,
    "evidence": {"p95Before": 120, "p95After": 940, "failingSpan": "POST /charge"},
    "change": {"service": "checkout", "change": "deploy v14", "t": 14},
    "blastRadius": [{"service": "checkout", "errorPct": 60}],
}


def _log_with_two(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    log.record(build_action_proposal(dict(_INV, scenario="s1")).model_dump(mode="json"), now=1000.0)
    log.record(build_action_proposal(dict(_INV, scenario="s2")).model_dump(mode="json"), now=1001.0)
    return log


def test_ecs_export_is_ndjson_with_provenance(tmp_path):
    log = _log_with_two(tmp_path)
    lines = export(log.entries(), "ecs").splitlines()
    assert len(lines) == 2
    e0 = json.loads(lines[0])
    ent0 = log.entries()[0]
    assert e0["@timestamp"].startswith("1970-01-01T00:16:40")  # 1000s since epoch, UTC
    assert e0["event"]["id"] == ent0["proposal_id"]
    assert e0["event"]["hash"] == ent0["entry_hash"]          # chain preserved
    assert e0["service"]["name"] == "checkout"
    assert e0["event"]["action"] == "rollback_change"
    assert e0["sentinel"]["evidence_grounding"] == 1.0
    assert e0["ecs"]["version"] == "8.11"


def test_cef_export_header_and_provenance_fields(tmp_path):
    log = _log_with_two(tmp_path)
    ent0 = log.entries()[0]
    lines = export(log.entries(), "cef").splitlines()
    assert len(lines) == 2
    line = lines[0]
    assert line.startswith("CEF:0|Frank Asante Van Laarhoven|Sentinel-AIOPs|1.0|rollback_change|")
    assert f"externalId={ent0['proposal_id']}" in line
    assert "cs1Label=chainHash" in line and ent0["entry_hash"] in line
    assert "cn1Label=confidence" in line


def test_cef_severity_tracks_confidence():
    entry = {"logged_at": 1.0, "proposal_id": "rp_x",
             "proposal": {"confidence": 0.2, "root_service": "svc",
                          "proposed_action": {"type": "rollback_change"}}}
    # severity = round(0.2*10) = 2, in the 7th |-delimited header field
    assert entry_to_cef(entry).split("|")[6] == "2"


def test_cef_escapes_special_characters():
    # a value containing '=' and '|' must be escaped so the CEF line stays parseable
    entry = {"logged_at": 1.0, "proposal_id": "rp=1|x",
             "proposal": {"confidence": 0.5, "root_service": "a|b",
                          "proposed_action": {"type": "rollback_change"}}}
    line = entry_to_cef(entry)
    assert "a\\|b" in line             # pipe escaped in the header name
    assert "externalId=rp\\=1|x" in line  # '=' escaped in the extension value


def test_unknown_format_rejected(tmp_path):
    log = _log_with_two(tmp_path)
    with pytest.raises(ValueError):
        export(log.entries(), "splunk-raw")
