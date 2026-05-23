import { describe, expect, it } from 'vitest';
import { CircuitOpenError, RetryError, circuitBreaker, retry } from '../src/index.js';

class Boom extends Error {}

describe('decorators', () => {
  it('@retry retries a method until it succeeds', async () => {
    class Service {
      calls = 0;

      @retry({ attempts: 3, sleep: () => Promise.resolve() })
      async flaky(): Promise<string> {
        this.calls += 1;
        if (this.calls < 2) throw new Boom();
        return 'ok';
      }
    }

    const svc = new Service();
    await expect(svc.flaky()).resolves.toBe('ok');
    expect(svc.calls).toBe(2);
  });

  it('@retry throws RetryError when exhausted', async () => {
    class Service {
      @retry({ attempts: 2, sleep: () => Promise.resolve() })
      async always(): Promise<void> {
        throw new Boom();
      }
    }
    await expect(new Service().always()).rejects.toBeInstanceOf(RetryError);
  });

  it('@circuitBreaker opens after the threshold', async () => {
    class Service {
      @circuitBreaker({ threshold: 2, timeout: 10_000 })
      async call(ok: boolean): Promise<string> {
        if (!ok) throw new Boom();
        return 'ok';
      }
    }
    const svc = new Service();
    await expect(svc.call(false)).rejects.toBeInstanceOf(Boom);
    await expect(svc.call(false)).rejects.toBeInstanceOf(Boom);
    await expect(svc.call(true)).rejects.toBeInstanceOf(CircuitOpenError);
  });

  it('preserves `this` binding', async () => {
    class Service {
      value = 7;

      @retry({ attempts: 1 })
      async read(): Promise<number> {
        return this.value;
      }
    }
    await expect(new Service().read()).resolves.toBe(7);
  });
});
