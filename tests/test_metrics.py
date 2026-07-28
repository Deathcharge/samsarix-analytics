from __future__ import annotations

import json
import math
from concurrent.futures import ThreadPoolExecutor

import pytest

from helix_analytics import (
    CardinalityLimitError,
    Counter,
    Gauge,
    Histogram,
    MetricError,
    MetricRegistry,
    track_duration,
)


def test_counter_gauge_histogram_snapshot_and_queries() -> None:
    registry = MetricRegistry(max_histogram_samples=2)
    counter = registry.counter("requests_total", "Requests", ("status",))
    gauge = registry.gauge("workers", "Workers")
    histogram = registry.histogram(
        "latency_seconds", "Latency", ("route",), buckets=(0.1, 0.5, 1.0)
    )

    counter.inc(status="200")
    counter.inc(2, status="200")
    gauge.set(3)
    gauge.dec()
    for value in (0.05, 0.2, 0.8):
        histogram.observe(value, route="/health")

    assert counter.value(status="200") == 3
    assert gauge.value() == 2
    summary = histogram.summary(route="/health")
    assert summary is not None
    assert summary["count"] == 3
    assert summary["recent_count"] == 2
    assert registry.query("latency_seconds", "p95")[0].value == pytest.approx(0.77)

    snapshot = registry.snapshot()
    assert snapshot["schema_version"] == "helix-analytics/v1"
    json.dumps(snapshot)


def test_definition_and_observation_validation() -> None:
    registry = MetricRegistry(max_metrics=1, max_label_value_length=3)
    counter = registry.counter("events_total", "Events", ("kind",), max_series=1)

    with pytest.raises(MetricError, match="missing labels"):
        counter.inc()
    with pytest.raises(MetricError, match="unknown labels"):
        counter.inc(kind="ok", extra="x")
    with pytest.raises(MetricError, match="exceeds"):
        counter.inc(kind="toolong")
    with pytest.raises(MetricError, match="control character"):
        counter.inc(kind="a\rb")
    with pytest.raises(MetricError, match="negative"):
        counter.inc(-1, kind="ok")
    with pytest.raises(MetricError, match="finite"):
        counter.inc(math.inf, kind="ok")

    counter.inc(kind="ok")
    with pytest.raises(CardinalityLimitError, match="series limit"):
        counter.inc(kind="new")
    with pytest.raises(CardinalityLimitError, match="metric limit"):
        registry.gauge("other", "Other")


def test_registration_is_idempotent_but_rejects_conflicts() -> None:
    registry = MetricRegistry()
    first = registry.counter("tasks_total", "Tasks")
    assert registry.counter("tasks_total", "Tasks") is first
    with pytest.raises(MetricError, match="different definition"):
        registry.counter("tasks_total", "Different")
    with pytest.raises(MetricError, match="different definition"):
        registry.gauge("tasks_total", "Tasks")


def test_histogram_configuration_and_aggregation_validation() -> None:
    registry = MetricRegistry()
    with pytest.raises(MetricError, match="strictly increasing"):
        registry.histogram("bad", "Bad", buckets=(1.0, 1.0))
    with pytest.raises(MetricError, match="reserved"):
        registry.histogram("bad_labels", "Bad", ("le",))

    histogram = registry.histogram("duration", "Duration", buckets=(1.0,))
    histogram.observe(0.5)
    with pytest.raises(MetricError, match="unsupported histogram aggregation"):
        registry.query("duration", "median")
    with pytest.raises(MetricError, match="not registered"):
        registry.query("missing")


def test_prometheus_output_escapes_labels_and_help() -> None:
    registry = MetricRegistry()
    counter = registry.counter("events_total", "Events\\from\nworkers", ("source",))
    counter.inc(source='a"b\\c\n')

    output = registry.to_prometheus()

    assert "# HELP events_total Events\\\\from\\nworkers" in output
    assert 'source="a\\"b\\\\c\\n"' in output
    assert "# TYPE events_total counter" in output


def test_track_duration_records_on_success_and_failure() -> None:
    registry = MetricRegistry()
    histogram = registry.histogram("operation_seconds", "Operation duration")

    with track_duration(histogram):
        pass
    with pytest.raises(RuntimeError), track_duration(histogram):
        raise RuntimeError("boom")

    summary = histogram.summary()
    assert summary is not None
    assert summary["count"] == 2


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: Counter("bad-name", "Description"), "metric names"),
        (lambda: Counter("valid", ""), "description"),
        (lambda: Counter("valid", "Description", max_series=0), "max_series"),
        (
            lambda: Counter("valid", "Description", max_label_value_length=0),
            "max_label_value_length",
        ),
        (lambda: Counter("valid", "Description", ("same", "same")), "unique"),
        (lambda: Counter("valid", "Description", ("__private",)), "invalid label"),
        (lambda: Histogram("valid", "Description", max_samples=0), "max_samples"),
    ],
)
def test_instrument_definition_validation(factory: object, message: str) -> None:
    with pytest.raises(MetricError, match=message):
        factory()  # type: ignore[operator]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_metrics": 0},
        {"max_series_per_metric": 0},
        {"max_histogram_samples": 0},
        {"max_label_value_length": 0},
    ],
)
def test_registry_limit_validation(kwargs: dict[str, int]) -> None:
    with pytest.raises(MetricError, match="at least 1"):
        MetricRegistry(**kwargs)


def test_gauge_and_histogram_capacity_and_export_branches() -> None:
    registry = MetricRegistry()
    gauge = registry.gauge("temperature", "Temperature", ("room",), max_series=1)
    assert gauge.value(room="a") is None
    gauge.inc(2, room="a")
    with pytest.raises(CardinalityLimitError):
        gauge.set(3, room="b")
    direct_gauge = Gauge("limited", "Limited", ("id",), max_series=1)
    direct_gauge.inc(id="a")
    with pytest.raises(CardinalityLimitError):
        direct_gauge.inc(id="b")
    with pytest.raises(MetricError, match="only the 'value'"):
        registry.query("temperature", "avg")

    histogram = registry.histogram("size_bytes", "Size", ("kind",), buckets=(1, 2), max_series=1)
    assert histogram.summary(kind="small") is None
    histogram.observe(0.5, kind="small")
    histogram.observe(3, kind="small")
    with pytest.raises(CardinalityLimitError):
        histogram.observe(1, kind="large")
    for aggregation in ("count", "sum", "avg", "min", "max", "p50"):
        assert registry.query("size_bytes", aggregation)

    output = registry.to_prometheus()
    assert 'size_bytes_bucket{kind="small",le="1"} 1' in output
    assert 'size_bytes_bucket{kind="small",le="+Inf"} 2' in output
    assert "size_bytes_sum" in output
    assert 'temperature{room="a"} 2' in output
    assert json.loads(registry.to_json(indent=None))["schema_version"] == "helix-analytics/v1"
    assert MetricRegistry().to_prometheus() == ""


def test_explicit_zero_overrides_are_rejected() -> None:
    registry = MetricRegistry()
    with pytest.raises(MetricError, match="max_series"):
        registry.counter("counter", "Counter", max_series=0)
    with pytest.raises(MetricError, match="max_series"):
        registry.gauge("gauge", "Gauge", max_series=0)
    with pytest.raises(MetricError, match="max_samples"):
        registry.histogram("histogram", "Histogram", max_samples=0)


def test_counter_updates_are_thread_safe() -> None:
    counter = MetricRegistry().counter("work_total", "Work")
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda _index: counter.inc(), range(1000)))
    assert counter.value() == 1000


def test_accumulations_cannot_overflow_to_non_finite_values() -> None:
    registry = MetricRegistry()
    counter = registry.counter("large_total", "Large total")
    gauge = registry.gauge("large_gauge", "Large gauge")
    histogram = registry.histogram("large_values", "Large values")

    counter.inc(1e308)
    gauge.set(1e308)
    histogram.observe(1e308)

    with pytest.raises(MetricError, match="finite numeric range"):
        counter.inc(1e308)
    with pytest.raises(MetricError, match="finite numeric range"):
        gauge.inc(1e308)
    with pytest.raises(MetricError, match="finite numeric range"):
        histogram.observe(1e308)

    assert counter.value() == 1e308
    assert gauge.value() == 1e308
    summary = histogram.summary()
    assert summary is not None
    assert summary["count"] == 1
    assert summary["sum"] == 1e308
