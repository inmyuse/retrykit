"""Tests for the circuit breaker state machine (sync and async)."""

from __future__ import annotations

import pytest

from retrykit import CircuitBreaker, CircuitOpenError, CircuitState, circuit_breaker


class Boom(Exception):
    pass


class FakeClock:
    """A controllable monotonic time source."""

    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def test_opens_after_threshold_failures() -> None:
    clock = FakeClock()
    opened: list[bool] = []
    cb = CircuitBreaker(threshold=3, timeout=10, on_open=lambda: opened.append(True), time_source=clock)

    def fail() -> None:
        raise Boom()

    for _ in range(3):
        with pytest.raises(Boom):
            cb.call(fail)

    assert cb.state is CircuitState.OPEN
    assert opened == [True]


def test_open_circuit_rejects_calls() -> None:
    clock = FakeClock()
    cb = CircuitBreaker(threshold=1, timeout=10, time_source=clock)

    with pytest.raises(Boom):
        cb.call(lambda: (_ for _ in ()).throw(Boom()))
    assert cb.state is CircuitState.OPEN

    with pytest.raises(CircuitOpenError) as info:
        cb.call(lambda: "never")
    assert info.value.retry_after == pytest.approx(10.0)


def test_half_open_after_timeout_then_closes_on_success() -> None:
    clock = FakeClock()
    closed: list[bool] = []
    cb = CircuitBreaker(
        threshold=1, timeout=5, on_close=lambda: closed.append(True), time_source=clock
    )

    with pytest.raises(Boom):
        cb.call(lambda: (_ for _ in ()).throw(Boom()))
    assert cb.state is CircuitState.OPEN

    clock.advance(5)
    assert cb.state is CircuitState.HALF_OPEN

    assert cb.call(lambda: "recovered") == "recovered"
    assert cb.state is CircuitState.CLOSED
    assert closed == [True]


def test_half_open_failure_reopens() -> None:
    clock = FakeClock()
    cb = CircuitBreaker(threshold=1, timeout=5, time_source=clock)

    with pytest.raises(Boom):
        cb.call(lambda: (_ for _ in ()).throw(Boom()))
    clock.advance(5)
    assert cb.state is CircuitState.HALF_OPEN

    with pytest.raises(Boom):
        cb.call(lambda: (_ for _ in ()).throw(Boom()))
    assert cb.state is CircuitState.OPEN


def test_success_resets_failure_count() -> None:
    cb = CircuitBreaker(threshold=3)
    with pytest.raises(Boom):
        cb.call(lambda: (_ for _ in ()).throw(Boom()))
    assert cb.failure_count == 1
    cb.call(lambda: "ok")
    assert cb.failure_count == 0
    assert cb.state is CircuitState.CLOSED


def test_reset_forces_closed() -> None:
    cb = CircuitBreaker(threshold=1)
    with pytest.raises(Boom):
        cb.call(lambda: (_ for _ in ()).throw(Boom()))
    assert cb.state is CircuitState.OPEN
    cb.reset()
    assert cb.state is CircuitState.CLOSED


def test_decorator_sync() -> None:
    @circuit_breaker(threshold=2, timeout=10)
    def fn(x: int) -> int:
        if x < 0:
            raise Boom()
        return x

    assert fn(1) == 1
    with pytest.raises(Boom):
        fn(-1)
    with pytest.raises(Boom):
        fn(-1)
    assert fn.breaker.state is CircuitState.OPEN
    with pytest.raises(CircuitOpenError):
        fn(1)


async def test_async_breaker_opens_and_recovers() -> None:
    clock = FakeClock()

    @circuit_breaker(threshold=2, timeout=5)
    async def fn(ok: bool) -> str:
        if not ok:
            raise Boom()
        return "ok"

    # Swap in the deterministic clock on the attached breaker.
    fn.breaker._now = clock

    with pytest.raises(Boom):
        await fn(False)
    with pytest.raises(Boom):
        await fn(False)
    assert fn.breaker.state is CircuitState.OPEN

    with pytest.raises(CircuitOpenError):
        await fn(True)

    clock.advance(5)
    assert fn.breaker.state is CircuitState.HALF_OPEN
    assert await fn(True) == "ok"
    assert fn.breaker.state is CircuitState.CLOSED


def test_invalid_config_rejected() -> None:
    with pytest.raises(ValueError):
        CircuitBreaker(threshold=0)
    with pytest.raises(ValueError):
        CircuitBreaker(threshold=1, timeout=-1)
