/**
 * Optional OpenTelemetry integration.
 *
 * retrykit never imports `@opentelemetry/api` directly, keeping the core free
 * of runtime dependencies and safe to run in the browser, Deno and Bun. Instead
 * it reads the OpenTelemetry API global that the package registers when an SDK
 * is configured. If no provider is registered, every helper here is a no-op.
 */

/** Minimal subset of an OpenTelemetry span that retrykit uses. */
interface MinimalSpan {
  setAttribute(key: string, value: string | number | boolean): unknown;
  recordException(error: unknown): unknown;
  end(): void;
}

/** Minimal subset of an OpenTelemetry tracer that retrykit uses. */
interface MinimalTracer {
  startSpan(name: string): MinimalSpan;
}

interface MinimalTracerProvider {
  getTracer(name: string): MinimalTracer;
}

// OpenTelemetry registers its API singletons on a versioned global symbol.
const OTEL_API_KEY = Symbol.for('opentelemetry.js.api.1');

let overrideTracer: MinimalTracer | null = null;

function lookupTracer(): MinimalTracer | null {
  if (overrideTracer) {
    return overrideTracer;
  }
  const registry = (globalThis as Record<symbol, unknown>)[OTEL_API_KEY] as
    | { trace?: MinimalTracerProvider }
    | undefined;
  const provider = registry?.trace;
  if (provider && typeof provider.getTracer === 'function') {
    return provider.getTracer('retrykit');
  }
  return null;
}

/**
 * Override the tracer used by retrykit.
 *
 * Mainly useful in tests; production code should configure a global
 * OpenTelemetry TracerProvider instead. Pass `null` to clear the override.
 */
export function setTracer(tracer: MinimalTracer | null): void {
  overrideTracer = tracer;
}

/** Whether a tracer is currently available and spans will be created. */
export function isAvailable(): boolean {
  return lookupTracer() !== null;
}

/**
 * Run `fn` inside a span for a single retry attempt.
 *
 * When no tracer is available this calls `fn` directly with no overhead. The
 * span is ended in all cases; a thrown error is recorded before re-throwing.
 *
 * @param name - Span name, typically the wrapped function's name.
 * @param attempt - One-based attempt number, recorded as `retry.attempt`.
 * @param maxAttempts - Total attempt budget, recorded as `retry.max_attempts`.
 * @param fn - The work to execute within the span.
 */
export async function withAttemptSpan<T>(
  name: string,
  attempt: number,
  maxAttempts: number,
  fn: () => Promise<T>,
): Promise<T> {
  const tracer = lookupTracer();
  if (!tracer) {
    return fn();
  }
  const span = tracer.startSpan(`retry.attempt:${name}`);
  span.setAttribute('retry.attempt', attempt);
  span.setAttribute('retry.max_attempts', maxAttempts);
  try {
    const result = await fn();
    span.setAttribute('retry.failed', false);
    return result;
  } catch (error) {
    span.setAttribute('retry.failed', true);
    span.recordException(error);
    throw error;
  } finally {
    span.end();
  }
}
