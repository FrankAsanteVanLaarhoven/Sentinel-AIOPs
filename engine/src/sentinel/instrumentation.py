"""OpenTelemetry wiring: traces + RED metrics + logs, exported via OTLP to the Collector.
Vendor-neutral (CNCF standard) so the same instrumentation works with any backend."""
from opentelemetry import trace, metrics
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

def setup(service_name: str):
    res = Resource.create({"service.name": service_name})
    tp = TracerProvider(resource=res)
    tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))   # OTEL_EXPORTER_OTLP_ENDPOINT
    trace.set_tracer_provider(tp)
    reader = PeriodicExportingMetricReader(OTLPMetricExporter())
    metrics.set_meter_provider(MeterProvider(resource=res, metric_readers=[reader]))
    meter = metrics.get_meter(service_name)
    red = {
        "requests": meter.create_counter("http_requests_total"),
        "errors":   meter.create_counter("http_errors_total"),
        "latency":  meter.create_histogram("http_request_duration_ms"),
    }
    return trace.get_tracer(service_name), red
