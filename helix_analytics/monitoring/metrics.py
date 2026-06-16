"""
Helix Metrics Collection System
Real-time metrics tracking for Helix Collective components
"""

import logging
import os
import re
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import psutil

logger = logging.getLogger(__name__)


@dataclass
class Metric:
    """Single metric data point."""

    name: str
    value: float
    timestamp: float
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class MetricSummary:
    """Summary statistics for a metric."""

    name: str
    count: int
    min: float
    max: float
    avg: float
    sum: float
    last_value: float
    last_timestamp: float


class MetricsRegistry:
    """Central metrics registry for collecting and storing metrics."""

    _MAX_POINTS_PER_METRIC = 5_000  # Cap per-metric list to prevent unbounded growth

    def __init__(self):
        self._metrics: dict[str, list[Metric]] = defaultdict(list)
        self._counters: dict[str, float] = defaultdict(float)
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _trim_list(self, lst: list, max_size: int | None = None) -> list:
        """Trim a list to max_size, keeping the most recent entries."""
        cap = max_size or self._MAX_POINTS_PER_METRIC
        if len(lst) > cap:
            return lst[-cap:]
        return lst

    def increment(self, name: str, value: float = 1.0, tags: dict[str, str] | None = None):
        """Increment a counter metric."""
        with self._lock:
            self._counters[name] += value
            self._metrics[name].append(Metric(name=name, value=value, timestamp=time.time(), tags=tags or {}))
            self._metrics[name] = self._trim_list(self._metrics[name])

    def set_gauge(self, name: str, value: float, tags: dict[str, str] | None = None):
        """Set a gauge metric."""
        with self._lock:
            self._gauges[name] = value
            self._metrics[name].append(Metric(name=name, value=value, timestamp=time.time(), tags=tags or {}))
            self._metrics[name] = self._trim_list(self._metrics[name])

    def observe(self, name: str, value: float, tags: dict[str, str] | None = None):
        """Observe a histogram metric."""
        with self._lock:
            self._histograms[name].append(value)
            self._histograms[name] = self._trim_list(self._histograms[name])
            self._metrics[name].append(Metric(name=name, value=value, timestamp=time.time(), tags=tags or {}))
            self._metrics[name] = self._trim_list(self._metrics[name])

    def get_counter(self, name: str) -> float:
        """Get counter value."""
        return self._counters.get(name, 0.0)

    def get_gauge(self, name: str) -> float | None:
        """Get gauge value."""
        return self._gauges.get(name)

    def get_histogram_summary(self, name: str, percentiles: list[float] | None = None) -> dict[str, float]:
        """Get histogram summary statistics."""
        if percentiles is None:
            percentiles = [0.5, 0.9, 0.95, 0.99]

        values = sorted(self._histograms.get(name, []))
        if not values:
            return {}

        summary = {
            "count": len(values),
            "sum": sum(values),
            "avg": sum(values) / len(values),
            "min": values[0],
            "max": values[-1],
        }

        for p in percentiles:
            idx = int(p * len(values))
            summary[f"p{int(p * 100)}"] = values[idx]

        return summary

    def get_metric_summary(self, name: str) -> MetricSummary | None:
        """Get summary statistics for a metric."""
        with self._lock:
            metrics = self._metrics.get(name, [])
            if not metrics:
                return None

            values = [m.value for m in metrics]
            return MetricSummary(
                name=name,
                count=len(metrics),
                min=min(values),
                max=max(values),
                avg=sum(values) / len(values),
                sum=sum(values),
                last_value=values[-1],
                last_timestamp=metrics[-1].timestamp,
            )

    def get_all_metrics(self) -> dict[str, Any]:
        """Get all current metric values."""
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {k: self.get_histogram_summary(k) for k in self._histograms},
            }

    def reset(self):
        """Reset all metrics."""
        with self._lock:
            self._metrics.clear()
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()

    def cleanup_old_metrics(self, max_age_seconds: int = 3600):
        """Remove metrics older than max_age_seconds."""
        cutoff_time = time.time() - max_age_seconds

        with self._lock:
            for name, metrics in self._metrics.items():
                self._metrics[name] = [m for m in metrics if m.timestamp > cutoff_time]


class HelixMetrics:
    """High-level metrics interface for Helix components."""

    _instance: "HelixMetrics | None" = None

    def __init__(self):
        self.registry = MetricsRegistry()
        self.start_time = time.time()

    @classmethod
    def get_instance(cls) -> "HelixMetrics":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # Cache Metrics
    def cache_hit(self, tags: dict[str, str] | None = None):
        self.registry.increment("cache.hits", tags=tags)

    def cache_miss(self, tags: dict[str, str] | None = None):
        self.registry.increment("cache.misses", tags=tags)

    def cache_set(self, tags: dict[str, str] | None = None):
        self.registry.increment("cache.sets", tags=tags)

    def cache_delete(self, tags: dict[str, str] | None = None):
        self.registry.increment("cache.deletes", tags=tags)

    def cache_size(self, size: int):
        self.registry.set_gauge("cache.size", size)

    def cache_hit_rate(self) -> float:
        hits = self.registry.get_counter("cache.hits")
        misses = self.registry.get_counter("cache.misses")
        total = hits + misses
        return (hits / total * 100) if total > 0 else 0.0

    # HTTP Metrics
    def http_request(
        self,
        method: str,
        status: int,
        duration: float,
        tags: dict[str, str] | None = None,
    ):
        metric_tags = {"method": method, "status": str(status)}
        if tags:
            metric_tags.update(tags)

        self.registry.increment("http.requests_total", tags=metric_tags)
        self.registry.observe("http.request_duration_seconds", duration, tags=metric_tags)

        if status >= 500:
            self.registry.increment("http.errors_5xx", tags=metric_tags)
        elif status >= 400:
            self.registry.increment("http.errors_4xx", tags=metric_tags)

    # Agent Metrics
    def agent_execution(self, agent_name: str, duration: float, success: bool):
        tags = {"agent": agent_name, "success": str(success)}
        self.registry.increment("agent.executions_total", tags=tags)
        self.registry.observe("agent.execution_duration_seconds", duration, tags=tags)

        if success:
            self.registry.increment("agent.executions_success", tags=tags)
        else:
            self.registry.increment("agent.executions_failure", tags=tags)

    # System Metrics
    def system_optimization(self, speedup: float, coordination_delta: float):
        self.registry.set_gauge("system.speedup_factor", speedup)
        self.registry.set_gauge("system.coordination_delta", coordination_delta)
        self.registry.increment("system.optimizations_total")

    # System Metrics
    def system_uptime(self) -> float:
        return time.time() - self.start_time

    def system_cpu_usage(self) -> float:
        """Get current CPU usage percentage."""
        return psutil.cpu_percent(interval=1)

    def system_memory_usage(self) -> dict[str, float]:
        """Get memory usage statistics."""
        mem = psutil.virtual_memory()
        return {
            "total": mem.total / (1024**3),  # GB
            "available": mem.available / (1024**3),  # GB
            "used": mem.used / (1024**3),  # GB
            "percentage": mem.percent,
        }

    def system_disk_usage(self) -> dict[str, float]:
        """Get disk usage statistics."""
        disk = psutil.disk_usage("/")
        return {
            "total": disk.total / (1024**3),  # GB
            "used": disk.used / (1024**3),  # GB
            "free": disk.free / (1024**3),  # GB
            "percentage": disk.percent,
        }

    def process_memory_usage(self) -> dict[str, float]:
        """Get current process memory usage."""
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        return {
            "rss": mem_info.rss / (1024**2),  # MB
            "vms": mem_info.vms / (1024**2),  # MB
            "percentage": process.memory_percent(),
        }

    def update_system_metrics(self):
        """Update system performance metrics."""
        try:
            # CPU usage
            cpu_percent = self.system_cpu_usage()
            self.registry.set_gauge("system.cpu_percent", cpu_percent)

            # Memory usage
            mem_usage = self.system_memory_usage()
            self.registry.set_gauge("system.memory_total_gb", mem_usage["total"])
            self.registry.set_gauge("system.memory_used_gb", mem_usage["used"])
            self.registry.set_gauge("system.memory_percent", mem_usage["percentage"])

            # Disk usage
            disk_usage = self.system_disk_usage()
            self.registry.set_gauge("system.disk_total_gb", disk_usage["total"])
            self.registry.set_gauge("system.disk_used_gb", disk_usage["used"])
            self.registry.set_gauge("system.disk_percent", disk_usage["percentage"])

            # Process memory
            proc_mem = self.process_memory_usage()
            self.registry.set_gauge("process.memory_rss_mb", proc_mem["rss"])
            self.registry.set_gauge("process.memory_vms_mb", proc_mem["vms"])
            self.registry.set_gauge("process.memory_percent", proc_mem["percentage"])

        except Exception as e:
            # Log error but don't crash metrics collection
            logger.error("Error updating system metrics: %s", e)

    def get_dashboard_data(self) -> dict[str, Any]:
        """Get all metrics for dashboard display."""
        return {
            "uptime": self.system_uptime(),
            "cache": {
                "hits": self.registry.get_counter("cache.hits"),
                "misses": self.registry.get_counter("cache.misses"),
                "hit_rate": self.cache_hit_rate(),
                "size": self.registry.get_gauge("cache.size"),
            },
            "http": {
                "requests_total": self.registry.get_counter("http.requests_total"),
                "errors_4xx": self.registry.get_counter("http.errors_4xx"),
                "errors_5xx": self.registry.get_counter("http.errors_5xx"),
                "avg_duration": self.registry.get_metric_summary("http.request_duration_seconds"),
            },
            "agents": {
                "executions_total": self.registry.get_counter("agent.executions_total"),
                "success_rate": self._calculate_success_rate(),
            },
            "system": {
                "speedup_factor": self.registry.get_gauge("system.speedup_factor"),
                "coordination_delta": self.registry.get_gauge("system.coordination_delta"),
                "optimizations_total": self.registry.get_counter("system.optimizations_total"),
            },
        }

    def _calculate_success_rate(self) -> float:
        success = self.registry.get_counter("agent.executions_success")
        failure = self.registry.get_counter("agent.executions_failure")
        total = success + failure
        return (success / total * 100) if total > 0 else 0.0


def get_metrics() -> HelixMetrics:
    """Get global metrics instance."""
    return HelixMetrics.get_instance()


async def initialize() -> None:
    """Initialize the metrics system.

    This function ensures the metrics singleton is created and ready for use.
    Called during application startup.
    """
    # Get or create the singleton instance
    _ = get_metrics()
    # Any async initialization can be added here in the future


# ============================================================================
# Module-level convenience functions
# ============================================================================
# These are used by websocket_service.py and integration_hub.py which call
# `from apps.backend.monitoring import metrics` then `metrics.increment_counter(...)`.


async def increment_counter(name: str, tags: dict[str, str] | None = None) -> None:
    """Increment a counter metric (module-level convenience function)."""
    get_metrics().registry.increment(name, tags=tags)


async def set_gauge(name: str, value: float, tags: dict[str, str] | None = None) -> None:
    """Set a gauge metric (module-level convenience function)."""
    get_metrics().registry.set_gauge(name, value, tags=tags)


def _prometheus_metric_name(name: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9_:]", "_", name)
    if not sanitized or sanitized[0].isdigit():
        sanitized = f"helix_{sanitized}"
    if (
        not sanitized.startswith("helix_")
        and not sanitized.startswith("process_")
        and not sanitized.startswith("system_")
    ):
        sanitized = f"helix_{sanitized}"
    return sanitized


def render_prometheus_metrics() -> str:
    """Render collected metrics in Prometheus exposition format."""
    metric_sets = get_metrics().registry.get_all_metrics()
    lines: list[str] = []

    for name, value in sorted(metric_sets.get("counters", {}).items()):
        metric_name = _prometheus_metric_name(name)
        lines.append(f"# TYPE {metric_name} counter")
        lines.append(f"{metric_name} {float(value)}")

    for name, value in sorted(metric_sets.get("gauges", {}).items()):
        metric_name = _prometheus_metric_name(name)
        lines.append(f"# TYPE {metric_name} gauge")
        lines.append(f"{metric_name} {float(value)}")

    for name, summary in sorted(metric_sets.get("histograms", {}).items()):
        if not summary:
            continue

        metric_name = _prometheus_metric_name(name)
        lines.append(f"# TYPE {metric_name}_count gauge")
        lines.append(f"{metric_name}_count {float(summary.get('count', 0.0))}")
        lines.append(f"# TYPE {metric_name}_sum gauge")
        lines.append(f"{metric_name}_sum {float(summary.get('sum', 0.0))}")
        lines.append(f"# TYPE {metric_name}_avg gauge")
        lines.append(f"{metric_name}_avg {float(summary.get('avg', 0.0))}")

    return "\n".join(lines) + "\n"
