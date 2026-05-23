"""Tests that OpenTelemetry spans are emitted when OTel is available."""

from __future__ import annotations

import pytest

from retrykit import RetryError, retry
from retrykit import telemetry

otel_sdk = pytest.importorskip("opentelemetry.sdk.trace")
from opentelemetry import trace  # noqa: E402
from opentelemetry.sdk.trace import TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E402
    InMemorySpanExporter,
)


_EXPORTER = InMemorySpanExporter()
_PROVIDER = TracerProvider()
_PROVIDER.add_span_processor(SimpleSpanProcessor(_EXPORTER))
trace.set_tracer_provider(_PROVIDER)


@pytest.fixture()
def span_exporter() -> InMemorySpanExporter:
    # The global TracerProvider can only be installed once, so reuse it and
    # rebind retrykit's tracer to it, clearing any spans from prior tests.
    telemetry._tracer = _PROVIDER.get_tracer("retrykit")
    _EXPORTER.clear()
    return _EXPORTER


def test_otel_is_available() -> None:
    assert telemetry.is_available() is True


def test_spans_created_per_attempt(span_exporter: InMemorySpanExporter) -> None:
    @retry(attempts=3, sleep=lambda _d: None)
    def fn() -> None:
        raise ValueError("boom")

    with pytest.raises(RetryError):
        fn()

    spans = span_exporter.get_finished_spans()
    assert len(spans) == 3
    for span in spans:
        assert span.name.startswith("retry.attempt:")
        assert span.attributes is not None
        assert span.attributes["retry.max_attempts"] == 3
        assert span.attributes["retry.failed"] is True


def test_span_marks_success(span_exporter: InMemorySpanExporter) -> None:
    @retry(attempts=2, sleep=lambda _d: None)
    def fn() -> str:
        return "ok"

    assert fn() == "ok"
    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].attributes is not None
    assert spans[0].attributes["retry.failed"] is False
