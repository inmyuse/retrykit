"""Optional OpenTelemetry integration.

If ``opentelemetry-api`` is installed, retrykit automatically creates a span for
every attempt. If it is not installed, all helpers in this module become no-ops
so that core retrykit has zero required dependencies.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

try:  # pragma: no cover - exercised indirectly depending on environment
    from opentelemetry import trace as _otel_trace

    _tracer: Any | None = _otel_trace.get_tracer("retrykit")
    OTEL_AVAILABLE = True
except Exception:  # pragma: no cover - import guard
    _otel_trace = None  # type: ignore[assignment]
    _tracer = None
    OTEL_AVAILABLE = False


def is_available() -> bool:
    """Return ``True`` if OpenTelemetry is installed and spans will be created."""
    return OTEL_AVAILABLE


@contextmanager
def attempt_span(
    name: str,
    attempt: int,
    *,
    max_attempts: int | None = None,
) -> Iterator[None]:
    """Create a span for a single retry attempt.

    When OpenTelemetry is unavailable this is a transparent no-op context
    manager, so callers never need to branch on availability themselves.

    Args:
        name: The span name, typically the wrapped callable's qualified name.
        attempt: Zero-based attempt index, recorded as ``retry.attempt``.
        max_attempts: Optional total attempt budget, recorded as
            ``retry.max_attempts``.
    """
    if not OTEL_AVAILABLE or _tracer is None:
        yield
        return

    with _tracer.start_as_current_span(f"retry.attempt:{name}") as span:
        span.set_attribute("retry.attempt", attempt)
        if max_attempts is not None:
            span.set_attribute("retry.max_attempts", max_attempts)
        try:
            yield
        except BaseException as exc:  # noqa: BLE001 - record then re-raise
            span.set_attribute("retry.failed", True)
            span.record_exception(exc)
            raise
        else:
            span.set_attribute("retry.failed", False)


__all__: list[str] = ["OTEL_AVAILABLE", "is_available", "attempt_span"]
