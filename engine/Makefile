export PYTHONPATH := src
install: ; pip install -r requirements.txt
test:    ; pytest -q
demo:    ; python demo/run_incident.py         # detect -> localize -> root cause report
verify:  ; python scripts/verify.py            # all 5 scenarios vs documented ground-truth root
install-ml:   ; pip install -r requirements-ml.txt          # extras for the log detector + RCA harness
train-logdet:    ; python scripts/train_log_anomaly.py      # train+eval log-anomaly on real HDFS (SHARDS=n)
train-metricdet: ; python scripts/train_metric_anomaly.py   # train+eval metric-anomaly on real SMD (MACHINES=…)
validate-rca:    ; python scripts/validate_localization.py  # score causal localization on the real PetShop corpus
validate-rcaeval:; python scripts/validate_rcaeval.py       # score causal localization on the RCAEval benchmark (RE1-OB)
serve:   ; uvicorn sentinel.api.engine_api:app --port 8008 --reload   # the incident engine HTTP API (:8008)
run:     ; uvicorn sentinel.api.main:app --reload   # instrumented sample service
incident:; FEATURE_FLAG_NEW_RANKING=1 uvicorn sentinel.api.main:app --port 8000  # reproduce the incident
stack:   ; docker compose -f deploy/docker-compose.yml up --build   # OTel + Prometheus + Tempo + Loki + Grafana
