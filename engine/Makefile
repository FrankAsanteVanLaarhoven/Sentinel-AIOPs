export PYTHONPATH := src
install: ; pip install -r requirements.txt
test:    ; pytest -q
demo:    ; python demo/run_incident.py         # detect -> localize -> root cause report
run:     ; uvicorn sentinel.api.main:app --reload   # instrumented sample service
incident:; FEATURE_FLAG_NEW_RANKING=1 uvicorn sentinel.api.main:app --port 8000  # reproduce the incident
stack:   ; docker compose -f deploy/docker-compose.yml up --build   # OTel + Prometheus + Tempo + Loki + Grafana
