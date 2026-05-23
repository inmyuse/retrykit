import { describe, expect, it } from 'vitest';
import { computeDelay } from '../src/index.js';

describe('computeDelay', () => {
  it('fixed backoff is constant', () => {
    for (let i = 0; i < 5; i += 1) {
      expect(computeDelay(i, { backoff: 'fixed', delay: 200 })).toBe(200);
    }
  });

  it('linear backoff scales with the attempt', () => {
    expect(computeDelay(0, { backoff: 'linear', delay: 100 })).toBe(100);
    expect(computeDelay(1, { backoff: 'linear', delay: 100 })).toBe(200);
    expect(computeDelay(2, { backoff: 'linear', delay: 100 })).toBe(300);
  });

  it('exponential backoff doubles', () => {
    expect(computeDelay(0, { backoff: 'exponential', delay: 100 })).toBe(100);
    expect(computeDelay(1, { backoff: 'exponential', delay: 100 })).toBe(200);
    expect(computeDelay(3, { backoff: 'exponential', delay: 100 })).toBe(800);
  });

  it('caps at maxDelay', () => {
    expect(computeDelay(10, { backoff: 'exponential', delay: 100, maxDelay: 500 })).toBe(500);
  });

  it('uses defaults when no options are given', () => {
    expect(computeDelay(0)).toBe(1000);
    expect(computeDelay(1)).toBe(2000);
  });

  it('applies full jitter within bounds', () => {
    const capped = computeDelay(2, { backoff: 'exponential', delay: 100 });
    const jittered = computeDelay(2, {
      backoff: 'exponential',
      delay: 100,
      jitter: true,
      random: () => 0.25,
    });
    expect(jittered).toBe(0.25 * capped);
    expect(jittered).toBeGreaterThanOrEqual(0);
    expect(jittered).toBeLessThanOrEqual(capped);
  });

  it('rejects a negative attempt', () => {
    expect(() => computeDelay(-1)).toThrow(RangeError);
  });

  it('rejects an unknown backoff strategy', () => {
    // @ts-expect-error exercising the runtime guard with an invalid value
    expect(() => computeDelay(0, { backoff: 'quadratic' })).toThrow(RangeError);
  });
});
