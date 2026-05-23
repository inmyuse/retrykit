import { describe, expect, it, vi } from 'vitest';
import {
  CircuitBreaker,
  CircuitOpenError,
  createCircuitBreaker,
} from '../src/index.js';

class Boom extends Error {}

/** A controllable clock in milliseconds. */
function fakeClock(): { now: () => number; advance: (ms: number) => void } {
  let t = 0;
  return { now: () => t, advance: (ms: number) => (t += ms) };
}

const fail = async () => {
  throw new Boom();
};

describe('CircuitBreaker', () => {
  it('opens after threshold consecutive failures', async () => {
    const onOpen = vi.fn();
    const cb = new CircuitBreaker({ threshold: 3, timeout: 10_000, onOpen });

    for (let i = 0; i < 3; i += 1) {
      await expect(cb.execute(fail)).rejects.toBeInstanceOf(Boom);
    }
    expect(cb.state).toBe('OPEN');
    expect(onOpen).toHaveBeenCalledTimes(1);
  });

  it('rejects calls while OPEN with CircuitOpenError', async () => {
    const clock = fakeClock();
    const cb = new CircuitBreaker({ threshold: 1, timeout: 10_000, now: clock.now });

    await expect(cb.execute(fail)).rejects.toBeInstanceOf(Boom);
    expect(cb.state).toBe('OPEN');

    await expect(cb.execute(async () => 'never')).rejects.toBeInstanceOf(CircuitOpenError);
  });

  it('transitions OPEN -> HALF_OPEN -> CLOSED on recovery', async () => {
    const clock = fakeClock();
    const onClose = vi.fn();
    const cb = new CircuitBreaker({
      threshold: 1,
      timeout: 5_000,
      onClose,
      now: clock.now,
    });

    await expect(cb.execute(fail)).rejects.toBeInstanceOf(Boom);
    expect(cb.state).toBe('OPEN');

    clock.advance(5_000);
    expect(cb.state).toBe('HALF_OPEN');

    await expect(cb.execute(async () => 'recovered')).resolves.toBe('recovered');
    expect(cb.state).toBe('CLOSED');
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('reopens when the HALF_OPEN trial fails', async () => {
    const clock = fakeClock();
    const cb = new CircuitBreaker({ threshold: 1, timeout: 5_000, now: clock.now });

    await expect(cb.execute(fail)).rejects.toBeInstanceOf(Boom);
    clock.advance(5_000);
    expect(cb.state).toBe('HALF_OPEN');

    await expect(cb.execute(fail)).rejects.toBeInstanceOf(Boom);
    expect(cb.state).toBe('OPEN');
  });

  it('resets the failure count on success', async () => {
    const cb = new CircuitBreaker({ threshold: 3 });
    await expect(cb.execute(fail)).rejects.toBeInstanceOf(Boom);
    expect(cb.failureCount).toBe(1);
    await cb.execute(async () => 'ok');
    expect(cb.failureCount).toBe(0);
    expect(cb.state).toBe('CLOSED');
  });

  it('reset() forces CLOSED', async () => {
    const cb = new CircuitBreaker({ threshold: 1 });
    await expect(cb.execute(fail)).rejects.toBeInstanceOf(Boom);
    expect(cb.state).toBe('OPEN');
    cb.reset();
    expect(cb.state).toBe('CLOSED');
  });

  it('supports synchronous execution', () => {
    const cb = new CircuitBreaker({ threshold: 1 });
    expect(() =>
      cb.executeSync(() => {
        throw new Boom();
      }),
    ).toThrow(Boom);
    expect(cb.state).toBe('OPEN');
    expect(() => cb.executeSync(() => 'x')).toThrow(CircuitOpenError);
  });

  it('createCircuitBreaker returns a working breaker', async () => {
    const breaker = createCircuitBreaker({ threshold: 2, timeout: 1_000 });
    expect(breaker.state).toBe('CLOSED');
    await expect(breaker.execute(async () => 42)).resolves.toBe(42);
  });

  it('rejects invalid options', () => {
    expect(() => new CircuitBreaker({ threshold: 0 })).toThrow(RangeError);
    expect(() => new CircuitBreaker({ timeout: -1 })).toThrow(RangeError);
  });
});
