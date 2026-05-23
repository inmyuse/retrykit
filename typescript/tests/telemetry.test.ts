import { afterEach, describe, expect, it } from 'vitest';
import { RetryError, isAvailable, setTracer, withRetry } from '../src/index.js';

interface RecordedSpan {
  name: string;
  attributes: Record<string, string | number | boolean>;
  exceptions: unknown[];
  ended: boolean;
}

/** A minimal in-memory tracer that records spans for assertions. */
function memoryTracer() {
  const spans: RecordedSpan[] = [];
  const tracer = {
    startSpan(name: string) {
      const span: RecordedSpan = { name, attributes: {}, exceptions: [], ended: false };
      spans.push(span);
      return {
        setAttribute(key: string, value: string | number | boolean) {
          span.attributes[key] = value;
        },
        recordException(error: unknown) {
          span.exceptions.push(error);
        },
        end() {
          span.ended = true;
        },
      };
    },
  };
  return { tracer, spans };
}

afterEach(() => setTracer(null));

describe('telemetry', () => {
  it('reports availability based on the configured tracer', () => {
    expect(isAvailable()).toBe(false);
    const { tracer } = memoryTracer();
    setTracer(tracer);
    expect(isAvailable()).toBe(true);
  });

  it('creates one span per attempt with retry attributes', async () => {
    const { tracer, spans } = memoryTracer();
    setTracer(tracer);

    await expect(
      withRetry(
        async () => {
          throw new Error('boom');
        },
        { attempts: 3, sleep: () => Promise.resolve() },
      ),
    ).rejects.toBeInstanceOf(RetryError);

    expect(spans).toHaveLength(3);
    for (const span of spans) {
      expect(span.name.startsWith('retry.attempt:')).toBe(true);
      expect(span.attributes['retry.max_attempts']).toBe(3);
      expect(span.attributes['retry.failed']).toBe(true);
      expect(span.exceptions).toHaveLength(1);
      expect(span.ended).toBe(true);
    }
  });

  it('marks a successful attempt span as not failed', async () => {
    const { tracer, spans } = memoryTracer();
    setTracer(tracer);

    await expect(withRetry(async () => 'ok', { attempts: 2 })).resolves.toBe('ok');
    expect(spans).toHaveLength(1);
    expect(spans[0]?.attributes['retry.failed']).toBe(false);
    expect(spans[0]?.ended).toBe(true);
  });

  it('is a no-op when no tracer is configured', async () => {
    await expect(withRetry(async () => 'ok')).resolves.toBe('ok');
  });

  it('auto-detects a tracer from the OpenTelemetry API global', async () => {
    const { tracer, spans } = memoryTracer();
    const key = Symbol.for('opentelemetry.js.api.1');
    const globalAny = globalThis as Record<symbol, unknown>;
    globalAny[key] = { trace: { getTracer: () => tracer } };
    try {
      expect(isAvailable()).toBe(true);
      await expect(withRetry(async () => 'ok', { attempts: 1 })).resolves.toBe('ok');
      expect(spans).toHaveLength(1);
    } finally {
      delete globalAny[key];
    }
  });
});
