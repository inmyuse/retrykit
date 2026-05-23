"""Tests for backoff strategies with exact timing assertions."""

from __future__ import annotations

import random

import pytest

from retrykit.strategies import compute_delay


def test_fixed_backoff_is_constant() -> None:
    for attempt in range(5):
        assert compute_delay(attempt, backoff="fixed", delay=2.0) == 2.0


def test_linear_backoff_scales_with_attempt() -> None:
    assert compute_delay(0, backoff="linear", delay=1.5) == 1.5
    assert compute_delay(1, backoff="linear", delay=1.5) == 3.0
    assert compute_delay(2, backoff="linear", delay=1.5) == 4.5


def test_exponential_backoff_doubles() -> None:
    assert compute_delay(0, backoff="exponential", delay=1.0) == 1.0
    assert compute_delay(1, backoff="exponential", delay=1.0) == 2.0
    assert compute_delay(2, backoff="exponential", delay=1.0) == 4.0
    assert compute_delay(3, backoff="exponential", delay=1.0) == 8.0


def test_max_delay_caps_value() -> None:
    assert compute_delay(10, backoff="exponential", delay=1.0, max_delay=5.0) == 5.0
    assert compute_delay(100, backoff="linear", delay=10.0, max_delay=15.0) == 15.0


def test_full_jitter_stays_within_bounds() -> None:
    rng = random.Random(1234)
    for attempt in range(6):
        capped = compute_delay(attempt, backoff="exponential", delay=1.0, max_delay=30.0)
        jittered = compute_delay(
            attempt, backoff="exponential", delay=1.0, max_delay=30.0, jitter=True, rng=rng
        )
        assert 0.0 <= jittered <= capped


def test_jitter_is_deterministic_with_seeded_rng() -> None:
    a = compute_delay(3, backoff="exponential", jitter=True, rng=random.Random(42))
    b = compute_delay(3, backoff="exponential", jitter=True, rng=random.Random(42))
    assert a == b


def test_negative_attempt_rejected() -> None:
    with pytest.raises(ValueError):
        compute_delay(-1)


def test_unknown_strategy_rejected() -> None:
    with pytest.raises(ValueError):
        compute_delay(0, backoff="quadratic")  # type: ignore[arg-type]
