"""Tamper-evident audit log for Sentinel ActionProposals — a provenance layer.

Append-only, hash-chained (each entry commits to the previous via
``entry_hash = sha256(prev_hash + core)``), and optionally HMAC-signed. It records
*what Sentinel proposed* so the chain can be replayed by ``proposal_id`` /
``replay_id`` and verified byte-for-byte — altering any past entry breaks the chain.

Deliberately narrow (see PROJECT_BOUNDARY.md): it stores **only ActionProposals**.
No telemetry, no execution, no policy evaluation. This is provenance for Sentinel's
outputs, not a general logging system.

Entry schema (one JSON object per line):
    seq         monotonic index (0-based append order)
    logged_at   unix seconds when appended
    proposal_id the ActionProposal id
    replay_id   the reproducibility.replay_id
    proposal    the full ActionProposal payload (JSON-native)
    prev_hash   entry_hash of the previous entry (GENESIS for seq 0)
    entry_hash  sha256(prev_hash + "\\n" + canonical({seq,logged_at,proposal_id,replay_id,proposal}))
    signature   HMAC-SHA256(key, entry_hash) if a key is configured, else null
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from typing import Optional

GENESIS = "0" * 64
_CORE_FIELDS = ("seq", "logged_at", "proposal_id", "replay_id", "proposal")


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _entry_hash(prev_hash: str, core: dict) -> str:
    return hashlib.sha256((prev_hash + "\n" + _canonical(core)).encode()).hexdigest()


def _sign(key: Optional[str], entry_hash: str) -> Optional[str]:
    if not key:
        return None
    return hmac.new(key.encode(), entry_hash.encode(), hashlib.sha256).hexdigest()


class AuditLog:
    """Append-only, hash-chained provenance log at ``path`` (JSON Lines).

    Signing key comes from ``key`` or the ``SENTINEL_AUDIT_KEY`` env var; without a
    key the hash chain still makes tampering detectable, just not authenticated.
    """

    def __init__(self, path, key: Optional[str] = None):
        self.path = Path(path)
        self.key = key if key is not None else os.environ.get("SENTINEL_AUDIT_KEY")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(ln) for ln in self.path.read_text().splitlines() if ln.strip()]

    def head_hash(self) -> str:
        e = self._entries()
        return e[-1]["entry_hash"] if e else GENESIS

    def record(self, proposal: dict, now: Optional[float] = None) -> dict:
        """Append a proposal to the chain. Idempotent by ``proposal_id`` — because
        proposals are deterministic, re-recording the same id returns the existing
        entry instead of duplicating it (keeps the log append-only and clean)."""
        entries = self._entries()
        pid = proposal.get("proposal_id")
        for e in entries:
            if e.get("proposal_id") == pid:
                return e
        seq = len(entries)
        prev_hash = entries[-1]["entry_hash"] if entries else GENESIS
        core = {
            "seq": seq,
            "logged_at": round(now if now is not None else time.time(), 3),
            "proposal_id": pid,
            "replay_id": (proposal.get("reproducibility") or {}).get("replay_id"),
            "proposal": proposal,
        }
        eh = _entry_hash(prev_hash, core)
        entry = {**core, "prev_hash": prev_hash, "entry_hash": eh, "signature": _sign(self.key, eh)}
        with self.path.open("a") as f:
            f.write(_canonical(entry) + "\n")
        return entry

    def get(self, action_id: str) -> Optional[dict]:
        """Look up an entry by ``proposal_id`` or ``replay_id`` (replayability)."""
        for e in self._entries():
            if e.get("proposal_id") == action_id or e.get("replay_id") == action_id:
                return e
        return None

    def verify(self) -> dict:
        """Re-walk the chain: check linkage, recompute every entry hash, and (if a
        key is set) every signature. Returns integrity status + first broken seq."""
        entries = self._entries()
        prev = GENESIS
        for i, e in enumerate(entries):
            core = {k: e.get(k) for k in _CORE_FIELDS}
            if e.get("prev_hash") != prev:
                return {"ok": False, "broken_at": i, "reason": "prev_hash mismatch", "length": len(entries)}
            if _entry_hash(prev, core) != e.get("entry_hash"):
                return {"ok": False, "broken_at": i, "reason": "entry_hash mismatch", "length": len(entries)}
            if self.key and _sign(self.key, e["entry_hash"]) != e.get("signature"):
                return {"ok": False, "broken_at": i, "reason": "signature mismatch", "length": len(entries)}
            prev = e["entry_hash"]
        return {"ok": True, "broken_at": None, "length": len(entries),
                "head_hash": prev, "signed": bool(self.key)}
