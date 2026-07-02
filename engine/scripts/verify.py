"""Verify every demo scenario localizes to its documented ground-truth root.

Runs the real engine (detect -> localize) on each scenario's store and checks
the localized root against the scenario's declared ground truth. Prints a table
and exits non-zero if any scenario disagrees. `make verify`."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sentinel.scenarios import SCENARIO_META, build  # noqa: E402
from sentinel.incident_agent import detect, localize  # noqa: E402
from sentinel.telemetry_sim import INC  # noqa: E402
from sentinel.tools import TelemetryTools  # noqa: E402


def main() -> int:
    ok = 0
    print(f"{'scenario':20} {'localized':16} {'ground-truth':16} {'MTTD':5} result")
    print("-" * 68)
    for m in SCENARIO_META:
        store = build(m["id"])
        tools = TelemetryTools(store)
        t, _ = detect(tools)
        culprit = localize(tools, t)[0] if t is not None else None
        gt = store["ground_truth_root"]
        good = culprit == gt
        ok += good
        mttd = f"{t - INC}m" if t is not None else "-"
        print(f"{m['id']:20} {str(culprit):16} {gt:16} {mttd:5} {'PASS' if good else 'FAIL'}")
    n = len(SCENARIO_META)
    print("-" * 68)
    print(f"{ok}/{n} scenarios at {round(100 * ok / n)}% ground-truth agreement")
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
