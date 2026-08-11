# Samsarix Analytics

`samsarix-analytics` is a dependency-free Python library from Samsarix LLC for bounded
in-process metrics and deterministic threshold alerts. It gives small services,
workers, CLIs, libraries, and test harnesses a deliberate local telemetry layer without
requiring a database, collector, hosted account, or another Samsarix repository.

General inquiries: [contact@samsarix.com](mailto:contact@samsarix.com). Support and
private security reports: [support@samsarix.com](mailto:support@samsarix.com).

The current `0.3.0` line is an alpha release candidate. Its metrics, alerting, HTTP
exposition, and explicit checkpoint journeys are implemented and tested; multiprocess
aggregation and OpenTelemetry adapters remain out of scope for this release.

## What it does

- labeled counters, gauges, and histograms;
- explicit limits for metric count, series cardinality, retained histogram samples,
  label length, alert rules/handlers, and alert history;
- strict validation for definitions, labels, and finite observations;
- JSON snapshots and Prometheus-compatible text export;
- WSGI, ASGI, and loopback-by-default Prometheus HTTP exposition;
- framework-neutral WSGI/ASGI request metrics without raw-path labels;
- threshold rules over values or histogram aggregates (`avg`, `p95`, and others);
- alert deduplication, cooldown, acknowledgement, auto-resolution, and isolated
  notification callbacks;
- deterministic, bounded, atomic JSON checkpoints for restartable local processes;
- no implicit threads, network/file access, secrets, analytics, or runtime dependencies.

## Requirements

- Python 3.10 or newer
- No third-party runtime packages

## Install

The `samsarix-analytics` distribution is not yet published on PyPI. That name returned
no current PyPI project record when checked on August 10, 2026, but it is not secured
until Samsarix LLC completes an intentional first publication.

From a checkout:

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install .
```

For development:

```bash
python -m pip install -r requirements-dev.txt
```

Maintainers should follow the checked, attested, Trusted Publishing process in
[`docs/RELEASING.md`](docs/RELEASING.md); no long-lived PyPI credential is required.

## Five-minute walkthrough

```python
from samsarix_analytics import AlertManager, AlertRule, Comparison, MetricRegistry

registry = MetricRegistry(max_series_per_metric=50)
jobs = registry.counter("jobs_total", "Jobs processed", ("status",))
duration = registry.histogram(
    "job_duration_seconds",
    "Job duration in seconds",
    ("queue",),
    buckets=(0.1, 0.5, 1.0, 5.0),
)

jobs.inc(status="ok")
duration.observe(1.4, queue="default")

alerts = AlertManager()
alerts.add_rule(
    AlertRule(
        name="slow_default_queue",
        metric="job_duration_seconds",
        aggregation="p95",
        operator=Comparison.GT,
        threshold=1.0,
        labels={"queue": "default"},
    )
)

result = alerts.evaluate(registry)
assert len(result.triggered) == 1

print(registry.to_json())
print(registry.to_prometheus())
```

The same journey is runnable without writing code:

```bash
samsarix-analytics --version
samsarix-analytics demo --format json
samsarix-analytics demo --format prometheus
# Equivalent from a checkout:
python -m samsarix_analytics demo --format json
```

See [`examples/basic_usage.py`](examples/basic_usage.py) for a complete script.

## Expose metrics to Prometheus

Mount a dependency-free endpoint inside an existing WSGI application:

```python
from samsarix_analytics import MetricRegistry, make_wsgi_app

registry = MetricRegistry()
requests = registry.counter("requests_total", "Requests processed")
metrics_app = make_wsgi_app(registry)
```

`make_asgi_app(registry)` provides the same contract for ASGI servers. For a local
worker, CLI, or development process, the standalone helper binds to loopback by
default and shuts down explicitly:

```python
from samsarix_analytics import MetricRegistry, start_metrics_server

registry = MetricRegistry()
with start_metrics_server(registry, port=9464) as server:
    print(server.url)  # http://127.0.0.1:9464/metrics
    run_application(registry)
```

Run `python -m examples.http_exposition` from an installed source checkout for a
scrapeable 15-second demo. Endpoint
factories support an optional bearer token, exact path matching, `GET`, `HEAD`, and
`OPTIONS`, a 10 MiB response budget, and the Prometheus
`text/plain; version=0.0.4` content type. Oversized output fails with `503` rather than
being sent partially; customize `max_response_bytes` only with an explicit resource
budget. The standalone server also enforces a five-second per-request timeout and a
32-request concurrency ceiling; tune `request_timeout_seconds` and
`max_concurrent_requests` to fit the process budget.

Instrument an existing application without framework-specific dependencies:

```python
from samsarix_analytics import MetricRegistry, instrument_wsgi

registry = MetricRegistry()
application = instrument_wsgi(application, registry)
```

`instrument_asgi(application, registry)` provides the async equivalent. Both wrappers
record completed requests, request duration, and active requests. Method values are
restricted to the standard HTTP methods plus `OTHER`, and responses use only a bounded
status class (`2xx`, `5xx`, and so on). Raw paths, query strings, headers, client
addresses, and request bodies are never used as labels or logged. Application
exceptions propagate normally; metric-capacity or recording failures are isolated and
logged without application data.

## Preserve explicit local state

Checkpointing is opt-in for batch jobs, edge workers, and other processes that own the
meaning of metrics across restarts:

```python
from samsarix_analytics import MetricRegistry, load_checkpoint, save_checkpoint

registry = load_checkpoint("worker-state.json")
jobs = registry.counter("worker_jobs_total", "Jobs completed across runs")
jobs.inc()
info = save_checkpoint(registry, "worker-state.json")
print(info.sha256)
```

Start a new `MetricRegistry` when the file does not yet exist; the complete pattern is
in [`examples/checkpointed_worker.py`](examples/checkpointed_worker.py):

```bash
python -m examples.checkpointed_worker worker-state.json --jobs 3
```

Inspect or validate a checkpoint without importing application code:

```bash
samsarix-analytics inspect worker-state.json --format json
samsarix-analytics inspect worker-state.json --format prometheus
```

The format is deterministic JSON—not pickle. Reads are capped before parsing and again
before metric allocation. Writes use a private same-directory temporary file, flush it,
atomically replace the target, and return its byte length and SHA-256 digest. A
checkpoint is consistent within each instrument but is not a transaction across
concurrent updates to several instruments; pause application updates when a globally
coordinated snapshot is required.

## Error and lifecycle behavior

- Registering the same metric definition twice returns the original instrument.
- Reusing a metric name with a different type, labels, limits, buckets, or description
  raises `MetricError`.
- Missing or unknown labels, non-string or invalid UTF-8 label values, invalid names,
  non-finite values, counter decrements, and overlong labels fail immediately.
- Adding a new metric or label series beyond its configured cap raises
  `CardinalityLimitError`; existing series remain usable.
- Alert evaluation reports missing metrics or unsupported aggregations in
  `EvaluationResult.errors` rather than silently claiming success.
- Active alerts update in place. When a condition clears, an auto-resolving rule moves
  the alert to bounded history. A cooldown prevents immediate re-triggering.
- Alert callback exceptions are logged and do not prevent other callbacks or alerts.

## Prometheus and privacy guidance

Prometheus output covers counters, gauges, and classic histogram buckets, sums, and
counts. Metric and label names are validated, while help text and label values are
escaped before rendering. HTTP responses disable caching and content sniffing. The
standalone server intentionally defaults to `127.0.0.1`, serves clients on bounded
daemon threads, and applies a five-second request timeout by default. Put public or
shared-network endpoints behind a TLS-capable reverse proxy and access control.

Every unique label set is a time series. Do not use user IDs, request IDs, raw URLs,
emails, tokens, or other unbounded/sensitive values as labels. The default limit is 100
series per metric and label values are capped at 200 characters, but good label design
is still required. The library stores all observations in the host process and sends
nothing over the network.

## Resource and operating cost

There is no external operating cost. Memory is bounded by configuration. A conservative
upper bound for retained histogram observations is:

```text
number of histogram metrics × max series per metric × retained samples per series
```

The default maximum is 1,024 recent samples for each of 100 series per histogram, with
at most 64 explicitly configured buckets per histogram.
All-time histogram count, sum, min, max, and bucket counters remain exact; percentiles
use only that bounded recent sample window.

Checkpoint size is bounded separately (10 MiB by default). Applications choosing a
larger registry must opt into correspondingly larger `CheckpointPolicy` limits when
loading untrusted or externally stored state.

See [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md) for the reproducible benchmark,
measured local result, retention assertion, and limitations of that evidence.

## Development and verification

```bash
python -m ruff format --check .
python -m ruff check .
python -m mypy samsarix_analytics benchmarks scripts
python scripts/verify_release.py
python -m pytest --cov=samsarix_analytics --cov-report=term-missing
python -m pip install --require-hashes -r requirements-release.txt
python -m build --no-isolation
python -m twine check dist/*
python -m scripts.verify_distributions
python -m benchmarks.benchmark_core --iterations 100000 --series 10
```

CI runs formatting, lint, strict type checks, coverage, and package build checks across
Python 3.10 through 3.14. Release publication is intentionally manual and owner-controlled.

## Architecture

- `samsarix_analytics.monitoring.metrics`: registry, instruments, validation, limits,
  snapshots, Prometheus rendering, and duration tracking.
- `samsarix_analytics.monitoring.alerting`: rules, lifecycle, cooldown, bounded history,
  and callback dispatch.
- `samsarix_analytics.exposition`: WSGI, ASGI, and explicit standalone HTTP adapters.
- `samsarix_analytics.checkpoint`: deterministic encoding, load policy, atomic file
  replacement, and checkpoint integrity metadata.
- `samsarix_analytics.instrumentation`: bounded WSGI/ASGI request lifecycle metrics.
- `samsarix_analytics.cli`: deterministic installed-package evaluation path.

The package performs no automatic global registration, I/O, service discovery, or
environment inspection. Applications own their registry and alert manager explicitly.

## Limitations

- State remains process-local unless the application explicitly saves and loads a
  checkpoint; automatic persistence and cross-process locking are not provided.
- Multiple worker processes do not aggregate automatically.
- Percentiles are exact only for the bounded recent sample window.
- The standalone HTTP helper does not provide TLS or multiprocess aggregation; use an
  application server/reverse proxy and one registry per process where those are needed.
- There is no OpenTelemetry export adapter yet; use this package as a small local layer,
  not as a replacement for a full distributed telemetry pipeline.

## Standalone design and integrations

Samsarix Analytics deliberately stands on its own. Existing Samsarix repositories can
consume this public API or add optional adapters, but this package does not import their
private modules or require them at runtime. Keeping that boundary makes installation,
testing, versioning, and security review tractable for every repository.

## Security and support

See [`SECURITY.md`](SECURITY.md) for the trust model and private reporting path. General
bugs and feature requests belong in [GitHub Issues](https://github.com/Deathcharge/samsarix-analytics/issues).
Contribution setup and quality expectations are in [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License and attribution

Source code is licensed under the [Mozilla Public License 2.0](LICENSE). Distributed
changes to MPL-covered files remain under MPL-2.0, while applications using the library
may remain under their own terms. See [`LICENSING.md`](LICENSING.md) for the rationale,
[`NOTICE`](NOTICE) for attribution, and [`TRADEMARKS.md`](TRADEMARKS.md) for Samsarix
brand-use guidance.
