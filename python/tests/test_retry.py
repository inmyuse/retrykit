"""Tests for the retry decorator and Retrying context manager."""

from __future__ import annotations

import asyncio
from typing import List

import pytest

from retrykit import RetryError, Retrying, retry


class Boom(Exception):
    pass


class Other(Exception):
    pass


# -- sync ----------------------------------------------------------------


def test_sync_succeeds_first_try() -> None:
    calls = 0

    @retry(attempts=3, sleep=lambda _d: None)
    def fn() -> str:
        nonlocal calls
        calls += 1
        return "ok"

    assert fn() == "ok"
    assert calls == 1


def test_sync_retries_then_succeeds() -> None:
    calls = 0

    @retry(attempts=3, sleep=lambda _d: None)
    def fn() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise Boom("nope")
        return "ok"

    assert fn() == "ok"
    assert calls == 3


def test_sync_exhausts_and_raises_retry_error() -> None:
    calls = 0

    @retry(attempts=3, sleep=lambda _d: None)
    def fn() -> None:
        nonlocal calls
        calls += 1
        raise Boom("always")

    with pytest.raises(RetryError) as info:
        fn()
    assert calls == 3
    assert info.value.attempts == 3
    assert isinstance(info.value.last_exception, Boom)


def test_sync_delays_follow_backoff() -> None:
    delays: List[float] = []

    @retry(attempts=4, backoff="exponential", delay=1.0, sleep=delays.append)
    def fn() -> None:
        raise Boom()

    with pytest.raises(RetryError):
        fn()
    # Waits happen after attempts 1, 2, 3 -> indices 0, 1, 2.
    assert delays == [1.0, 2.0, 4.0]


def test_on_filter_skips_unlisted_exceptions() -> None:
    calls = 0

    @retry(attempts=5, on=[Boom], sleep=lambda _d: None)
    def fn() -> None:
        nonlocal calls
        calls += 1
        raise Other("not retried")

    with pytest.raises(Other):
        fn()
    assert calls == 1


def test_on_filter_accepts_string_names() -> None:
    calls = 0

    @retry(attempts=3, on=["Boom"], sleep=lambda _d: None)
    def fn() -> None:
        nonlocal calls
        calls += 1
        raise Boom()

    with pytest.raises(RetryError):
        fn()
    assert calls == 3


def test_on_retry_callback_receives_attempt_and_error() -> None:
    seen: List[tuple[int, str]] = []

    @retry(
        attempts=3,
        sleep=lambda _d: None,
        on_retry=lambda attempt, error: seen.append((attempt, type(error).__name__)),
    )
    def fn() -> None:
        raise Boom()

    with pytest.raises(RetryError):
        fn()
    assert seen == [(1, "Boom"), (2, "Boom")]


# -- async ---------------------------------------------------------------


async def test_async_retries_then_succeeds() -> None:
    calls = 0

    @retry(attempts=3, async_sleep=lambda _d: asyncio.sleep(0))
    async def fn() -> str:
        nonlocal calls
        calls += 1
        if calls < 2:
            raise Boom()
        return "ok"

    assert await fn() == "ok"
    assert calls == 2


async def test_async_exhausts() -> None:
    recorded: List[float] = []

    async def fake_sleep(d: float) -> None:
        recorded.append(d)

    @retry(attempts=3, backoff="fixed", delay=0.5, async_sleep=fake_sleep)
    async def fn() -> None:
        raise Boom()

    with pytest.raises(RetryError):
        await fn()
    assert recorded == [0.5, 0.5]


# -- Retrying context manager --------------------------------------------


def test_retrying_sync_iterator() -> None:
    calls = 0
    result = None
    with Retrying(attempts=3, sleep=lambda _d: None) as r:
        for attempt in r:
            with attempt:
                calls += 1
                if calls < 2:
                    raise Boom()
                result = "ok"
    assert result == "ok"
    assert calls == 2


def test_retrying_sync_exhausts_raises_retry_error() -> None:
    with pytest.raises(RetryError):
        with Retrying(attempts=2, sleep=lambda _d: None) as r:
            for attempt in r:
                with attempt:
                    raise Boom()


def test_retrying_sync_non_retryable_propagates() -> None:
    with pytest.raises(Other):
        with Retrying(attempts=3, on=[Boom], sleep=lambda _d: None) as r:
            for attempt in r:
                with attempt:
                    raise Other()


async def test_retrying_async_iterator() -> None:
    calls = 0
    result = None
    async with Retrying(attempts=3, async_sleep=lambda _d: asyncio.sleep(0)) as r:
        async for attempt in r:
            with attempt:
                calls += 1
                if calls < 3:
                    raise Boom()
                result = "ok"
    assert result == "ok"
    assert calls == 3


def test_invalid_attempts_rejected() -> None:
    with pytest.raises(ValueError):
        retry(attempts=0)
    with pytest.raises(ValueError):
        Retrying(attempts=0)
