/** Backoff strategies for computing the delay between retry attempts. */

/** The available backoff strategies. */
export type BackoffName = 'fixed' | 'linear' | 'exponential';

/** Options accepted by {@link computeDelay}. */
export interface ComputeDelayOptions {
  /** Backoff strategy. Defaults to `'exponential'`. */
  backoff?: BackoffName;
  /** Base delay in milliseconds. Defaults to `1000`. */
  delay?: number;
  /** Maximum delay in milliseconds (before jitter). Defaults to `60000`. */
  maxDelay?: number;
  /** Apply full jitter (random between 0 and the capped delay). */
  jitter?: boolean;
  /** Random source in `[0, 1)`, injectable for deterministic tests. */
  random?: () => number;
}

/**
 * Compute the delay (in milliseconds) to wait before a given retry attempt.
 *
 * @param attempt - Zero-based index of the upcoming wait. `0` is the wait after
 *   the first failed attempt, `1` after the second, and so on.
 * @returns The number of milliseconds to wait before the next attempt.
 * @throws {RangeError} If `attempt` is negative or `backoff` is unknown.
 */
export function computeDelay(
  attempt: number,
  options: ComputeDelayOptions = {},
): number {
  const {
    backoff = 'exponential',
    delay = 1000,
    maxDelay = 60_000,
    jitter = false,
    random = Math.random,
  } = options;

  if (attempt < 0) {
    throw new RangeError('attempt must be >= 0');
  }

  let raw: number;
  switch (backoff) {
    case 'fixed':
      raw = delay;
      break;
    case 'linear':
      raw = delay * (attempt + 1);
      break;
    case 'exponential':
      raw = delay * 2 ** attempt;
      break;
    default:
      throw new RangeError(`Unknown backoff strategy: ${String(backoff)}`);
  }

  const capped = Math.min(raw, maxDelay);
  return jitter ? random() * capped : capped;
}
