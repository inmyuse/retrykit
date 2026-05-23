"""Backoff strategies for computing the delay between retry attempts."""

from __future__ import annotations

import random
from typing import Literal

BackoffName = Literal["fixed", "linear", "exponential"]


def compute_delay(
    attempt: int,
    *,
    backoff: BackoffName = "exponential",
    delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = False,
    rng: random.Random | None = None,
) -> float:
    """Compute the delay (in seconds) to wait before a given retry attempt.

    Args:
        attempt: Zero-based index of the *upcoming* wait. ``0`` is the wait
            after the first failed attempt, ``1`` after the second, and so on.
        backoff: The backoff strategy. One of ``"fixed"``, ``"linear"`` or
            ``"exponential"``.
        delay: The base delay in seconds.
        max_delay: Upper bound applied to the computed delay before jitter.
        jitter: If ``True``, apply *full jitter*: the returned value is a random
            number between ``0`` and the computed (capped) delay.
        rng: Optional :class:`random.Random` instance, mainly for deterministic
            tests. Defaults to the module-global random source.

    Returns:
        The number of seconds to sleep before the next attempt.

    Raises:
        ValueError: If ``backoff`` is not a recognised strategy.
    """
    if attempt < 0:
        raise ValueError("attempt must be >= 0")

    if backoff == "fixed":
        raw = delay
    elif backoff == "linear":
        raw = delay * (attempt + 1)
    elif backoff == "exponential":
        raw = delay * (2 ** attempt)
    else:  # pragma: no cover - guarded by typing, defensive for runtime callers
        raise ValueError(f"Unknown backoff strategy: {backoff!r}")

    capped = min(raw, max_delay)

    if jitter:
        source = rng if rng is not None else random
        return source.uniform(0.0, capped)

    return capped


__all__: list[str] = ["BackoffName", "compute_delay"]
