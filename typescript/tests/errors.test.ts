import { describe, expect, it } from 'vitest';
import { CircuitOpenError, RetryError, RetrykitError } from '../src/index.js';

describe('error classes', () => {
  it('RetryError includes the last error message when present', () => {
    const err = new RetryError(3, new Error('downstream'));
    expect(err).toBeInstanceOf(RetrykitError);
    expect(err.message).toContain('3 attempt(s)');
    expect(err.message).toContain('downstream');
  });

  it('RetryError omits detail when there is no last error', () => {
    const err = new RetryError(2);
    expect(err.message).toBe('Retry failed after 2 attempt(s)');
    expect(err.lastError).toBeUndefined();
  });

  it('CircuitOpenError includes retryAfter when present', () => {
    const err = new CircuitOpenError(1500);
    expect(err.message).toContain('1500ms');
    expect(err.retryAfter).toBe(1500);
  });

  it('CircuitOpenError omits detail when retryAfter is absent', () => {
    const err = new CircuitOpenError();
    expect(err.message).toBe('Circuit breaker is open');
    expect(err.retryAfter).toBeUndefined();
  });
});
