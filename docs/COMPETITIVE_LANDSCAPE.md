# Competitive landscape and product wedge

Research reviewed on August 1, 2026. This record uses official project documentation
to position Samsarix Analytics honestly; it is not a claim of validated market demand.

## Decision

Samsarix Analytics should be the small, dependency-free observability control loop for
Python processes that cannot justify a collector stack: bounded local metrics,
deterministic threshold alerts, explicit checkpoints, and standards-compatible scrape
output. It should integrate with Prometheus and coexist with OpenTelemetry, not attempt
to replace either ecosystem.

## What established alternatives do well

The official Prometheus Python client already supplies the conventional global
registry, core metric types, WSGI/ASGI applications, a standalone HTTP server, and a
special multiprocess mode. Prometheus requires text exposition over HTTP by default and
documents `text/plain; version=0.0.4` as the legacy format content type. Its own client
guidance recommends separating core instrumentation from exposition bridges and warns
about dependency conflicts in embedded libraries.

Sources:

- [Prometheus exposition formats](https://prometheus.io/docs/instrumenting/exposition_formats/)
- [Prometheus client-library guidance](https://prometheus.io/docs/instrumenting/writing_clientlibs/)
- [Python WSGI exporter](https://prometheus.github.io/client_python/exporting/http/wsgi/)
- [Python ASGI exporter](https://prometheus.github.io/client_python/exporting/http/asgi/)
- [Python multiprocess mode](https://prometheus.github.io/client_python/multiprocess/)

OpenTelemetry is the appropriate choice when an application needs vendor-neutral
traces, logs, metrics, semantic conventions, collectors, OTLP transport, or broad
automatic framework instrumentation. The Python zero-code path installs a distro,
exporter, and integration packages and uses monkey patching. That breadth is useful,
but it solves a different operational problem from a zero-runtime-dependency local
library.

Sources:

- [OpenTelemetry Python zero-code instrumentation](https://opentelemetry.io/docs/zero-code/python/)
- [OpenTelemetry metrics data model](https://opentelemetry.io/docs/specs/otel/metrics/data-model/)
- [OpenTelemetry metrics semantic conventions](https://opentelemetry.io/docs/specs/semconv/general/metrics/)

## Defensible use cases

1. **Restartable batch and edge workers.** Record a bounded set of operational metrics,
   evaluate local alerts, and explicitly checkpoint state when there is no always-on
   metrics backend.
2. **Small private services.** Mount a WSGI/ASGI scrape endpoint or use the loopback
   server without adding a framework or runtime dependency.
3. **Test and reliability harnesses.** Assert deterministic metric snapshots and alert
   transitions without a global registry, background exporter, or external service.
4. **Dependency-sensitive libraries and CLIs.** Accept an application-owned registry
   and expose useful instrumentation without selecting the application's telemetry
   vendor or collector topology.

## Differentiation that is real today

- Every memory-growth dimension has an explicit cap and fails closed when exceeded.
- Registries are application-owned; imports create no singleton state or implicit I/O.
- Threshold alert lifecycle is available in the same process and is deterministic in
  tests.
- HTTP adapters use exact paths, bounded rendered state, no-cache responses, optional
  constant-time bearer checks, and loopback as the standalone default.
- Checkpoints are deterministic JSON rather than pickle, reject duplicate keys and
  malformed invariants, apply load-time resource policies, and replace files atomically.

## Deliberate non-goals

- distributed tracing or log collection;
- a hosted backend, dashboard, query engine, or long-term time-series database;
- transparent aggregation across worker processes;
- automatic instrumentation or monkey patching;
- claiming OpenTelemetry conformance without a tested adapter.

## `0.3.0` acceptance criteria

- Existing `0.2` metric and alert APIs remain source-compatible.
- WSGI, ASGI, and standalone scrape paths return reproducible Prometheus text with
  correct method, status, content-type, length, and authentication behavior.
- The standalone server binds to loopback by default and has explicit shutdown.
- Registry checkpoint bytes round-trip counters, gauges, and complete histogram state.
- File loading is bounded before JSON parsing or metric allocation; corrupt definitions,
  duplicate keys/series, non-finite values, and policy violations fail clearly.
- Checkpoint writes are same-directory, flushed, atomic replacements and return an
  integrity digest.
- A new user can run a scrapeable example, a restartable-worker example, and inspect a
  saved checkpoint from the CLI.
- Formatting, lint, strict typing, branch coverage, clean wheel installation, artifact
  inspection, and the Python 3.10-3.14 CI matrix pass.
