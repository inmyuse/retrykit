import { describe, expect, it, vi } from 'vitest';
import { RetryError, withRetry } from '../src/index.js';

class Boom extends Error {
  constructor() {
    super('boom');
    this.name = 'Boom';
  }
}

class Other extends Error {
  constructor() {
    super('other');
    this.name = 'Other';
  }
}

const noSleep = () => Promise.resolve();

describe('withRetry', () => {
  it('returns immediately on success', async () => {
    const fn = vi.fn(async () => 'ok');
    await expect(withRetry(fn, { sleep: noSleep })).resolves.toBe('ok');
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it('retries then succeeds', async () => {
    let calls = 0;
    const fn = async () => {
      calls += 1;
      if (calls < 3) throw new Boom();
      return 'ok';
    };
    await expect(withRetry(fn, { attempts: 3, sleep: noSleep })).resolves.toBe('ok');
    expect(calls).toBe(3);
  });

  it('throws RetryError after exhausting attempts', async () => {
    let calls = 0;
    const fn = async () => {
      calls += 1;
      throw new Boom();
    };
    await expect(withRetry(fn, { attempts: 3, sleep: noSleep })).rejects.toBeInstanceOf(
      RetryError,
    );
    expect(calls).toBe(3);
  });

  it('exposes attempts and lastError on RetryError', async () => {
    const fn = async () => {
      throw new Boom();
    };
    try {
      await withRetry(fn, { attempts: 2, sleep: noSleep });
      expect.fail('should have thrown');
    } catch (error) {
      expect(error).toBeInstanceOf(RetryError);
      const re = error as RetryError;
      expect(re.attempts).toBe(2);
      expect(re.lastError).toBeInstanceOf(Boom);
    }
  });

  it('follows the exponential backoff schedule', async () => {
    const delays: number[] = [];
    const sleep = (ms: number) => {
      delays.push(ms);
      return Promise.resolve();
    };
    const fn = async () => {
      throw new Boom();
    };
    await expect(
      withRetry(fn, { attempts: 4, backoff: 'exponential', delay: 1000, sleep }),
    ).rejects.toBeInstanceOf(RetryError);
    expect(delays).toEqual([1000, 2000, 4000]);
  });

  it('caps delays at maxDelay (linear)', async () => {
    const delays: number[] = [];
    const sleep = (ms: number) => {
      delays.push(ms);
      return Promise.resolve();
    };
    await expect(
      withRetry(
        async () => {
          throw new Boom();
        },
        { attempts: 4, backoff: 'linear', delay: 10_000, maxDelay: 15_000, sleep },
      ),
    ).rejects.toThrow();
    expect(delays).toEqual([10_000, 15_000, 15_000]);
  });

  it('only retries on listed error constructors', async () => {
    let calls = 0;
    const fn = async () => {
      calls += 1;
      throw new Other();
    };
    await expect(
      withRetry(fn, { attempts: 5, on: [Boom], sleep: noSleep }),
    ).rejects.toBeInstanceOf(Other);
    expect(calls).toBe(1);
  });

  it('matches errors by name string', async () => {
    let calls = 0;
    const fn = async () => {
      calls += 1;
      throw new Boom();
    };
    await expect(
      withRetry(fn, { attempts: 3, on: ['Boom'], sleep: noSleep }),
    ).rejects.toBeInstanceOf(RetryError);
    expect(calls).toBe(3);
  });

  it('invokes onRetry with attempt number and error', async () => {
    const seen: Array<[number, string]> = [];
    await expect(
      withRetry(
        async () => {
          throw new Boom();
        },
        {
          attempts: 3,
          sleep: noSleep,
          onRetry: (attempt, error) => seen.push([attempt, (error as Error).name]),
        },
      ),
    ).rejects.toThrow();
    expect(seen).toEqual([
      [1, 'Boom'],
      [2, 'Boom'],
    ]);
  });

  it('applies jitter within bounds using injected random', async () => {
    const delays: number[] = [];
    const sleep = (ms: number) => {
      delays.push(ms);
      return Promise.resolve();
    };
    await expect(
      withRetry(
        async () => {
          throw new Boom();
        },
        {
          attempts: 3,
          backoff: 'exponential',
          delay: 1000,
          jitter: true,
          random: () => 0.5,
          sleep,
        },
      ),
    ).rejects.toThrow();
    // 0.5 * 1000, 0.5 * 2000
    expect(delays).toEqual([500, 1000]);
  });

  it('rejects invalid attempts', async () => {
    await expect(withRetry(async () => 1, { attempts: 0 })).rejects.toBeInstanceOf(
      RangeError,
    );
  });
});
