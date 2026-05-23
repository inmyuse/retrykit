"""retrykit — retry logic and circuit breakers with an identical API in Python and TypeScript.

Public API:
    retry            Decorator that retries a function on failure.
    Retrying         Context-manager / iterator form of ``retry``.
    circuit_breaker  Decorator that wraps a function with a circuit breaker.
    CircuitBreaker   Standalone circuit breaker object.
    CircuitState     Enum of breaker states (CLOSED / OPEN / HALF_OPEN).
    RetryError       Raised when all attempts are exhausted.
    CircuitOpenError Raised when calling through an open circuit.
"""

from __future__ import annotations

from .circuit_breaker import CircuitBreaker, CircuitState, circuit_breaker
from .exceptions import CircuitOpenError, RetryError, RetrykitError
from .retry import Retrying, retry
from .strategies import compute_delay

__version__ = "0.1.0"

__all__: list[str] = [
    "retry",
    "Retrying",
    "circuit_breaker",
    "CircuitBreaker",
    "CircuitState",
    "RetryError",
    "CircuitOpenError",
    "RetrykitError",
    "compute_delay",
    "__version__",
]
