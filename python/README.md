# retrykit (Python)

Retry logic and circuit breakers with an identical API in Python and TypeScript.

- ✅ `@retry` decorator and `Retrying` context manager
- ✅ Built-in circuit breaker (`CLOSED → OPEN → HALF_OPEN → CLOSED`)
- ✅ Sync **and** async, transparently
- ✅ Automatic OpenTelemetry spans when `opentelemetry-api` is installed
- ✅ Zero required dependencies, fully typed (`py.typed`)

## Install

```bash
pip install retrykit
# with OpenTelemetry spans:
pip install "retrykit[otel]"
```

## Quick start

```python
from retrykit import retry

@retry(attempts=3)
async def call_api() -> str:
    ...
```

### Full options

```python
@retry(
    attempts=5,
    backoff="exponential",   # "fixed" | "linear" | "exponential"
    delay=1.0,               # base delay in seconds
    max_delay=60.0,
    jitter=True,             # full jitter to avoid thundering herd
    on=["HTTPError", "TimeoutError"],  # retry only on these (class or name)
    on_retry=lambda attempt, error: print(f"Retry {attempt}: {error}"),
)
async def call_openai(prompt: str) -> str:
    ...
```

### Circuit breaker

```python
from retrykit import circuit_breaker, CircuitBreaker, CircuitOpenError

@circuit_breaker(threshold=5, timeout=30, on_open=lambda: print("opened!"))
async def call_stripe(): ...

# Or standalone:
breaker = CircuitBreaker(threshold=5, timeout=30)
result = breaker.call(do_work)          # sync
result = await breaker.call_async(work) # async
print(breaker.state)                    # CircuitState.CLOSED / OPEN / HALF_OPEN
```

### Composable

```python
@retry(attempts=3, backoff="exponential")
@circuit_breaker(threshold=5, timeout=30)
async def resilient_call(): ...
```

### Context-manager style

```python
from retrykit import Retrying

async with Retrying(attempts=3, backoff="exponential") as r:
    async for attempt in r:
        with attempt:
            result = await call_api()
```

The sync form is identical without the `async` keywords:

```python
with Retrying(attempts=3) as r:
    for attempt in r:
        with attempt:
            result = call_api()
```

## API reference

### `retry(attempts=3, *, backoff="exponential", delay=1.0, max_delay=60.0, jitter=False, on=None, on_retry=None)`

Decorator. Retries up to `attempts` times. Raises `RetryError` (with
`.last_exception`) when exhausted. `on` accepts exception classes or their
string names; `None` retries on any `Exception`.

### `Retrying(...)`

Same options as `retry`; usable as a sync or async context manager / iterator.

### `circuit_breaker(threshold=5, timeout=30, *, on_open=None, on_close=None)`

Decorator. The underlying `CircuitBreaker` is exposed on the wrapped function as
`.breaker`. Raises `CircuitOpenError` while open.

### `CircuitBreaker(threshold=5, timeout=30.0, *, on_open=None, on_close=None)`

`.call(fn, *a, **kw)`, `await .call_async(fn, *a, **kw)`, `.state`,
`.failure_count`, `.reset()`.

## OpenTelemetry

If `opentelemetry-api` is importable, every attempt is wrapped in a span named
`retry.attempt:<func>` with attributes `retry.attempt`, `retry.max_attempts`,
and `retry.failed`. If it is not installed, span creation is silently skipped —
no configuration required.

## Development

```bash
pip install -e ".[dev]"
pytest --cov=retrykit
mypy
ruff check retrykit
```

## License

MIT
