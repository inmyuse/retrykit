# retrykit (TypeScript)

Retry logic and circuit breakers with an identical API in Python and TypeScript.

- ✅ Functional `withRetry()` and `@retry` / `@circuitBreaker` decorators
- ✅ Built-in circuit breaker (`CLOSED → OPEN → HALF_OPEN → CLOSED`)
- ✅ Fully typed generics — `withRetry<T>()` returns `Promise<T>`, no `any`
- ✅ Automatic OpenTelemetry spans when an OTel provider is configured
- ✅ Zero runtime dependencies; ESM + CJS; works on Node 18+, Deno, Bun, browser

## Install

```bash
npm install retrykit
```

`@opentelemetry/api` is an optional peer dependency — install it only if you
want spans.

## Quick start

```ts
import { withRetry } from 'retrykit';

const data = await withRetry(() => fetch(url).then((r) => r.json()), {
  attempts: 3,
});
```

### Full options

```ts
const result = await withRetry(
  () => fetch('https://api.openai.com/v1/chat/completions', { /* ... */ }),
  {
    attempts: 5,
    backoff: 'exponential',   // 'fixed' | 'linear' | 'exponential'
    delay: 1000,              // base delay in milliseconds
    maxDelay: 60_000,
    jitter: true,             // full jitter to avoid thundering herd
    on: [TypeError, SyntaxError], // retry only on these (constructors or names)
    onRetry: (attempt, error) => console.log(`Retry ${attempt}:`, error),
  },
);
```

### Circuit breaker

```ts
import { createCircuitBreaker } from 'retrykit';

const breaker = createCircuitBreaker({
  threshold: 5,
  timeout: 30_000,
  onOpen: () => console.warn('Circuit opened'),
});

const result = await breaker.execute(() => callStripe());
console.log(breaker.state); // 'CLOSED' | 'OPEN' | 'HALF_OPEN'
```

### Decorators (requires `experimentalDecorators`)

```ts
import { retry, circuitBreaker } from 'retrykit';

class ApiClient {
  @retry({ attempts: 3, backoff: 'exponential' })
  @circuitBreaker({ threshold: 5, timeout: 30_000 })
  async callOpenAI(prompt: string): Promise<string> {
    /* ... */
  }
}
```

## API reference

### `withRetry<T>(fn, options?): Promise<T>`

Runs `fn`, retrying on failure. Throws `RetryError` (with `.attempts` and
`.lastError`) when exhausted. `on` accepts error constructors or their string
names; omit it to retry on any error.

Options: `attempts` (3), `backoff` (`'exponential'`), `delay` (1000 ms),
`maxDelay` (60000 ms), `jitter` (false), `on`, `onRetry(attempt, error)`.

### `retry(options?)`

Method decorator equivalent of `withRetry`.

### `createCircuitBreaker(options?)` / `new CircuitBreaker(options?)`

`.execute(fn)`, `.executeSync(fn)`, `.state`, `.failureCount`, `.reset()`.
Options: `threshold` (5), `timeout` (30000 ms), `onOpen`, `onClose`. Throws
`CircuitOpenError` while open.

### `circuitBreaker(options?)`

Method decorator that wraps a method with a circuit breaker.

## OpenTelemetry

retrykit never imports `@opentelemetry/api` directly. When an OpenTelemetry
TracerProvider is registered (e.g. via the Node SDK), every attempt is wrapped
in a span named `retry.attempt:<fn>` with attributes `retry.attempt`,
`retry.max_attempts` and `retry.failed`. With no provider, span creation is
skipped at zero cost.

## Development

```bash
npm install
npm run typecheck   # tsc --noEmit (strict)
npm run lint        # eslint
npm test            # vitest
npm run build       # tsup -> dist (ESM + CJS + d.ts)
```

## License

MIT
