"""SIEM export for the audit log — ECS (Elastic) and CEF (ArcSight) renderings.

Projects tamper-evident `ActionProposal` audit entries into the two formats SIEMs
ingest, **preserving the hash chain + signature** so the SIEM can re-verify provenance
downstream. This is a read-only projection of the audit log — it adds no scope: no
execution, no policy, no new state (see PROJECT_BOUNDARY.md).

- **ECS** (Elastic Common Schema) — newline-delimited JSON, one object per entry.
- **CEF** (Common Event Format) — `CEF:0|vendor|product|version|sigID|name|severity|ext`.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

PRODUCT = "Sentinel-AIOPs"
VENDOR = "Frank Asante Van Laarhoven"


def _iso(logged_at) -> str:
    return datetime.fromtimestamp(float(logged_at or 0), tz=timezone.utc).isoformat()


def entry_to_ecs(entry: dict) -> dict:
    """One audit entry -> an Elastic Common Schema document."""
    p = entry.get("proposal") or {}
    action = p.get("proposed_action") or {}
    grounding = p.get("evidence_grounding") or {}
    return {
        "@timestamp": _iso(entry.get("logged_at")),
        "ecs": {"version": "8.11"},
        "event": {
            "kind": "event",
            "category": ["configuration"],
            "type": ["info"],
            "action": action.get("type"),
            "id": entry.get("proposal_id"),
            "sequence": entry.get("seq"),
            "hash": entry.get("entry_hash"),
            "provider": "sentinel-aiops",
            "module": "action-proposal",
            "risk_score": p.get("confidence"),
            "reason": action.get("rationale"),
        },
        "service": {"name": p.get("root_service")},
        "labels": {
            "replay_id": entry.get("replay_id"),
            "autonomy_level": (p.get("policy") or {}).get("autonomy_level"),
            "handoff_target": (p.get("handoff") or {}).get("target"),
        },
        "sentinel": {
            "evidence_grounding": grounding.get("ratio"),
            "action_target": action.get("target_service"),
            "prev_hash": entry.get("prev_hash"),
            "signature": entry.get("signature"),
        },
    }


def _cef_header(s) -> str:
    # CEF header escaping: backslash and pipe.
    return str(s).replace("\\", "\\\\").replace("|", "\\|")


def _cef_value(v) -> str:
    # CEF extension-value escaping: backslash, equals, and newlines.
    return str(v).replace("\\", "\\\\").replace("=", "\\=").replace("\n", "\\n")


def entry_to_cef(entry: dict, severity: int | None = None) -> str:
    """One audit entry -> a CEF line. Severity defaults to round(confidence*10) in [0,10]."""
    p = entry.get("proposal") or {}
    action = p.get("proposed_action") or {}
    conf = float(p.get("confidence") or 0.0)
    sev = severity if severity is not None else max(0, min(10, round(conf * 10)))
    name = f"ActionProposal {action.get('type')} on {p.get('root_service')}"
    header = "|".join([
        "CEF:0", _cef_header(VENDOR), _cef_header(PRODUCT),
        _cef_header(p.get("schema_version", "1.0")),
        _cef_header(action.get("type")), _cef_header(name), str(sev),
    ])
    ext = {
        "rt": int(float(entry.get("logged_at") or 0) * 1000),
        "externalId": entry.get("proposal_id"),
        "act": action.get("type"),
        "dhost": p.get("root_service"),
        "cn1": conf, "cn1Label": "confidence",
        "cfp1": (p.get("evidence_grounding") or {}).get("ratio"), "cfp1Label": "evidenceGrounding",
        "cs1": entry.get("entry_hash"), "cs1Label": "chainHash",
        "cs2": entry.get("replay_id"), "cs2Label": "replayId",
        "cs3": entry.get("signature"), "cs3Label": "signature",
        "cs4": (p.get("handoff") or {}).get("target"), "cs4Label": "handoffTarget",
    }
    ext_str = " ".join(f"{k}={_cef_value(v)}" for k, v in ext.items() if v is not None)
    return f"{header}|{ext_str}"


def export(entries, fmt: str = "ecs") -> str:
    """Render an iterable of audit entries as newline-delimited SIEM records."""
    fmt = (fmt or "ecs").lower()
    if fmt == "ecs":
        return "\n".join(json.dumps(entry_to_ecs(e), sort_keys=True) for e in entries)
    if fmt == "cef":
        return "\n".join(entry_to_cef(e) for e in entries)
    raise ValueError(f"unknown format {fmt!r} (use 'ecs' or 'cef')")
