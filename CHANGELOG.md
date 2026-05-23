# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-05-23

### Added
- **Python package** (`retrykit`):
  - `@retry` decorator and `Retrying` context manager / iterator (sync + async).
  - `circuit_breaker` decorator and `CircuitBreaker` class with
    `CLOSED → OPEN → HALF_OPEN → CLOSED` state machine, thread-safe and
    asyncio-safe.
  - `fixed`, `linear` and `exponential` backoff with optional full jitter.
  - Optional OpenTelemetry spans per attempt, skipped silently when the API is
    not installed.
  - `RetryError` and `CircuitOpenError`; full type hints and `py.typed`.
- **TypeScript package** (`retrykit`):
  - `withRetry<T>()` function plus `@retry` and `@circuitBreaker` decorators.
  - `createCircuitBreaker()` / `CircuitBreaker` with the same state machine.
  - Identical option names and backoff strategies as the Python package.
  - Optional OpenTelemetry spans via the registered API global; zero runtime
    dependencies; ESM + CJS dual output.
- Repository tooling: CI for Python 3.9/3.11/3.12 and Node 18/20/22, MIT
  license, contributing guide.

[0.1.0]: https://github.com/inmyuse/retrykit/releases/tag/v0.1.0
