"""Export the tamper-evident audit log to a SIEM format on stdout.

    python scripts/export_audit.py --format ecs        # Elastic Common Schema (NDJSON)
    python scripts/export_audit.py --format cef        # ArcSight Common Event Format
    python scripts/export_audit.py --format ecs | <your SIEM forwarder>

Reads SENTINEL_AUDIT_PATH (default artifacts/audit_log.jsonl). Read-only: it projects
the audit log; it never mutates it. The hash chain + signature are carried through so the
SIEM can re-verify provenance.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sentinel.audit_log import AuditLog  # noqa: E402
from sentinel.siem_export import export  # noqa: E402

_DEFAULT = str(Path(__file__).resolve().parents[1] / "artifacts" / "audit_log.jsonl")


def main() -> int:
    ap = argparse.ArgumentParser(description="SIEM export of the Sentinel audit log")
    ap.add_argument("--format", default="ecs", choices=["ecs", "cef"])
    ap.add_argument("--path", default=os.environ.get("SENTINEL_AUDIT_PATH", _DEFAULT))
    args = ap.parse_args()
    body = export(AuditLog(args.path).entries(), args.format)
    if body:
        print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
