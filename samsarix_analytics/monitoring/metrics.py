# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: MPL-2.0

"""Thread-safe, bounded in-process metric instruments."""

from __future__ import annotations

import json
import math
import re
from collections import deque
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import RLock
from time import perf_counter
from typing import Final

_METRIC_NAME: Final = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_LABEL_NAME: Final = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_HISTOGRAM_AGGREGATIONS: Final = frozenset(
    {"count", "sum", "avg", "min", "max", "p50", "p90", "p95", "p99"}
)


class MetricError(ValueError):
    """Base exception for invalid metric definitions or observations."""


class CardinalityLimitError(MetricError):
    """Raised when a new label set would exceed an instrument's series limit."""


@dataclass(frozen=True)
class MetricSample:
    """A numeric view of one metric series used by alert evaluation."""

    metric: str
    labels: Mapping[str, str]
    aggregation: str
    value: float


def _finite_number(value: float | int, *, field_name: str = "value") -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MetricError(f"{field_name} must be a finite number")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise MetricError(f"{field_name} must be a finite number")
    return normalized


def _finite_sum(left: float, right: float, *, field_name: str) -> float:
    result = left + right
    if not math.isfinite(result):
        raise MetricError(f"{field_name} would exceed the finite numeric range")
    return result


def _format_float(value: float) -> str:
    return format(value, ".17g")


def _escape_help(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\r", "\\n").replace("\n", "\\n")


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _percentile(values: Sequence[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise MetricError("cannot calculate a percentile without observations")
    position = (len(ordered) - 1) * percentile / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


@dataclass
class _HistogramSeries:
    count: int = 0
    total: float = 0.0
    minimum: float | None = None
    maximum: float | None = None
    bucket_counts: list[int] = field(default_factory=list)
    recent: deque[float] = field(default_factory=deque)


class _Instrument:
    kind: str

    def __init__(
        self,
        name: str,
        description: str,
        label_names: Sequence[str],
        *,
        max_series: int,
        max_label_value_length: int,
    ) -> None:
        if not _METRIC_NAME.fullmatch(name):
            raise MetricError("metric names must match ^[a-zA-Z_][a-zA-Z0-9_]*$")
        if not description.strip():
            raise MetricError("metric description cannot be empty")
        if max_series < 1:
            raise MetricError("max_series must be at least 1")
        if max_label_value_length < 1:
            raise MetricError("max_label_value_length must be at least 1")

        normalized_names = tuple(label_names)
        if len(set(normalized_names)) != len(normalized_names):
            raise MetricError("label names must be unique")
        for label_name in normalized_names:
            if not _LABEL_NAME.fullmatch(label_name) or label_name.startswith("__"):
                raise MetricError(f"invalid label name: {label_name!r}")

        self.name = name
        self.description = description.strip()
        self.label_names = normalized_names
        self.max_series = max_series
        self.max_label_value_length = max_label_value_length
        self._lock = RLock()

    def _key(self, labels: Mapping[str, object]) -> tuple[str, ...]:
        provided = set(labels)
        expected = set(self.label_names)
        missing = sorted(expected - provided)
        extra = sorted(provided - expected)
        if missing or extra:
            details: list[str] = []
            if missing:
                details.append(f"missing labels: {', '.join(missing)}")
            if extra:
                details.append(f"unknown labels: {', '.join(extra)}")
            raise MetricError("; ".join(details))

        values: list[str] = []
        for name in self.label_names:
            value = str(labels[name])
            if any(ord(character) < 32 and character not in "\t\n" for character in value):
                raise MetricError(f"label {name!r} contains an unsupported control character")
            if len(value) > self.max_label_value_length:
                raise MetricError(
                    f"label {name!r} exceeds {self.max_label_value_length} characters"
                )
            values.append(value)
        return tuple(values)

    def _labels(self, key: tuple[str, ...]) -> dict[str, str]:
        return dict(zip(self.label_names, key, strict=True))

    def _render_labels(self, key: tuple[str, ...], extra: tuple[tuple[str, str], ...] = ()) -> str:
        pairs = [*zip(self.label_names, key, strict=True), *extra]
        if not pairs:
            return ""
        rendered = ",".join(f'{name}="{_escape_label(value)}"' for name, value in pairs)
        return "{" + rendered + "}"

    def definition(self) -> tuple[object, ...]:
        return (self.kind, self.description, self.label_names, self.max_series)

    def snapshot(self) -> dict[str, object]:
        raise NotImplementedError

    def query(self, aggregation: str) -> list[MetricSample]:
        raise NotImplementedError

    def prometheus_lines(self) -> list[str]:
        raise NotImplementedError


class Counter(_Instrument):
    """A monotonically increasing labeled counter."""

    kind = "counter"

    def __init__(
        self,
        name: str,
        description: str,
        label_names: Sequence[str] = (),
        *,
        max_series: int = 100,
        max_label_value_length: int = 200,
    ) -> None:
        super().__init__(
            name,
            description,
            label_names,
            max_series=max_series,
            max_label_value_length=max_label_value_length,
        )
        self._values: dict[tuple[str, ...], float] = {}

    def inc(self, amount: float = 1.0, **labels: object) -> None:
        increment = _finite_number(amount, field_name="counter increment")
        if increment < 0:
            raise MetricError("counter increments cannot be negative")
        key = self._key(labels)
        with self._lock:
            if key not in self._values and len(self._values) >= self.max_series:
                raise CardinalityLimitError(
                    f"metric {self.name!r} reached its {self.max_series}-series limit"
                )
            self._values[key] = _finite_sum(
                self._values.get(key, 0.0),
                increment,
                field_name="counter value",
            )

    def value(self, **labels: object) -> float:
        key = self._key(labels)
        with self._lock:
            return self._values.get(key, 0.0)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            series = [
                {"labels": self._labels(key), "value": value}
                for key, value in sorted(self._values.items())
            ]
        return {
            "name": self.name,
            "type": self.kind,
            "description": self.description,
            "series": series,
        }

    def query(self, aggregation: str = "value") -> list[MetricSample]:
        if aggregation != "value":
            raise MetricError("counters support only the 'value' aggregation")
        with self._lock:
            return [
                MetricSample(self.name, self._labels(key), aggregation, value)
                for key, value in sorted(self._values.items())
            ]

    def prometheus_lines(self) -> list[str]:
        with self._lock:
            samples = [
                f"{self.name}{self._render_labels(key)} {_format_float(value)}"
                for key, value in sorted(self._values.items())
            ]
        return [
            f"# HELP {self.name} {_escape_help(self.description)}",
            f"# TYPE {self.name} counter",
            *samples,
        ]


class Gauge(_Instrument):
    """A labeled value that may increase or decrease."""

    kind = "gauge"

    def __init__(
        self,
        name: str,
        description: str,
        label_names: Sequence[str] = (),
        *,
        max_series: int = 100,
        max_label_value_length: int = 200,
    ) -> None:
        super().__init__(
            name,
            description,
            label_names,
            max_series=max_series,
            max_label_value_length=max_label_value_length,
        )
        self._values: dict[tuple[str, ...], float] = {}

    def set(self, value: float, **labels: object) -> None:
        normalized = _finite_number(value)
        key = self._key(labels)
        with self._lock:
            if key not in self._values and len(self._values) >= self.max_series:
                raise CardinalityLimitError(
                    f"metric {self.name!r} reached its {self.max_series}-series limit"
                )
            self._values[key] = normalized

    def inc(self, amount: float = 1.0, **labels: object) -> None:
        delta = _finite_number(amount, field_name="gauge increment")
        key = self._key(labels)
        with self._lock:
            if key not in self._values and len(self._values) >= self.max_series:
                raise CardinalityLimitError(
                    f"metric {self.name!r} reached its {self.max_series}-series limit"
                )
            self._values[key] = _finite_sum(
                self._values.get(key, 0.0),
                delta,
                field_name="gauge value",
            )

    def dec(self, amount: float = 1.0, **labels: object) -> None:
        self.inc(-_finite_number(amount, field_name="gauge decrement"), **labels)

    def value(self, **labels: object) -> float | None:
        key = self._key(labels)
        with self._lock:
            return self._values.get(key)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            series = [
                {"labels": self._labels(key), "value": value}
                for key, value in sorted(self._values.items())
            ]
        return {
            "name": self.name,
            "type": self.kind,
            "description": self.description,
            "series": series,
        }

    def query(self, aggregation: str = "value") -> list[MetricSample]:
        if aggregation != "value":
            raise MetricError("gauges support only the 'value' aggregation")
        with self._lock:
            return [
                MetricSample(self.name, self._labels(key), aggregation, value)
                for key, value in sorted(self._values.items())
            ]

    def prometheus_lines(self) -> list[str]:
        with self._lock:
            samples = [
                f"{self.name}{self._render_labels(key)} {_format_float(value)}"
                for key, value in sorted(self._values.items())
            ]
        return [
            f"# HELP {self.name} {_escape_help(self.description)}",
            f"# TYPE {self.name} gauge",
            *samples,
        ]


class Histogram(_Instrument):
    """A labeled histogram with all-time aggregates and bounded recent samples."""

    kind = "histogram"

    def __init__(
        self,
        name: str,
        description: str,
        label_names: Sequence[str] = (),
        *,
        buckets: Sequence[float] = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
        max_series: int = 100,
        max_samples: int = 1024,
        max_label_value_length: int = 200,
    ) -> None:
        super().__init__(
            name,
            description,
            label_names,
            max_series=max_series,
            max_label_value_length=max_label_value_length,
        )
        if "le" in self.label_names:
            raise MetricError("histogram label name 'le' is reserved")
        if max_samples < 1:
            raise MetricError("max_samples must be at least 1")
        normalized_buckets = tuple(
            _finite_number(bucket, field_name="histogram bucket") for bucket in buckets
        )
        if not normalized_buckets or tuple(sorted(set(normalized_buckets))) != normalized_buckets:
            raise MetricError("histogram buckets must be unique and strictly increasing")

        self.buckets = normalized_buckets
        self.max_samples = max_samples
        self._series: dict[tuple[str, ...], _HistogramSeries] = {}

    def definition(self) -> tuple[object, ...]:
        return (*super().definition(), self.buckets, self.max_samples)

    def observe(self, value: float, **labels: object) -> None:
        observation = _finite_number(value, field_name="histogram observation")
        key = self._key(labels)
        with self._lock:
            series = self._series.get(key)
            if series is None:
                if len(self._series) >= self.max_series:
                    raise CardinalityLimitError(
                        f"metric {self.name!r} reached its {self.max_series}-series limit"
                    )
                series = _HistogramSeries(
                    bucket_counts=[0] * len(self.buckets),
                    recent=deque(maxlen=self.max_samples),
                )

            updated_total = _finite_sum(
                series.total,
                observation,
                field_name="histogram sum",
            )
            self._series.setdefault(key, series)

            series.count += 1
            series.total = updated_total
            series.minimum = (
                observation if series.minimum is None else min(series.minimum, observation)
            )
            series.maximum = (
                observation if series.maximum is None else max(series.maximum, observation)
            )
            for index, upper_bound in enumerate(self.buckets):
                if observation <= upper_bound:
                    series.bucket_counts[index] += 1
            series.recent.append(observation)

    def _summary(self, series: _HistogramSeries) -> dict[str, object]:
        values = list(series.recent)
        return {
            "count": series.count,
            "sum": series.total,
            "min": series.minimum,
            "max": series.maximum,
            "avg": series.total / series.count,
            "recent_count": len(values),
            "percentiles": {
                "p50": _percentile(values, 50),
                "p90": _percentile(values, 90),
                "p95": _percentile(values, 95),
                "p99": _percentile(values, 99),
            },
            "buckets": [
                {"le": upper_bound, "count": series.bucket_counts[index]}
                for index, upper_bound in enumerate(self.buckets)
            ],
        }

    def summary(self, **labels: object) -> dict[str, object] | None:
        key = self._key(labels)
        with self._lock:
            series = self._series.get(key)
            return None if series is None else self._summary(series)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            series = [
                {"labels": self._labels(key), **self._summary(value)}
                for key, value in sorted(self._series.items())
            ]
        return {
            "name": self.name,
            "type": self.kind,
            "description": self.description,
            "series": series,
        }

    def query(self, aggregation: str = "avg") -> list[MetricSample]:
        if aggregation not in _HISTOGRAM_AGGREGATIONS:
            supported = ", ".join(sorted(_HISTOGRAM_AGGREGATIONS))
            raise MetricError(f"unsupported histogram aggregation; choose one of: {supported}")

        with self._lock:
            samples: list[MetricSample] = []
            for key, series in sorted(self._series.items()):
                if aggregation == "count":
                    value = float(series.count)
                elif aggregation == "sum":
                    value = series.total
                elif aggregation == "avg":
                    value = series.total / series.count
                elif aggregation == "min":
                    assert series.minimum is not None
                    value = series.minimum
                elif aggregation == "max":
                    assert series.maximum is not None
                    value = series.maximum
                else:
                    value = _percentile(list(series.recent), float(aggregation[1:]))
                samples.append(MetricSample(self.name, self._labels(key), aggregation, value))
            return samples

    def prometheus_lines(self) -> list[str]:
        with self._lock:
            samples: list[str] = []
            for key, series in sorted(self._series.items()):
                for index, upper_bound in enumerate(self.buckets):
                    label_text = self._render_labels(key, (("le", _format_float(upper_bound)),))
                    samples.append(f"{self.name}_bucket{label_text} {series.bucket_counts[index]}")
                samples.append(
                    f"{self.name}_bucket{self._render_labels(key, (('le', '+Inf'),))} "
                    f"{series.count}"
                )
                samples.append(
                    f"{self.name}_sum{self._render_labels(key)} {_format_float(series.total)}"
                )
                samples.append(f"{self.name}_count{self._render_labels(key)} {series.count}")
        return [
            f"# HELP {self.name} {_escape_help(self.description)}",
            f"# TYPE {self.name} histogram",
            *samples,
        ]


Instrument = Counter | Gauge | Histogram


class MetricRegistry:
    """Owns a bounded collection of metric definitions and their in-memory series."""

    def __init__(
        self,
        *,
        max_metrics: int = 1000,
        max_series_per_metric: int = 100,
        max_histogram_samples: int = 1024,
        max_label_value_length: int = 200,
    ) -> None:
        if max_metrics < 1:
            raise MetricError("max_metrics must be at least 1")
        if max_series_per_metric < 1:
            raise MetricError("max_series_per_metric must be at least 1")
        if max_histogram_samples < 1:
            raise MetricError("max_histogram_samples must be at least 1")
        if max_label_value_length < 1:
            raise MetricError("max_label_value_length must be at least 1")
        self.max_metrics = max_metrics
        self.max_series_per_metric = max_series_per_metric
        self.max_histogram_samples = max_histogram_samples
        self.max_label_value_length = max_label_value_length
        self._instruments: dict[str, Instrument] = {}
        self._lock = RLock()

    def _register(self, instrument: Instrument) -> Instrument:
        with self._lock:
            existing = self._instruments.get(instrument.name)
            if existing is not None:
                if existing.definition() != instrument.definition():
                    raise MetricError(
                        f"metric {instrument.name!r} is already registered "
                        "with a different definition"
                    )
                return existing
            if len(self._instruments) >= self.max_metrics:
                raise CardinalityLimitError(f"registry reached its {self.max_metrics}-metric limit")
            self._instruments[instrument.name] = instrument
            return instrument

    def counter(
        self,
        name: str,
        description: str,
        label_names: Sequence[str] = (),
        *,
        max_series: int | None = None,
    ) -> Counter:
        instrument = Counter(
            name,
            description,
            label_names,
            max_series=(self.max_series_per_metric if max_series is None else max_series),
            max_label_value_length=self.max_label_value_length,
        )
        registered = self._register(instrument)
        if not isinstance(registered, Counter):
            raise MetricError(f"metric {name!r} is not a counter")
        return registered

    def gauge(
        self,
        name: str,
        description: str,
        label_names: Sequence[str] = (),
        *,
        max_series: int | None = None,
    ) -> Gauge:
        instrument = Gauge(
            name,
            description,
            label_names,
            max_series=(self.max_series_per_metric if max_series is None else max_series),
            max_label_value_length=self.max_label_value_length,
        )
        registered = self._register(instrument)
        if not isinstance(registered, Gauge):
            raise MetricError(f"metric {name!r} is not a gauge")
        return registered

    def histogram(
        self,
        name: str,
        description: str,
        label_names: Sequence[str] = (),
        *,
        buckets: Sequence[float] = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
        max_series: int | None = None,
        max_samples: int | None = None,
    ) -> Histogram:
        instrument = Histogram(
            name,
            description,
            label_names,
            buckets=buckets,
            max_series=(self.max_series_per_metric if max_series is None else max_series),
            max_samples=(self.max_histogram_samples if max_samples is None else max_samples),
            max_label_value_length=self.max_label_value_length,
        )
        registered = self._register(instrument)
        if not isinstance(registered, Histogram):
            raise MetricError(f"metric {name!r} is not a histogram")
        return registered

    def get(self, name: str) -> Instrument:
        with self._lock:
            try:
                return self._instruments[name]
            except KeyError as exc:
                raise MetricError(f"metric {name!r} is not registered") from exc

    def query(self, name: str, aggregation: str = "value") -> list[MetricSample]:
        return self.get(name).query(aggregation)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            instruments = [self._instruments[name] for name in sorted(self._instruments)]
        return {
            "schema_version": "samsarix-analytics/v1",
            "limits": {
                "max_metrics": self.max_metrics,
                "max_series_per_metric": self.max_series_per_metric,
                "max_histogram_samples": self.max_histogram_samples,
                "max_label_value_length": self.max_label_value_length,
            },
            "metrics": [instrument.snapshot() for instrument in instruments],
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.snapshot(), indent=indent, sort_keys=True)

    def to_prometheus(self) -> str:
        with self._lock:
            instruments = [self._instruments[name] for name in sorted(self._instruments)]
        lines = [line for instrument in instruments for line in instrument.prometheus_lines()]
        return "\n".join(lines) + ("\n" if lines else "")


@contextmanager
def track_duration(histogram: Histogram, **labels: object) -> Iterator[None]:
    """Observe elapsed monotonic seconds in ``histogram`` on success or failure."""

    started = perf_counter()
    try:
        yield
    finally:
        histogram.observe(perf_counter() - started, **labels)
