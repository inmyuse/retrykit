"""Exceptions raised by retrykit."""

from __future__ import annotations


class RetrykitError(Exception):
    """Base class for all retrykit errors."""


class RetryError(RetrykitError):
    """Raised when all retry attempts have been exhausted.

    Attributes:
        attempts: The number of attempts that were made.
        last_exception: The exception raised by the final attempt, if any.
    """

    def __init__(self, attempts: int, last_exception: BaseException | None = None) -> None:
        self.attempts = attempts
        self.last_exception = last_exception
        message = f"Retry failed after {attempts} attempt(s)"
        if last_exception is not None:
            message += f": {last_exception!r}"
        super().__init__(message)


class CircuitOpenError(RetrykitError):
    """Raised when a call is attempted while the circuit breaker is OPEN.

    Attributes:
        retry_after: Approximate seconds until the circuit transitions to HALF_OPEN.
    """

    def __init__(self, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        message = "Circuit breaker is open"
        if retry_after is not None:
            message += f"; retry after {retry_after:.2f}s"
        super().__init__(message)


__all__: list[str] = ["RetrykitError", "RetryError", "CircuitOpenError"]
