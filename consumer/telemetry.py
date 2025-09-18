import os
from dotenv import load_dotenv
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

# Service and OTLP endpoint configuration
environment_service = "Inferno"
environment_endpoint = "http://jaeger:4318/v1/traces"

# Initialize tracer provider with resource
tp = TracerProvider(resource=Resource.create({"service.name": environment_service}))
tp.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
tp.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=environment_endpoint)))
trace.set_tracer_provider(tp)

# Expose tracer and provider
tracer = trace.get_tracer(__name__)
provider = tp