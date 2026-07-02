import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from sentinel.telemetry_sim import simulate
from sentinel.incident_agent import investigate, detect
from sentinel.tools import TelemetryTools

def test_detects_incident():
    m, _ = investigate(simulate())
    assert m["detected"] and m["mttd_minutes"] <= 2      # fast detection

def test_localizes_root_cause_service():
    m, _ = investigate(simulate())
    assert m["localized"] == "productcatalog" and m["localization_correct"]

def test_identifies_change_and_blast_radius():
    m, _ = investigate(simulate())
    assert m["root_cause_found"]                          # found the feature-flag change
    assert set(m["affected"]) >= {"productcatalog", "frontend", "cart"}

def test_no_false_alarm_before_incident():
    store = simulate(); tools = TelemetryTools(store)
    t, _ = detect(tools)
    assert t is not None and t >= 40                      # no alert before the injected incident
