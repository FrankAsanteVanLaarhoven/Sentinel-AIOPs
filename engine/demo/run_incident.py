"""End-to-end demo: simulate telemetry with an injected incident, run the engine, emit the report."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from sentinel.telemetry_sim import simulate
from sentinel.incident_agent import investigate

store = simulate()
metrics, report = investigate(store)
print(report)
print(json.dumps(metrics, indent=2))
os.makedirs("artifacts", exist_ok=True)
open("artifacts/incident_report.md", "w").write(report)
json.dump(metrics, open("artifacts/incident_metrics.json", "w"), indent=2)
