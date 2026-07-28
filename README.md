# helix-analytics

`helix-analytics` is a dependency-free Python library for bounded in-process metrics
and deterministic threshold alerts. It gives small services, workers, CLIs, libraries,
and test harnesses a deliberate local telemetry layer without requiring a database,
collector, hosted account, or another Helix repository.

The current `0.2.0` line is an alpha release candidate. Its focused metrics/alerting
journey is implemented and tested; persistence, multiprocess aggregation, and
OpenTelemetry adapters are intentionally out of scope for this release.

## What it does

- labeled counters, gauges, and histograms;
- explicit limits for metric count, series cardinality, retained histogram samples,
  label length, alert rules/handlers, and alert history;
- strict validation for definitions, labels, and finite observations;
- JSON snapshots and Prometheus-compatible text export;
- threshold rules over values or histogram aggregates (`avg`, `p95`, and others);
- alert deduplication, cooldown, acknowledgement, auto-resolution, and isolated
  notification callbacks;
- no background threads, network requests, secrets, analytics, or runtime dependencies.

## Requirements

- Python 3.10 or newer
- No third-party runtime packages

## Install

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

## Five-minute walkthrough

```python
from helix_analytics import AlertManager, AlertRule, Comparison, MetricRegistry

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
helix-analytics --version
helix-analytics demo --format json
helix-analytics demo --format prometheus
# Equivalent from a checkout:
python -m helix_analytics demo --format json
```

See [`examples/basic_usage.py`](examples/basic_usage.py) for a complete script.

## Error and lifecycle behavior

- Registering the same metric definition twice returns the original instrument.
- Reusing a metric name with a different type, labels, limits, buckets, or description
  raises `MetricError`.
- Missing or unknown labels, invalid names, non-finite values, counter decrements, and
  overlong label values fail immediately.
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
escaped before rendering.

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

The default maximum is 1,024 recent samples for each of 100 series per histogram.
All-time histogram count, sum, min, max, and bucket counters remain exact; percentiles
use only that bounded recent sample window.

## Development and verification

```bash
python -m ruff format --check .
python -m ruff check .
python -m mypy helix_analytics
python -m pytest --cov=helix_analytics --cov-report=term-missing
python -m build
python -m twine check dist/*
```

CI runs formatting, lint, strict type checks, coverage, and package build checks across
Python 3.10 through 3.14. Release publication is intentionally manual and owner-controlled.

## Architecture

- `helix_analytics.monitoring.metrics`: registry, instruments, validation, limits,
  snapshots, Prometheus rendering, and duration tracking.
- `helix_analytics.monitoring.alerting`: rules, lifecycle, cooldown, bounded history,
  and callback dispatch.
- `helix_analytics.cli`: deterministic installed-package evaluation path.

The package performs no automatic global registration, I/O, service discovery, or
environment inspection. Applications own their registry and alert manager explicitly.

## Limitations

- State is process-local and is lost on restart.
- Multiple worker processes do not aggregate automatically.
- Percentiles are exact only for the bounded recent sample window.
- There is no HTTP server or framework middleware in the core package.
- There is no OpenTelemetry export adapter yet; use this package as a small local layer,
  not as a replacement for a full distributed telemetry pipeline.

## Security and support

See [`SECURITY.md`](SECURITY.md) for the trust model and private reporting path. General
bugs and feature requests belong in [GitHub Issues](https://github.com/Deathcharge/helix-analytics/issues).
Contribution setup and quality expectations are in [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License status

The repository contains a modified Business Source License 1.1-style `LICENSE`, not an
MIT license. Its parameters currently name “Helix Licensing System” instead of
`helix-analytics`; this is a known owner/legal release gate documented in
[`docs/PRODUCTIZATION.md`](docs/PRODUCTIZATION.md). No license text was changed during
productization.
