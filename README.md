# retrykit

> Retry logic and circuit breakers with an **identical API in Python and TypeScript**.

[![PyPI version](https://img.shields.io/pypi/v/retrykit_lib?label=pypi)](https://pypi.org/project/retrykit-lib/)
[![npm version](https://img.shields.io/npm/v/retrykit?label=npm)](https://www.npmjs.com/package/retrykit)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)
[![Coverage](https://img.shields.io/badge/coverage-%3E90%25-brightgreen.svg)](#)

retrykit gives you retries, backoff, jitter and a real circuit breaker behind
one mental model — write it once, and the Python and TypeScript versions read
the same. OpenTelemetry spans are emitted automatically when available, and the
core has **zero required dependencies** in both languages.

## Why retrykit?

| Feature              | retrykit | tenacity | p-retry | async-retry |
|----------------------|----------|----------|---------|-------------|
| Python               | ✅       | ✅       | ❌      | ❌          |
| TypeScript           | ✅       | ❌       | ✅      | ✅          |
| Circuit breaker      | ✅       | ❌       | ❌      | ❌          |
| OpenTelemetry        | ✅       | ❌       | ❌      | ❌          |
| Identical API        | ✅       | ❌       | ❌      | ❌          |
| Zero dependencies    | ✅       | ❌       | ✅      | ✅          |
| Async/sync           | ✅       | ✅       | ✅      | ✅          |

retrykit is the only option that combines a **built-in circuit breaker**,
**automatic OpenTelemetry spans**, and a **single API across Python and
TypeScript**.

## Installation

```bash
pip install retrykit_lib   # Python  (import as `retrykit`)
npm install retrykit       # TypeScript / JavaScript
```

OpenTelemetry is optional: `pip install "retrykit_lib[otel]"` or
`npm install @opentelemetry/api`.

## Quick start — same use case, both languages

<table>
<tr><th>Python</th><th>TypeScript</th></tr>
<tr>
<td>

```python
from retrykit import retry

@retry(
    attempts=5,
    backoff="exponential",
    delay=1.0,          # seconds
    jitter=True,
)
async def fetch(url: str) -> dict:
    return await http_get(url)
```

</td>
<td>

```ts
import { withRetry } from 'retrykit';

const data = await withRetry(
  () => httpGet(url),
  {
    attempts: 5,
    backoff: 'exponential',
    delay: 1000,        // milliseconds
    jitter: true,
  },
);
```

</td>
</tr>
</table>

The only intentional difference: **Python uses seconds, TypeScript uses
milliseconds**, following each ecosystem's convention. Every option name and
backoff strategy is otherwise identical.

## Real-world example: resilient OpenAI calls

Retry transient failures *and* stop hammering the API once it is clearly down,
with a circuit breaker underneath the retry loop.

<table>
<tr><th>Python</th><th>TypeScript</th></tr>
<tr>
<td>

```python
from retrykit import (
    retry, circuit_breaker,
    RetryError, CircuitOpenError,
)

@retry(
    attempts=4,
    backoff="exponential",
    delay=1.0,
    max_delay=20.0,
    jitter=True,
    on=["APITimeoutError", "RateLimitError"],
    on_retry=lambda n, e: log.warning(
        "retry %s: %r", n, e),
)
@circuit_breaker(
    threshold=5,
    timeout=30,
    on_open=lambda: log.error("OpenAI circuit open"),
)
async def ask(prompt: str) -> str:
    resp = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content

try:
    answer = await ask("Hello!")
except CircuitOpenError:
    answer = "Service temporarily unavailable."
except RetryError as e:
    answer = f"Failed after retries: {e.last_exception}"
```

</td>
<td>

```ts
import {
  withRetry, createCircuitBreaker,
  RetryError, CircuitOpenError,
} from 'retrykit';

const breaker = createCircuitBreaker({
  threshold: 5,
  timeout: 30_000,
  onOpen: () => log.error('OpenAI circuit open'),
});

async function ask(prompt: string): Promise<string> {
  return withRetry(
    () => breaker.execute(async () => {
      const resp = await client.chat.completions.create({
        model: 'gpt-4o',
        messages: [{ role: 'user', content: prompt }],
      });
      return resp.choices[0].message.content;
    }),
    {
      attempts: 4,
      backoff: 'exponential',
      delay: 1000,
      maxDelay: 20_000,
      jitter: true,
      on: ['APITimeoutError', 'RateLimitError'],
      onRetry: (n, e) => log.warn(`retry ${n}:`, e),
    },
  );
}

try {
  var answer = await ask('Hello!');
} catch (e) {
  if (e instanceof CircuitOpenError)
    answer = 'Service temporarily unavailable.';
  else if (e instanceof RetryError)
    answer = `Failed after retries: ${e.lastError}`;
  else throw e;
}
```

</td>
</tr>
</table>

## API reference

### Retry options (shared)

| Option      | Python default | TypeScript default | Meaning                                   |
|-------------|----------------|--------------------|-------------------------------------------|
| `attempts`  | `3`            | `3`                | Max attempts (not retries).               |
| `backoff`   | `"exponential"`| `'exponential'`    | `fixed` \| `linear` \| `exponential`.     |
| `delay`     | `1.0` (s)      | `1000` (ms)        | Base delay.                               |
| `max_delay` / `maxDelay` | `60.0` (s) | `60000` (ms) | Cap applied before jitter.          |
| `jitter`    | `False`        | `false`            | Full jitter: random in `[0, delay]`.      |
| `on`        | `None`         | `undefined`        | Restrict retries to these errors.         |
| `on_retry` / `onRetry`   | `None`     | `undefined`     | Callback `(attempt, error)`.           |

**Backoff math** (attempt index is 0-based): `fixed` → `delay`; `linear` →
`delay × (n + 1)`; `exponential` → `delay × 2ⁿ`, all capped at the max. With
jitter, the actual wait is uniformly random between `0` and the capped value.

### Python

```python
from retrykit import (
    retry, Retrying, circuit_breaker, CircuitBreaker, CircuitState,
    RetryError, CircuitOpenError,
)

@retry(attempts=3)              # decorator, sync or async
async def f(): ...

with Retrying(attempts=3) as r: # context-manager / iterator form
    for attempt in r:
        with attempt:
            do_work()

@circuit_breaker(threshold=5, timeout=30)
async def g(): ...

cb = CircuitBreaker(threshold=5, timeout=30)
cb.call(fn)                     # sync
await cb.call_async(fn)         # async
cb.state                        # CircuitState.CLOSED / OPEN / HALF_OPEN
```

See [python/README.md](./python/README.md) for full details.

### TypeScript

```ts
import {
  withRetry, retry, createCircuitBreaker, CircuitBreaker,
  RetryError, CircuitOpenError,
} from 'retrykit';

const x = await withRetry<number>(() => compute(), { attempts: 3 });

class Client {
  @retry({ attempts: 3 })       // decorator (experimentalDecorators)
  async f() { /* ... */ }
}

const cb = createCircuitBreaker({ threshold: 5, timeout: 30_000 });
await cb.execute(() => callApi());
cb.state;                       // 'CLOSED' | 'OPEN' | 'HALF_OPEN'
```

See [typescript/README.md](./typescript/README.md) for full details.

## Circuit breaker state machine

```
CLOSED  ──(failures ≥ threshold)──▶  OPEN
OPEN    ──(timeout elapsed)───────▶  HALF_OPEN
HALF_OPEN ──(trial succeeds)──────▶  CLOSED
HALF_OPEN ──(trial fails)─────────▶  OPEN
```

## OpenTelemetry

When OpenTelemetry is available, every attempt is wrapped in a span named
`retry.attempt:<fn>` carrying `retry.attempt`, `retry.max_attempts` and
`retry.failed`. If it isn't configured, span creation is skipped at zero cost —
no code changes required.

## License

[MIT](./LICENSE)
