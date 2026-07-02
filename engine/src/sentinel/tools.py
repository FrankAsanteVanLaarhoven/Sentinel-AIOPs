"""MCP-style tools the agent calls. Backed by the sim here; in production each maps to a real
query (Prometheus range query, Tempo trace search, a change/deploy feed). The agent calls these over MCP."""
class TelemetryTools:
    def __init__(self, store): self.s = store
    def query_metric(self, service, signal, t0, t1): return self.s["metrics"][service][signal][t0:t1]
    def list_changes(self, t0, t1): return [c for c in self.s["changes"] if t0 <= c["t"] < t1]
    def get_error_traces(self, service): return [x for x in self.s["traces"]
                                                 if x["status"] == "ERROR" and service in x["error_span"]]
