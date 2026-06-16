"""
Advanced metrics collection and monitoring for Helix Unified Enterprise
Provides real-time performance monitoring, alerting, and analytics.
"""

import json
import logging
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import wraps
from typing import Any

import psutil

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Performance metric data structure"""

    endpoint: str
    method: str
    duration_ms: float
    status_code: int
    timestamp: datetime
    tenant_id: str | None = None
    user_id: str | None = None
    memory_usage_mb: float | None = None
    cpu_usage_percent: float | None = None
    error_type: str | None = None


@dataclass
class SystemMetric:
    """System-level metric data structure"""

    metric_type: str  # cpu, memory, disk, network
    value: float
    unit: str
    timestamp: datetime
    tags: dict[str, str] | None = None


class MetricsCollector:
    """Collects and manages performance metrics"""

    def __init__(self, max_metrics: int = 10000):
        self.metrics: deque = deque(maxlen=max_metrics)
        self.system_metrics: deque = deque(maxlen=max_metrics)
        self.error_counts: defaultdict = defaultdict(int)
        self.start_time = time.time()
        self.lock = threading.Lock()

        # Performance thresholds
        self.thresholds = {
            "response_time_ms": 1000,  # 1 second
            "error_rate_percent": 5.0,  # 5%
            "memory_usage_mb": 1024,  # 1GB
            "cpu_usage_percent": 80.0,  # 80%
        }

        # Alerting configuration
        self.alerts_enabled = True
        self.alert_callbacks: list[Callable] = []

        # Start background monitoring
        self._start_background_monitoring()

    def track_performance_metric(
        self,
        endpoint: str,
        method: str,
        duration_ms: float,
        status_code: int,
        tenant_id: str | None = None,
        user_id: str | None = None,
        error_type: str | None = None,
    ) -> None:
        """Track API performance metric"""
        metric = PerformanceMetric(
            endpoint=endpoint,
            method=method,
            duration_ms=duration_ms,
            status_code=status_code,
            timestamp=datetime.now(UTC),
            tenant_id=tenant_id,
            user_id=user_id,
            error_type=error_type,
        )

        with self.lock:
            self.metrics.append(metric)
            self._check_performance_alerts(metric)

            if error_type:
                self.error_counts[f"{endpoint}_{status_code}"] += 1

    def track_system_metric(
        self, metric_type: str, value: float, unit: str, tags: dict[str, str] | None = None
    ) -> None:
        """Track system-level metric"""
        metric = SystemMetric(
            metric_type=metric_type,
            value=value,
            unit=unit,
            timestamp=datetime.now(UTC),
            tags=tags or {},
        )

        with self.lock:
            self.system_metrics.append(metric)
            self._check_system_alerts(metric)

    def get_performance_summary(self, time_window_minutes: int = 60) -> dict[str, Any]:
        """Get performance summary for the specified time window"""
        cutoff_time = datetime.now(UTC) - timedelta(minutes=time_window_minutes)

        with self.lock:
            recent_metrics = [m for m in self.metrics if m.timestamp >= cutoff_time]

        if not recent_metrics:
            return {"error": "No metrics found"}

        # Calculate statistics
        total_requests = len(recent_metrics)
        successful_requests = len([m for m in recent_metrics if 200 <= m.status_code < 400])
        error_requests = len([m for m in recent_metrics if m.status_code >= 400])

        avg_response_time = sum(m.duration_ms for m in recent_metrics) / total_requests
        p95_response_time = self._percentile([m.duration_ms for m in recent_metrics], 95)
        p99_response_time = self._percentile([m.duration_ms for m in recent_metrics], 99)

        error_rate = (error_requests / total_requests) * 100 if total_requests > 0 else 0

        # Group by endpoint
        endpoint_stats = self._group_by_endpoint(recent_metrics)

        return {
            "time_window_minutes": time_window_minutes,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "error_requests": error_requests,
            "error_rate_percent": round(error_rate, 2),
            "avg_response_time_ms": round(avg_response_time, 2),
            "p95_response_time_ms": round(p95_response_time, 2),
            "p99_response_time_ms": round(p99_response_time, 2),
            "endpoints": endpoint_stats,
            "error_breakdown": self._get_error_breakdown(recent_metrics),
            "tenant_distribution": self._get_tenant_distribution(recent_metrics),
        }

    def get_system_health(self) -> dict[str, Any]:
        """Get current system health status"""
        with self.lock:
            recent_system_metrics = list(self.system_metrics)[-100:]  # Last 100 metrics

            health_status = {
                "cpu_usage_percent": self._get_latest_metric_value(recent_system_metrics, "cpu"),
                "memory_usage_mb": self._get_latest_metric_value(recent_system_metrics, "memory"),
                "disk_usage_percent": self._get_latest_metric_value(recent_system_metrics, "disk"),
                "network_io_mb": self._get_latest_metric_value(recent_system_metrics, "network"),
                "uptime_seconds": time.time() - self.start_time,
                "total_metrics_collected": len(self.metrics),
                "total_system_metrics": len(self.system_metrics),
                "alerts_triggered": self._get_recent_alerts(),
                "thresholds": self.thresholds,
            }

            return health_status

    def add_alert_callback(self, callback: Callable) -> None:
        """Add a callback function for alert notifications"""
        self.alert_callbacks.append(callback)

    def _check_performance_alerts(self, metric: PerformanceMetric) -> None:
        """Check if performance metric triggers alerts"""
        if not self.alerts_enabled:
            return

        alerts_triggered = []

        # Check response time
        if metric.duration_ms > self.thresholds["response_time_ms"]:
            alerts_triggered.append(f"Slow response: {metric.duration_ms:.2f}ms on {metric.endpoint}")

        # Check error rate
        if metric.status_code >= 400:
            endpoint_errors = self.error_counts.get(f"{metric.endpoint}_{metric.status_code}", 0)
            total_requests = len([m for m in self.metrics if m.endpoint == metric.endpoint])
            if total_requests > 0:
                error_rate = (endpoint_errors / total_requests) * 100
                if error_rate > self.thresholds["error_rate_percent"]:
                    alerts_triggered.append(f"High error rate: {error_rate:.2f}% on {metric.endpoint}")

        # Send alerts
        for alert in alerts_triggered:
            self._send_alert(alert, "performance")

    def _check_system_alerts(self, metric: SystemMetric) -> None:
        """Check if system metric triggers alerts"""
        if not self.alerts_enabled:
            return

        alerts_triggered = []

        if metric.metric_type == "memory" and metric.value > self.thresholds["memory_usage_mb"]:
            alerts_triggered.append(f"High memory usage: {metric.value}MB")
        elif metric.metric_type == "cpu" and metric.value > self.thresholds["cpu_usage_percent"]:
            alerts_triggered.append(f"High CPU usage: {metric.value}%")

        # Send alerts
        for alert in alerts_triggered:
            self._send_alert(alert, "system")

    def _send_alert(self, message: str, alert_type: str) -> None:
        """Send alert notification"""
        alert_data = {
            "type": alert_type,
            "message": message,
            "timestamp": datetime.now(UTC).isoformat(),
            "severity": "warning",
        }

        logger.warning("ALERT [%s]: %s", alert_type.upper(), message)

        # Notify callback functions
        for callback in self.alert_callbacks:
            try:
                callback(alert_data)
            except Exception as e:
                logger.error("Error in alert callback: %s", e)

    def _percentile(self, data: list[float], percentile: float) -> float:
        """Calculate percentile of data"""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[index]

    def _group_by_endpoint(self, metrics: list[PerformanceMetric]) -> dict[str, dict[str, Any]]:
        """Group metrics by endpoint"""
        groups: defaultdict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "count": 0,
                "avg_duration": 0,
                "error_rate": 0,
                "status_codes": defaultdict(int),
            }
        )

        for metric in metrics:
            group = groups[metric.endpoint]
            group["count"] += 1
            group["avg_duration"] += metric.duration_ms
            group["status_codes"][metric.status_code] += 1

            if metric.status_code >= 400:
                group["error_rate"] += 1

        # Calculate averages
        for _endpoint, stats in groups.items():
            if stats["count"] > 0:
                stats["avg_duration"] /= stats["count"]
                stats["error_rate"] = (stats["error_rate"] / stats["count"]) * 100

        return dict(groups)

    def _get_error_breakdown(self, metrics: list[PerformanceMetric]) -> dict[str, int]:
        """Get breakdown of error types"""
        errors: defaultdict[str, int] = defaultdict(int)
        for metric in metrics:
            if metric.error_type:
                errors[f"{metric.endpoint}_{metric.error_type}"] += 1
            elif metric.status_code >= 400:
                errors[f"{metric.endpoint}_{metric.status_code}"] += 1
        return dict(errors)

    def _get_tenant_distribution(self, metrics: list[PerformanceMetric]) -> dict[str, int]:
        """Get distribution of requests by tenant"""
        tenants: defaultdict[str, int] = defaultdict(int)
        for metric in metrics:
            if metric.tenant_id:
                tenants[metric.tenant_id] += 1
        return dict(tenants)

    def _get_latest_metric_value(self, metrics: list[SystemMetric], metric_type: str) -> float | None:
        """Get latest value for specific metric type"""
        filtered = [m for m in metrics if m.metric_type == metric_type]
        if filtered:
            return filtered[-1].value
        return None

    def _get_recent_alerts(self) -> list[str]:
        """Get recent alert messages (implementation dependent)"""
        # This would typically query an alert storage system
        return []

    def _start_background_monitoring(self) -> None:
        """Start background monitoring thread"""

        def monitor():
            while True:
                try:
                    time.sleep(30)  # Collect every 30 seconds
                except Exception as e:
                    logger.error("Error in background monitoring: %s", e)
                    time.sleep(60)

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()

    def _collect_system_metrics(self) -> None:
        """Collect system metrics"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.track_system_metric("cpu", cpu_percent, "%")

            # Memory usage
            memory = psutil.virtual_memory()
            self.track_system_metric("memory", memory.used / 1024 / 1024, "MB")

            # Disk usage
            disk = psutil.disk_usage("/")
            self.track_system_metric("disk", (disk.used / disk.total) * 100, "%")

            # Network I/O
            net_io = psutil.net_io_counters()
            self.track_system_metric("network", (net_io.bytes_sent + net_io.bytes_recv) / 1024 / 1024, "MB")

        except ImportError:
            logger.warning("psutil not available, system metrics disabled")
        except Exception as e:
            logger.error("Error collecting system metrics: %s", e)


@contextmanager
def track_performance(endpoint: str, method: str, tenant_id: str | None = None):
    """Context manager to track performance of code blocks"""
    start_time = time.time()
    try:
        duration_ms = (time.time() - start_time) * 1000
        metrics_collector.track_performance_metric(
            endpoint=endpoint,
            method=method,
            duration_ms=duration_ms,
            status_code=200,
            tenant_id=tenant_id,
        )
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        metrics_collector.track_performance_metric(
            endpoint=endpoint,
            method=method,
            duration_ms=duration_ms,
            status_code=500,
            tenant_id=tenant_id,
            error_type=type(e).__name__,
        )
        raise


# Global metrics collector instance
metrics_collector = MetricsCollector()


# Flask decorator for automatic metric collection
def monitor_endpoint(endpoint_name: str, tenant_aware: bool = True):
    """Decorator for Flask endpoints to automatically collect metrics"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            tenant_id = None

            if tenant_aware:
                # This would get tenant from request context
                # tenant_id = get_current_tenant()
                pass

            try:
                response = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                status_code = getattr(response, "status_code", 200)

                metrics_collector.track_performance_metric(
                    endpoint=endpoint_name,
                    method="GET",  # Default method since request context not available
                    duration_ms=duration_ms,
                    status_code=status_code,
                    tenant_id=tenant_id,
                )

                return response

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000

                metrics_collector.track_performance_metric(
                    endpoint=endpoint_name,
                    method="GET",  # Default method since request context not available
                    duration_ms=duration_ms,
                    status_code=500,
                    tenant_id=tenant_id,
                    error_type=type(e).__name__,
                )
                raise

        return wrapper

    return decorator


# Example usage and testing
if __name__ == "__main__":
    # Simulate some metrics

    def simulate_traffic():
        for i in range(100):
            # Simulate API calls
            metrics_collector.track_performance_metric(
                endpoint="/api/users",
                method="GET",
                duration_ms=50 + i % 100,
                status_code=200 if i % 10 != 0 else 500,
                tenant_id="tenant_123",
            )

            time.sleep(0.01)

    # Add alert callback
    def alert_callback(alert_data):
        logger.info("ALERT RECEIVED: %s", alert_data)

    metrics_collector.add_alert_callback(alert_callback)

    # Start simulation
    thread = threading.Thread(target=simulate_traffic)
    thread.start()
    thread.join()

    # Get performance summary
    summary = metrics_collector.get_performance_summary()
    logger.info("Performance Summary: %s", json.dumps(summary, indent=2, default=str))

    # Get system health
    health = metrics_collector.get_system_health()
    logger.info("System Health: %s", json.dumps(health, indent=2, default=str))
