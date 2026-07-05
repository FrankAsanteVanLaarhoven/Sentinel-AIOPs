export PYTHONPATH := src
install: ; pip install -r requirements.txt
test:    ; pytest -q
demo:    ; python demo/run_incident.py         # detect -> localize -> root cause report
verify:  ; python scripts/verify.py            # all 5 scenarios vs documented ground-truth root
install-ml:   ; pip install -r requirements-ml.txt          # extras for the log detector + RCA harness
train-logdet:    ; python scripts/train_log_anomaly.py      # train+eval log-anomaly on real HDFS (SHARDS=n)
train-metricdet: ; python scripts/train_metric_anomaly.py   # train+eval metric-anomaly on real SMD (MACHINES=…)
validate-rca:    ; python scripts/validate_localization.py  # score causal localization on the real PetShop corpus
validate-rcaeval:; python scripts/validate_rcaeval.py       # score causal localization on the RCAEval benchmark (RE1)
validate-rcaeval-re2:; TIER=RE2 python scripts/validate_rcaeval_multi.py  # metrics-only causal_root on RE2/RE3 (framing A; TIER=RE3 for RE3)
derive-tt-graph:; python scripts/derive_tt_graph.py         # derive a verified TT call graph from RE2-TT traces (streams RE2-TT.zip)
tt-graph-delta:; python scripts/tt_graph_delta.py           # measured trade-off: TT graph-free vs the RE2-derived call graph
compare-baselines:; python scripts/compare_baselines.py     # Sentinel vs BARO on RE1 (TIER=RE2 for RE2 metric-only; needs RCAEVAL_SRC)
enforce-demo:    ; python scripts/enforcement_demo.py        # Sentinel rollback under real VerdictPlane enforcement (needs: pip install verdictplane)
export-audit:    ; python scripts/export_audit.py --format ecs   # SIEM export of the audit log (ECS; use --format cef for ArcSight)
serve:   ; uvicorn sentinel.api.engine_api:app --port 8008 --reload   # the incident engine HTTP API (:8008)
run:     ; uvicorn sentinel.api.main:app --reload   # instrumented sample service
incident:; FEATURE_FLAG_NEW_RANKING=1 uvicorn sentinel.api.main:app --port 8000  # reproduce the incident
stack:   ; docker compose -f deploy/docker-compose.yml up --build   # OTel + Prometheus + Tempo + Loki + Grafana
