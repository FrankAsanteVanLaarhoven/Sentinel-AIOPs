"""A sample OpenTelemetry-instrumented service emitting golden signals (RED).
Set FEATURE_FLAG_NEW_RANKING=1 to reproduce the incident (productcatalog errors) — the exact
scenario the incident engine investigates."""
import os, time, random
from fastapi import FastAPI, HTTPException
from sentinel.instrumentation import setup

tracer, RED = setup(os.environ.get("SERVICE_NAME", "productcatalog"))
app = FastAPI(title="Sentinel sample service")
BROKEN = os.environ.get("FEATURE_FLAG_NEW_RANKING") == "1"

try:  # optional auto-instrumentation of FastAPI routes/spans
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    FastAPIInstrumentor.instrument_app(app)
except Exception:
    pass

@app.get("/health")
def health(): return {"status": "ok"}

@app.get("/products/{pid}")
def get_product(pid: str):
    start = time.time()
    with tracer.start_as_current_span("productcatalog.GetProduct") as span:
        span.set_attribute("product.id", pid)
        RED["requests"].add(1, {"route": "/products"})
        if BROKEN and random.random() < 0.22:               # the injected failure
            RED["errors"].add(1, {"route": "/products"})
            span.set_attribute("otel.status_code", "ERROR")
            RED["latency"].record((time.time()-start)*1000, {"route": "/products"})
            raise HTTPException(500, "ranking backend unavailable")
        RED["latency"].record((time.time()-start)*1000, {"route": "/products"})
        return {"id": pid, "name": "Hamlet (e-book)"}
