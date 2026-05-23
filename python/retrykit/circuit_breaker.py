"""Circuit breaker implementation.

State machine::

    CLOSED  --(failures >= threshold)-->  OPEN
    OPEN    --(timeout elapsed)--------->  HALF_OPEN
    HALF_OPEN --(trial succeeds)-------->  CLOSED
    HALF_OPEN --(trial fails)----------->  OPEN

The breaker is usable three ways:

* As a decorator: ``@circuit_breaker(threshold=5, timeout=30)``.
* As a standalone object: ``cb = CircuitBreaker(...); cb.call(fn)`` /
  ``await cb.call_async(fn)``.
* Composed beneath ``@retry`` (see :mod:`retrykit.retry`).

Sync state mutations are guarded by a :class:`threading.Lock`; async mutations
by an :class:`asyncio.Lock`, so a single breaker is safe to share across threads
*or* coroutines.
"""

from __future__ import annotations

import asyncio
import functools
import threading
import time
from collections.abc import Awaitable
from enum import Enum
from typing import (
    Any,
    Callable,
    TypeVar,
    cast,
)

from .exceptions import CircuitOpenError

T = TypeVar("T")
SyncFunc = Callable[..., T]
AsyncFunc = Callable[..., Awaitable[T]]


class CircuitState(str, Enum):
    """The three states of a circuit breaker."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """A circuit breaker that trips after repeated failures.

    Args:
        threshold: Number of consecutive failures that trips the breaker OPEN.
        timeout: Seconds the breaker stays OPEN before allowing a HALF_OPEN
            trial call.
        on_open: Optional zero-argument callback invoked when the breaker opens.
        on_close: Optional zero-argument callback invoked when the breaker
            recovers and closes.
        time_source: Callable returning the current monotonic time in seconds;
            injectable for deterministic tests. Defaults to :func:`time.monotonic`.
    """

    def __init__(
        self,
        threshold: int = 5,
        timeout: float = 30.0,
        *,
        on_open: Callable[[], None] | None = None,
        on_close: Callable[[], None] | None = None,
        time_source: Callable[[], float] = time.monotonic,
    ) -> None:
        if threshold < 1:
            raise ValueError("threshold must be >= 1")
        if timeout < 0:
            raise ValueError("timeout must be >= 0")

        self.threshold = threshold
        self.timeout = timeout
        self._on_open = on_open
        self._on_close = on_close
        self._now = time_source

        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at: float | None = None
        self._lock = threading.Lock()
        self._async_lock = asyncio.Lock()

    # -- introspection ----------------------------------------------------

    @property
    def state(self) -> CircuitState:
        """The current state, accounting for an elapsed OPEN timeout."""
        with self._lock:
            self._maybe_half_open()
            return self._state

    @property
    def failure_count(self) -> int:
        """Number of consecutive failures currently recorded."""
        with self._lock:
            return self._failures

    def reset(self) -> None:
        """Force the breaker back to a clean CLOSED state."""
        with self._lock:
            self._to_closed()

    # -- internal transitions (must hold a lock) --------------------------

    def _maybe_half_open(self) -> None:
        if (
            self._state is CircuitState.OPEN
            and self._opened_at is not None
            and (self._now() - self._opened_at) >= self.timeout
        ):
            self._state = CircuitState.HALF_OPEN

    def _to_closed(self) -> None:
        was_open = self._state is not CircuitState.CLOSED
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at = None
        if was_open and self._on_close is not None:
            self._on_close()

    def _to_open(self) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = self._now()
        if self._on_open is not None:
            self._on_open()

    def _before_call(self) -> None:
        """Raise if the call is not currently permitted."""
        self._maybe_half_open()
        if self._state is CircuitState.OPEN:
            retry_after = None
            if self._opened_at is not None:
                retry_after = max(0.0, self.timeout - (self._now() - self._opened_at))
            raise CircuitOpenError(retry_after=retry_after)

    def _on_success(self) -> None:
        if self._state is CircuitState.HALF_OPEN:
            self._to_closed()
        else:
            self._failures = 0

    def _on_failure(self) -> None:
        if self._state is CircuitState.HALF_OPEN:
            # A failed trial sends us straight back to OPEN.
            self._to_open()
            return
        self._failures += 1
        if self._failures >= self.threshold:
            self._to_open()

    # -- execution --------------------------------------------------------

    def call(self, func: SyncFunc[T], *args: Any, **kwargs: Any) -> T:
        """Execute a synchronous callable through the breaker."""
        with self._lock:
            self._before_call()
        try:
            result = func(*args, **kwargs)
        except BaseException:
            with self._lock:
                self._on_failure()
            raise
        with self._lock:
            self._on_success()
        return result

    async def call_async(self, func: AsyncFunc[T], *args: Any, **kwargs: Any) -> T:
        """Execute an async callable through the breaker."""
        async with self._async_lock:
            self._before_call()
        try:
            result = await func(*args, **kwargs)
        except BaseException:
            async with self._async_lock:
                self._on_failure()
            raise
        async with self._async_lock:
            self._on_success()
        return result

    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Use the breaker instance directly as a decorator."""
        return _wrap(self, func)


def circuit_breaker(
    threshold: int = 5,
    timeout: float = 30.0,
    *,
    on_open: Callable[[], None] | None = None,
    on_close: Callable[[], None] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator factory that wraps a function with a fresh circuit breaker.

    Works transparently on both sync and async functions. The created
    :class:`CircuitBreaker` is attached to the wrapper as ``.breaker`` for
    introspection.

    Example:
        >>> @circuit_breaker(threshold=5, timeout=30)
        ... async def call_stripe(): ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        breaker = CircuitBreaker(
            threshold=threshold,
            timeout=timeout,
            on_open=on_open,
            on_close=on_close,
        )
        return _wrap(breaker, func)

    return decorator


def _wrap(breaker: CircuitBreaker, func: Callable[..., Any]) -> Callable[..., Any]:
    if asyncio.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            return await breaker.call_async(
                cast(AsyncFunc[Any], func), *args, **kwargs
            )

        async_wrapper.breaker = breaker  # type: ignore[attr-defined]
        return async_wrapper

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        return breaker.call(func, *args, **kwargs)

    sync_wrapper.breaker = breaker  # type: ignore[attr-defined]
    return sync_wrapper


__all__: list[str] = ["CircuitState", "CircuitBreaker", "circuit_breaker"]
