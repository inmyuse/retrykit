/**
 * Circuit breaker implementation.
 *
 * State machine:
 * ```
 * CLOSED    --(failures >= threshold)--> OPEN
 * OPEN      --(timeout elapsed)--------> HALF_OPEN
 * HALF_OPEN --(trial succeeds)---------> CLOSED
 * HALF_OPEN --(trial fails)------------> OPEN
 * ```
 *
 * JavaScript is single-threaded, so no locking is required; concurrent async
 * calls observe a consistent state because mutations happen synchronously
 * between `await` points.
 */

import { CircuitOpenError } from './errors.js';

/** The three states of a circuit breaker. */
export type CircuitState = 'CLOSED' | 'OPEN' | 'HALF_OPEN';

/** Options for {@link CircuitBreaker} and {@link createCircuitBreaker}. */
export interface CircuitBreakerOptions {
  /** Consecutive failures that trip the breaker OPEN. Defaults to `5`. */
  threshold?: number;
  /** Milliseconds the breaker stays OPEN before a HALF_OPEN trial. Defaults to `30000`. */
  timeout?: number;
  /** Called when the breaker opens. */
  onOpen?: () => void;
  /** Called when the breaker recovers and closes. */
  onClose?: () => void;
  /** Monotonic clock in milliseconds, injectable for tests. Defaults to `Date.now`. */
  now?: () => number;
}

/** A circuit breaker that trips after repeated failures. */
export class CircuitBreaker {
  readonly threshold: number;
  readonly timeout: number;
  private readonly onOpen?: () => void;
  private readonly onClose?: () => void;
  private readonly now: () => number;

  private _state: CircuitState = 'CLOSED';
  private failures = 0;
  private openedAt: number | null = null;

  constructor(options: CircuitBreakerOptions = {}) {
    const { threshold = 5, timeout = 30_000, onOpen, onClose, now = Date.now } = options;
    if (threshold < 1) {
      throw new RangeError('threshold must be >= 1');
    }
    if (timeout < 0) {
      throw new RangeError('timeout must be >= 0');
    }
    this.threshold = threshold;
    this.timeout = timeout;
    this.onOpen = onOpen;
    this.onClose = onClose;
    this.now = now;
  }

  /** The current state, accounting for an elapsed OPEN timeout. */
  get state(): CircuitState {
    this.maybeHalfOpen();
    return this._state;
  }

  /** Number of consecutive failures currently recorded. */
  get failureCount(): number {
    return this.failures;
  }

  /** Force the breaker back to a clean CLOSED state. */
  reset(): void {
    this.toClosed();
  }

  private maybeHalfOpen(): void {
    if (
      this._state === 'OPEN' &&
      this.openedAt !== null &&
      this.now() - this.openedAt >= this.timeout
    ) {
      this._state = 'HALF_OPEN';
    }
  }

  private toClosed(): void {
    const wasOpen = this._state !== 'CLOSED';
    this._state = 'CLOSED';
    this.failures = 0;
    this.openedAt = null;
    if (wasOpen) {
      this.onClose?.();
    }
  }

  private toOpen(): void {
    this._state = 'OPEN';
    this.openedAt = this.now();
    this.onOpen?.();
  }

  private beforeCall(): void {
    this.maybeHalfOpen();
    if (this._state === 'OPEN') {
      const retryAfter =
        this.openedAt !== null
          ? Math.max(0, this.timeout - (this.now() - this.openedAt))
          : undefined;
      throw new CircuitOpenError(retryAfter);
    }
  }

  private onSuccess(): void {
    if (this._state === 'HALF_OPEN') {
      this.toClosed();
    } else {
      this.failures = 0;
    }
  }

  private onFailure(): void {
    if (this._state === 'HALF_OPEN') {
      this.toOpen();
      return;
    }
    this.failures += 1;
    if (this.failures >= this.threshold) {
      this.toOpen();
    }
  }

  /** Execute an async function through the breaker. */
  async execute<T>(fn: () => Promise<T> | T): Promise<T> {
    this.beforeCall();
    try {
      const result = await fn();
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure();
      throw error;
    }
  }

  /** Execute a synchronous function through the breaker. */
  executeSync<T>(fn: () => T): T {
    this.beforeCall();
    try {
      const result = fn();
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure();
      throw error;
    }
  }
}

/**
 * Create a standalone circuit breaker.
 *
 * @example
 * ```ts
 * const breaker = createCircuitBreaker({ threshold: 5, timeout: 30_000 });
 * const result = await breaker.execute(() => callStripe());
 * console.log(breaker.state); // 'CLOSED' | 'OPEN' | 'HALF_OPEN'
 * ```
 */
export function createCircuitBreaker(options: CircuitBreakerOptions = {}): CircuitBreaker {
  return new CircuitBreaker(options);
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AsyncMethod = (...args: any[]) => Promise<unknown>;

/**
 * Method decorator that wraps a method with a circuit breaker.
 *
 * Requires `experimentalDecorators`. One breaker is shared across all instances
 * of the class, mirroring the Python decorator.
 *
 * @example
 * ```ts
 * class ApiClient {
 *   @circuitBreaker({ threshold: 5, timeout: 30_000 })
 *   async callOpenAI(prompt: string): Promise<string> { ... }
 * }
 * ```
 */
export function circuitBreaker(options: CircuitBreakerOptions = {}) {
  return function <T extends AsyncMethod>(
    _target: object,
    _propertyKey: string | symbol,
    descriptor: TypedPropertyDescriptor<T>,
  ): void {
    const original = descriptor.value;
    if (!original) {
      return;
    }
    const breaker = new CircuitBreaker(options);
    descriptor.value = function (this: unknown, ...args: Parameters<T>): ReturnType<T> {
      return breaker.execute(() => original.apply(this, args)) as ReturnType<T>;
    } as unknown as T;
  };
}
