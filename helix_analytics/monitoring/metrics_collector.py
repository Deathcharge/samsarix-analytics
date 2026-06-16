"""
Metrics Collection System for Helix Platform

This module implements a comprehensive metrics collection system for monitoring
platform health, performance, and business metrics.

Features:
- Counter, Gauge, Histogram metrics
- Prometheus-compatible endpoint
- Custom business metrics
- Agent execution metrics
- Coordination field metrics
"""

import importlib.util
import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, overload

logger = logging.getLogger(__name__)

PROMETHEUS_AVAILABLE = importlib.util.find_spec("prometheus_client") is not None
if not PROMETHEUS_AVAILABLE:
    logger.warning("Prometheus client not available. Install with: pip install prometheus_client")


@dataclass
class MetricPoint:
    """A single metric data point."""

    timestamp: float
    value: float
    labels: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"timestamp": self.timestamp, "value": self.value, "labels": self.labels}


class TimeSeriesBuffer:
    """Buffer for storing recent metric data points."""

    def __init__(self, max_size: int = 100) -> None:
        self.max_size = max_size
        self.data: deque[MetricPoint] = deque(maxlen=max_size)
        self._lock = Lock()

    def add(self, point: MetricPoint) -> None:
        """Add a data point."""
        with self._lock:
            self.data.append(point)

    def get_recent(self, seconds: int | None = None) -> list[MetricPoint]:
        """Get recent data points."""
        with self._lock:
            if seconds is None:
                return list(self.data)

            cutoff = time.time() - seconds
            return [p for p in self.data if p.timestamp >= cutoff]

    def clear(self) -> None:
        """Clear all data."""
        with self._lock:
            self.data.clear()


class Metric:
    """Base class for custom metrics."""

    def __init__(self, name: str, description: str, labels: list[str] | None = None) -> None:
        self.name = name
        self.description = description
        self.labels = labels or []
        self._buffer = TimeSeriesBuffer()
        self._lock = Lock()

    def record(self, value: float, **label_values: Any) -> None:
        """Record a metric value."""
        labels = {k: str(v) for k, v in label_values.items()}
        point = MetricPoint(timestamp=time.time(), value=value, labels=labels)
        self._buffer.add(point)

    def get_data(self, seconds: int | None = None) -> list[MetricPoint]:
        """Get recent metric data."""
        return self._buffer.get_recent(seconds)


class CounterMetric(Metric):
    """Counter metric that only increases."""

    def __init__(self, name: str, description: str, labels: list[str] | None = None) -> None:
        super().__init__(name, description, labels)
        self._counters: dict[str, float] = defaultdict(float)

    def inc(self, amount: float = 1.0, **label_values: Any) -> None:
        """Increment the counter."""
        key = self._make_key(label_values)
        with self._lock:
            self._counters[key] += amount
        self.record(self._counters[key], **label_values)

    def get_value(self, **label_values) -> float:
        """Get current counter value."""
        key = self._make_key(label_values)
        return self._counters[key]

    def _make_key(self, label_values: dict[str, str]) -> str:
        """Create a key from label values."""
        return json.dumps(sorted(label_values.items()))


class GaugeMetric(Metric):
    """Gauge metric that can go up or down."""

    def __init__(self, name: str, description: str, labels: list[str] | None = None) -> None:
        super().__init__(name, description, labels)
        self._gauges: dict[str, float] = {}

    def set(self, value: float, **label_values: Any) -> None:
        """Set the gauge value."""
        key = self._make_key(label_values)
        with self._lock:
            self._gauges[key] = value
        self.record(value, **label_values)

    def inc(self, amount: float = 1.0, **label_values: Any) -> None:
        """Increment the gauge."""
        key = self._make_key(label_values)
        with self._lock:
            self._gauges[key] = self._gauges.get(key, 0) + amount
        self.record(self._gauges[key], **label_values)

    def dec(self, amount: float = 1.0, **label_values: Any) -> None:
        """Decrement the gauge."""
        key = self._make_key(label_values)
        with self._lock:
            self._gauges[key] = self._gauges.get(key, 0) - amount
        self.record(self._gauges[key], **label_values)

    def get_value(self, **label_values) -> float | None:
        """Get current gauge value."""
        key = self._make_key(label_values)
        return self._gauges.get(key)

    def _make_key(self, label_values: dict[str, str]) -> str:
        """Create a key from label values."""
        return json.dumps(sorted(label_values.items()))


class HistogramMetric(Metric):
    """Histogram metric that tracks value distributions."""

    def __init__(
        self, name: str, description: str, buckets: list[float] | None = None, labels: list[str] | None = None
    ) -> None:
        super().__init__(name, description, labels)
        self.buckets = buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
        self._observations: dict[str, list[float]] = defaultdict(list)

    def observe(self, value: float, **label_values: Any) -> None:
        """Observe a value."""
        key = self._make_key(label_values)
        with self._lock:
            self._observations[key].append(value)
        self.record(value, **label_values)

    def get_count(self, **label_values) -> int:
        """Get count of observations."""
        key = self._make_key(label_values)
        return len(self._observations.get(key, []))

    def get_sum(self, **label_values) -> float:
        """Get sum of observations."""
        key = self._make_key(label_values)
        return sum(self._observations.get(key, []))

    def get_avg(self, **label_values) -> float:
        """Get average of observations."""
        key = self._make_key(label_values)
        observations = self._observations.get(key, [])
        return sum(observations) / len(observations) if observations else 0.0

    def get_percentile(self, percentile: float, **label_values) -> float | None:
        """Get percentile of observations."""
        key = self._make_key(label_values)
        observations = sorted(self._observations.get(key, []))
        if not observations:
            return None
        k = (len(observations) - 1) * percentile / 100
        f = int(k)
        c = f + 1 if f + 1 < len(observations) else f
        return observations[f] + (k - f) * (observations[c] - observations[f])

    def _make_key(self, label_values: dict[str, str]) -> str:
        """Create a key from label values."""
        return json.dumps(sorted(label_values.items()))


class MetricsRegistry:
    """
    Registry for managing custom metrics.

    Provides centralized access to metrics for querying and export.
    """

    def __init__(self) -> None:
        self._counters: dict[str, CounterMetric] = {}
        self._gauges: dict[str, GaugeMetric] = {}
        self._histograms: dict[str, HistogramMetric] = {}
        self._lock = Lock()

    @overload
    def counter(self, name: str) -> CounterMetric: ...

    @overload
    def counter(self, name: str, description: str, labels: list[str] | None = None) -> CounterMetric: ...

    def counter(self, name: str, description: str | None = None, labels: list[str] | None = None) -> CounterMetric:
        """Get or create a counter metric."""
        with self._lock:
            if name not in self._counters:
                if description is None:
                    raise ValueError(f"Counter metric '{name}' is not registered")
                self._counters[name] = CounterMetric(name, description, labels)
            return self._counters[name]

    @overload
    def gauge(self, name: str) -> GaugeMetric: ...

    @overload
    def gauge(self, name: str, description: str, labels: list[str] | None = None) -> GaugeMetric: ...

    def gauge(self, name: str, description: str | None = None, labels: list[str] | None = None) -> GaugeMetric:
        """Get or create a gauge metric."""
        with self._lock:
            if name not in self._gauges:
                if description is None:
                    raise ValueError(f"Gauge metric '{name}' is not registered")
                self._gauges[name] = GaugeMetric(name, description, labels)
            return self._gauges[name]

    @overload
    def histogram(self, name: str) -> HistogramMetric: ...

    @overload
    def histogram(
        self,
        name: str,
        description: str,
        buckets: list[float] | None = None,
        labels: list[str] | None = None,
    ) -> HistogramMetric: ...

    def histogram(
        self,
        name: str,
        description: str | None = None,
        buckets: list[float] | None = None,
        labels: list[str] | None = None,
    ) -> HistogramMetric:
        """Get or create a histogram metric."""
        with self._lock:
            if name not in self._histograms:
                if description is None:
                    raise ValueError(f"Histogram metric '{name}' is not registered")
                self._histograms[name] = HistogramMetric(name, description, buckets, labels)
            return self._histograms[name]

    def get_all_metrics(self) -> dict[str, Any]:
        """Get all metrics data."""
        return {
            "counters": {name: metric.get_data() for name, metric in self._counters.items()},
            "gauges": {name: metric.get_data() for name, metric in self._gauges.items()},
            "histograms": {name: metric.get_data() for name, metric in self._histograms.items()},
        }

    def get_metric_summary(self) -> dict[str, Any]:
        """Get summary of all metrics."""
        summary: dict[str, dict[str, dict[str, Any]]] = {"counters": {}, "gauges": {}, "histograms": {}}

        for name, counter_metric in self._counters.items():
            summary["counters"][name] = {
                "description": counter_metric.description,
                "labels": counter_metric.labels,
                "current_value": counter_metric.get_value(),
            }

        for name, gauge_metric in self._gauges.items():
            summary["gauges"][name] = {
                "description": gauge_metric.description,
                "labels": gauge_metric.labels,
                "current_value": gauge_metric.get_value(),
            }

        for name, histogram_metric in self._histograms.items():
            summary["histograms"][name] = {
                "description": histogram_metric.description,
                "labels": histogram_metric.labels,
                "buckets": histogram_metric.buckets,
                "count": histogram_metric.get_count(),
                "sum": histogram_metric.get_sum(),
                "avg": histogram_metric.get_avg(),
                "p50": histogram_metric.get_percentile(50),
                "p95": histogram_metric.get_percentile(95),
                "p99": histogram_metric.get_percentile(99),
            }

        return summary


# Global metrics registry instance
metrics_registry = MetricsRegistry()


# Predefined metrics for Helix platform


def initialize_helix_metrics() -> None:
    """Initialize standard Helix platform metrics."""

    # Request metrics
    metrics_registry.counter("http_requests_total", "Total HTTP requests", labels=["method", "endpoint", "status"])

    metrics_registry.histogram("http_request_duration_seconds", "HTTP request duration", labels=["method", "endpoint"])

    # Agent metrics
    metrics_registry.counter(
        "agent_executions_total", "Total agent executions", labels=["agent_id", "agent_type", "status"]
    )

    metrics_registry.histogram("agent_execution_duration_seconds", "Agent execution duration", labels=["agent_id"])

    # Workflow metrics
    metrics_registry.counter("workflow_executions_total", "Total workflow executions", labels=["workflow_id", "status"])

    metrics_registry.histogram(
        "workflow_execution_duration_seconds", "Workflow execution duration", labels=["workflow_id"]
    )

    # LLM metrics
    metrics_registry.counter("llm_calls_total", "Total LLM API calls", labels=["provider", "model", "status"])

    metrics_registry.histogram("llm_call_duration_seconds", "LLM API call duration", labels=["provider", "model"])

    metrics_registry.counter(
        "llm_tokens_total",
        "Total LLM tokens used",
        labels=["provider", "model", "type"],  # prompt, completion
    )

    # Coordination metrics
    metrics_registry.gauge("coordination_field_value", "Coordination field values", labels=["field_name", "agent_id"])

    # Database metrics
    metrics_registry.counter("db_queries_total", "Total database queries", labels=["operation", "table", "status"])

    metrics_registry.histogram("db_query_duration_seconds", "Database query duration", labels=["operation", "table"])

    # User metrics
    metrics_registry.gauge("active_users", "Number of active users", labels=["subscription_tier"])

    metrics_registry.counter("user_sessions_total", "Total user sessions", labels=["auth_method"])

    # Spiral metrics
    metrics_registry.counter("spiral_executions_total", "Total spiral executions", labels=["spiral_id", "status"])

    metrics_registry.histogram("spiral_execution_duration_seconds", "Spiral execution duration", labels=["spiral_id"])

    logger.info("Helix platform metrics initialized")


# Utility functions for recording metrics


def record_http_request(method: str, endpoint: str, status: int, duration: float) -> None:
    """Record HTTP request metrics."""
    request_counter = metrics_registry.counter("http_requests_total")
    request_duration = metrics_registry.histogram("http_request_duration_seconds")

    request_counter.inc(method=method, endpoint=endpoint, status=status)
    request_duration.observe(duration, method=method, endpoint=endpoint)


def record_agent_execution(agent_id: str, agent_type: str, status: str, duration: float) -> None:
    """Record agent execution metrics."""
    execution_counter = metrics_registry.counter("agent_executions_total")
    execution_duration = metrics_registry.histogram("agent_execution_duration_seconds")

    execution_counter.inc(agent_id=agent_id, agent_type=agent_type, status=status)
    execution_duration.observe(duration, agent_id=agent_id)


def record_llm_call(
    provider: str, model: str, status: str, duration: float, prompt_tokens: int = 0, completion_tokens: int = 0
) -> None:
    """Record LLM call metrics."""
    call_counter = metrics_registry.counter("llm_calls_total")
    call_duration = metrics_registry.histogram("llm_call_duration_seconds")
    tokens_counter = metrics_registry.counter("llm_tokens_total")

    call_counter.inc(provider=provider, model=model, status=status)
    call_duration.observe(duration, provider=provider, model=model)
    tokens_counter.inc(prompt_tokens, provider=provider, model=model, type="prompt")
    tokens_counter.inc(completion_tokens, provider=provider, model=model, type="completion")


def record_coordination_field(field_name: str, agent_id: str, value: float) -> None:
    """Record coordination field metric."""
    field_gauge = metrics_registry.gauge("coordination_field_value")
    field_gauge.set(value, field_name=field_name, agent_id=agent_id)


def record_db_query(operation: str, table: str, status: str, duration: float) -> None:
    """Record database query metrics."""
    query_counter = metrics_registry.counter("db_queries_total")
    query_duration = metrics_registry.histogram("db_query_duration_seconds")

    query_counter.inc(operation=operation, table=table, status=status)
    query_duration.observe(duration, operation=operation, table=table)


def get_metrics_summary() -> dict[str, Any]:
    """Get summary of all metrics."""
    return metrics_registry.get_metric_summary()


def get_metrics_data(seconds: int | None = None) -> dict[str, Any]:
    """Get recent metrics data."""
    return metrics_registry.get_all_metrics()


# Initialize metrics on module import
initialize_helix_metrics()
