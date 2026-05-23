"""Retry decorator and the ``Retrying`` context-manager / iterator API."""

from __future__ import annotations

import asyncio
import functools
import time
from collections.abc import Awaitable, Iterable, Sequence
from types import TracebackType
from typing import (
    Any,
    Callable,
    Optional,
    TypeVar,
    Union,
)

from .exceptions import RetryError
from .strategies import BackoffName, compute_delay
from .telemetry import attempt_span

T = TypeVar("T")

# An ``on`` entry may be an exception class or the string name of one.
OnSpec = Union[type[BaseException], str]
OnArg = Optional[Iterable[OnSpec]]

SyncSleep = Callable[[float], None]
AsyncSleep = Callable[[float], Awaitable[None]]


def _matches(exc: BaseException, on: Sequence[OnSpec] | None) -> bool:
    """Return ``True`` if ``exc`` should be retried given the ``on`` filter.

    ``on=None`` retries on any :class:`Exception`. Otherwise an entry matches
    when it is an exception class ``exc`` is an instance of, or a string equal
    to the name of any class in ``exc``'s method-resolution order.
    """
    if on is None:
        return isinstance(exc, Exception)
    for spec in on:
        if isinstance(spec, str):
            if any(klass.__name__ == spec for klass in type(exc).__mro__):
                return True
        elif isinstance(exc, spec):
            return True
    return False


class retry:  # noqa: N801 - public API is a decorator spelled lowercase
    """Decorator that retries a function on failure.

    Usable on both sync and async functions; the wrapper matches the wrapped
    function's nature automatically.

    Args:
        attempts: Maximum number of attempts (not retries). ``attempts=3`` calls
            the function up to three times.
        backoff: Backoff strategy: ``"fixed"``, ``"linear"`` or ``"exponential"``.
        delay: Base delay in seconds.
        max_delay: Maximum delay in seconds (before jitter).
        jitter: If ``True``, apply full jitter to each delay.
        on: Restrict retries to these exceptions. Each entry is an exception
            class or the string name of one. ``None`` retries on any ``Exception``.
        on_retry: Callback ``(attempt, error)`` invoked after each failed
            attempt that will be retried. ``attempt`` is the 1-based number of
            the attempt that just failed.

    Raises:
        RetryError: When all attempts are exhausted; the original exception is
            available as :attr:`RetryError.last_exception`.
    """

    def __init__(
        self,
        attempts: int = 3,
        *,
        backoff: BackoffName = "exponential",
        delay: float = 1.0,
        max_delay: float = 60.0,
        jitter: bool = False,
        on: OnArg = None,
        on_retry: Callable[[int, BaseException], None] | None = None,
        sleep: SyncSleep | None = None,
        async_sleep: AsyncSleep | None = None,
    ) -> None:
        if attempts < 1:
            raise ValueError("attempts must be >= 1")
        self.attempts = attempts
        self.backoff = backoff
        self.delay = delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.on: Sequence[OnSpec] | None = list(on) if on is not None else None
        self.on_retry = on_retry
        self._sleep: SyncSleep = sleep or time.sleep
        self._async_sleep: AsyncSleep = async_sleep or asyncio.sleep

    def _delay_for(self, failed_attempt: int) -> float:
        return compute_delay(
            failed_attempt - 1,
            backoff=self.backoff,
            delay=self.delay,
            max_delay=self.max_delay,
            jitter=self.jitter,
        )

    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        name = getattr(func, "__qualname__", getattr(func, "__name__", "callable"))

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                last_exc: BaseException | None = None
                for attempt in range(1, self.attempts + 1):
                    try:
                        with attempt_span(name, attempt, max_attempts=self.attempts):
                            return await func(*args, **kwargs)
                    except BaseException as exc:  # noqa: BLE001
                        if not _matches(exc, self.on):
                            raise
                        last_exc = exc
                        if attempt >= self.attempts:
                            break
                        if self.on_retry is not None:
                            self.on_retry(attempt, exc)
                        await self._async_sleep(self._delay_for(attempt))
                raise RetryError(self.attempts, last_exc)

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: BaseException | None = None
            for attempt in range(1, self.attempts + 1):
                try:
                    with attempt_span(name, attempt, max_attempts=self.attempts):
                        return func(*args, **kwargs)
                except BaseException as exc:  # noqa: BLE001
                    if not _matches(exc, self.on):
                        raise
                    last_exc = exc
                    if attempt >= self.attempts:
                        break
                    if self.on_retry is not None:
                        self.on_retry(attempt, exc)
                    self._sleep(self._delay_for(attempt))
            raise RetryError(self.attempts, last_exc)

        return sync_wrapper


class _Attempt:
    """A single attempt yielded by :class:`Retrying`.

    Used as ``with attempt:``. The block's exception (if any) is captured so the
    parent :class:`Retrying` can decide whether to retry.
    """

    def __init__(self, parent: Retrying, number: int) -> None:
        self._parent = parent
        self.number = number
        self._span = attempt_span(parent._name, number, max_attempts=parent.attempts)

    def __enter__(self) -> _Attempt:
        self._span.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        # Forward the outcome to the telemetry span first.
        self._span.__exit__(exc_type, exc, tb)
        parent = self._parent
        if exc is None:
            parent._succeeded = True
            return False
        if not _matches(exc, parent.on):
            return False  # propagate non-retryable errors immediately
        parent._last_exc = exc
        if self.number >= parent.attempts:
            raise RetryError(parent.attempts, exc)
        if parent.on_retry is not None:
            parent.on_retry(self.number, exc)
        parent._needs_sleep = True
        return True  # suppress; the loop will retry


class Retrying:
    """Context-manager / iterator form of :class:`retry`.

    Synchronous::

        with Retrying(attempts=3) as r:
            for attempt in r:
                with attempt:
                    result = call_api()

    Asynchronous::

        async with Retrying(attempts=3, backoff="exponential") as r:
            async for attempt in r:
                with attempt:
                    result = await call_api()

    Accepts the same options as :class:`retry`.
    """

    def __init__(
        self,
        attempts: int = 3,
        *,
        backoff: BackoffName = "exponential",
        delay: float = 1.0,
        max_delay: float = 60.0,
        jitter: bool = False,
        on: OnArg = None,
        on_retry: Callable[[int, BaseException], None] | None = None,
        name: str = "Retrying",
        sleep: SyncSleep | None = None,
        async_sleep: AsyncSleep | None = None,
    ) -> None:
        if attempts < 1:
            raise ValueError("attempts must be >= 1")
        self.attempts = attempts
        self.backoff = backoff
        self.delay = delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.on: Sequence[OnSpec] | None = list(on) if on is not None else None
        self.on_retry = on_retry
        self._name = name
        self._sleep: SyncSleep = sleep or time.sleep
        self._async_sleep: AsyncSleep = async_sleep or asyncio.sleep

        self._attempt = 0
        self._succeeded = False
        self._needs_sleep = False
        self._last_exc: BaseException | None = None

    def _delay_for(self, failed_attempt: int) -> float:
        return compute_delay(
            failed_attempt - 1,
            backoff=self.backoff,
            delay=self.delay,
            max_delay=self.max_delay,
            jitter=self.jitter,
        )

    # -- sync protocol ----------------------------------------------------

    def __enter__(self) -> Retrying:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        return None

    def __iter__(self) -> Retrying:
        return self

    def __next__(self) -> _Attempt:
        if self._succeeded:
            raise StopIteration
        if self._needs_sleep:
            self._needs_sleep = False
            self._sleep(self._delay_for(self._attempt))
        self._attempt += 1
        return _Attempt(self, self._attempt)

    # -- async protocol ---------------------------------------------------

    async def __aenter__(self) -> Retrying:
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        return None

    def __aiter__(self) -> Retrying:
        return self

    async def __anext__(self) -> _Attempt:
        if self._succeeded:
            raise StopAsyncIteration
        if self._needs_sleep:
            self._needs_sleep = False
            await self._async_sleep(self._delay_for(self._attempt))
        self._attempt += 1
        return _Attempt(self, self._attempt)


__all__: list[str] = ["retry", "Retrying", "RetryError"]
