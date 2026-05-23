/**
 * retrykit — retry logic and circuit breakers with an identical API in Python
 * and TypeScript.
 */

export { RetrykitError, RetryError, CircuitOpenError } from './errors.js';
export { computeDelay, type BackoffName, type ComputeDelayOptions } from './strategies.js';
export {
  withRetry,
  retry,
  type RetryOptions,
  type ErrorMatcher,
} from './retry.js';
export {
  CircuitBreaker,
  createCircuitBreaker,
  circuitBreaker,
  type CircuitState,
  type CircuitBreakerOptions,
} from './circuitBreaker.js';
export { isAvailable, setTracer } from './telemetry.js';

export const VERSION = '0.1.0';
