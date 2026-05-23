/** Retry logic: the `withRetry` function and the `@retry` method decorator. */

import { RetryError } from './errors.js';
import { type BackoffName, computeDelay } from './strategies.js';
import { withAttemptSpan } from './telemetry.js';

/** An entry in {@link RetryOptions.on}: an error constructor or its name. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type ErrorMatcher = (new (...args: any[]) => Error) | string;

/** Options for {@link withRetry} and the {@link retry} decorator. */
export interface RetryOptions {
  /** Maximum number of attempts (not retries). Defaults to `3`. */
  attempts?: number;
  /** Backoff strategy. Defaults to `'exponential'`. */
  backoff?: BackoffName;
  /** Base delay in milliseconds. Defaults to `1000`. */
  delay?: number;
  /** Maximum delay in milliseconds (before jitter). Defaults to `60000`. */
  maxDelay?: number;
  /** Apply full jitter to each delay. Defaults to `false`. */
  jitter?: boolean;
  /** Retry only on these errors (constructors or names). Omit to retry on any error. */
  on?: ErrorMatcher[];
  /** Called after each failed attempt that will be retried. `attempt` is 1-based. */
  onRetry?: (attempt: number, error: unknown) => void;
  /** Sleep implementation, injectable for tests. Defaults to `setTimeout`. */
  sleep?: (ms: number) => Promise<void>;
  /** Random source for jitter, injectable for tests. */
  random?: () => number;
}

function defaultSleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function matches(error: unknown, on: ErrorMatcher[] | undefined): boolean {
  if (on === undefined) {
    return true;
  }
  for (const matcher of on) {
    if (typeof matcher === 'string') {
      if (
        error instanceof Error &&
        (error.name === matcher || error.constructor?.name === matcher)
      ) {
        return true;
      }
    } else if (error instanceof matcher) {
      return true;
    }
  }
  return false;
}

/**
 * Run `fn`, retrying on failure according to `options`.
 *
 * @typeParam T - The resolved value type; `withRetry` returns `Promise<T>`.
 * @throws {RetryError} When all attempts are exhausted. The final error is on
 *   {@link RetryError.lastError}.
 *
 * @example
 * ```ts
 * const data = await withRetry(() => fetchJson(url), {
 *   attempts: 5,
 *   backoff: 'exponential',
 *   delay: 1000,
 *   jitter: true,
 *   on: [TypeError],
 *   onRetry: (attempt, error) => console.log(`Retry ${attempt}:`, error),
 * });
 * ```
 */
export async function withRetry<T>(
  fn: () => Promise<T> | T,
  options: RetryOptions = {},
): Promise<T> {
  const {
    attempts = 3,
    backoff = 'exponential',
    delay = 1000,
    maxDelay = 60_000,
    jitter = false,
    on,
    onRetry,
    sleep = defaultSleep,
    random,
  } = options;

  if (attempts < 1) {
    throw new RangeError('attempts must be >= 1');
  }

  const name = fn.name || 'withRetry';
  let lastError: unknown;

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      return await withAttemptSpan(name, attempt, attempts, async () => fn());
    } catch (error) {
      if (!matches(error, on)) {
        throw error;
      }
      lastError = error;
      if (attempt >= attempts) {
        break;
      }
      onRetry?.(attempt, error);
      const waitMs = computeDelay(attempt - 1, { backoff, delay, maxDelay, jitter, random });
      await sleep(waitMs);
    }
  }

  throw new RetryError(attempts, lastError);
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AsyncMethod = (...args: any[]) => Promise<unknown>;

/**
 * Method decorator equivalent of {@link withRetry}.
 *
 * Requires `experimentalDecorators`.
 *
 * @example
 * ```ts
 * class ApiClient {
 *   @retry({ attempts: 3, backoff: 'exponential' })
 *   async callOpenAI(prompt: string): Promise<string> { ... }
 * }
 * ```
 */
export function retry(options: RetryOptions = {}) {
  return function <T extends AsyncMethod>(
    _target: object,
    _propertyKey: string | symbol,
    descriptor: TypedPropertyDescriptor<T>,
  ): void {
    const original = descriptor.value;
    if (!original) {
      return;
    }
    descriptor.value = function (this: unknown, ...args: Parameters<T>): ReturnType<T> {
      return withRetry(() => original.apply(this, args), options) as ReturnType<T>;
    } as unknown as T;
  };
}
