/** Errors thrown by retrykit. */

/** Base class for all retrykit errors. */
export class RetrykitError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'RetrykitError';
    // Restore prototype chain for transpiled targets.
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

/**
 * Thrown when all retry attempts have been exhausted.
 *
 * The exception from the final attempt is available as {@link lastError}.
 */
export class RetryError extends RetrykitError {
  /** Number of attempts that were made. */
  readonly attempts: number;
  /** The error thrown by the final attempt, if any. */
  readonly lastError: unknown;

  constructor(attempts: number, lastError?: unknown) {
    const detail =
      lastError instanceof Error ? `: ${lastError.message}` : '';
    super(`Retry failed after ${attempts} attempt(s)${detail}`);
    this.name = 'RetryError';
    this.attempts = attempts;
    this.lastError = lastError;
  }
}

/**
 * Thrown when a call is attempted while the circuit breaker is `OPEN`.
 *
 * {@link retryAfter} is the approximate number of milliseconds until the
 * breaker transitions to `HALF_OPEN`.
 */
export class CircuitOpenError extends RetrykitError {
  readonly retryAfter?: number;

  constructor(retryAfter?: number) {
    const detail =
      retryAfter !== undefined ? `; retry after ${Math.round(retryAfter)}ms` : '';
    super(`Circuit breaker is open${detail}`);
    this.name = 'CircuitOpenError';
    this.retryAfter = retryAfter;
  }
}
