"""
📊 Performance Monitoring System
Comprehensive performance tracking and anomaly detection

Features:
- Real-time performance metrics
- Anomaly detection
- Historical trend analysis
- Alerting system
- Service health monitoring
"""

import asyncio
import logging
import statistics
import time
from collections import deque
from datetime import UTC, datetime, timedelta
from typing import Any

from apps.backend.cache_manager import get_cache_manager
from apps.backend.database import get_db_session

logger = logging.getLogger(__name__)

_background_tasks: set[asyncio.Task[Any]] = set()


class PerformanceMetrics:
    """Performance metrics collector"""

    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.response_times: deque[dict[str, Any]] = deque(maxlen=window_size)
        self.error_rates: deque[dict[str, Any]] = deque(maxlen=window_size)
        self.throughput: deque[float] = deque(maxlen=window_size)
        self.memory_usage: deque[dict[str, Any]] = deque(maxlen=window_size)
        self.database_queries: deque[dict[str, Any]] = deque(maxlen=window_size)
        self.start_time = datetime.now(UTC)
        self.total_requests = 0

        # Thresholds
        self.thresholds = {
            "response_time": 500,  # ms
            "error_rate": 5,  # %
            "memory_usage": 80,  # %
            "database_time": 100,  # ms
            "throughput_drop": 30,  # % drop
        }

        # Alerting
        self.alerts: list[dict[str, Any]] = []
        self.last_alert_time = 0
        self.alert_cooldown = 300  # 5 minutes

    def record_response_time(self, time_ms: float, endpoint: str = "unknown"):
        """Record API response time"""
        self.response_times.append({"time": time_ms, "endpoint": endpoint, "timestamp": time.time()})

    def record_error(self, endpoint: str = "unknown"):
        """Record an error occurrence"""
        self.error_rates.append({"endpoint": endpoint, "timestamp": time.time()})
        self.total_requests += 1

    def record_request(self):
        """Record a successful request for throughput calculation"""
        self.throughput.append(time.time())
        self.total_requests += 1

    def record_memory_usage(self, usage_percent: float):
        """Record memory usage"""
        self.memory_usage.append({"usage": usage_percent, "timestamp": time.time()})

    def record_database_query(self, query_time: float, query_type: str = "select"):
        """Record database query performance"""
        self.database_queries.append({"time": query_time, "type": query_type, "timestamp": time.time()})

    def check_anomalies(self) -> list[dict[str, Any]]:
        """Check for performance anomalies"""
        anomalies = []

        # Check response time anomalies
        if len(self.response_times) > 10:
            recent_times = [item["time"] for item in self.response_times][-10:]
            avg_time = statistics.mean(recent_times)
            if avg_time > self.thresholds["response_time"]:
                anomalies.append(
                    {
                        "type": "high_latency",
                        "metric": "response_time",
                        "value": f"{avg_time:.2f}ms",
                        "threshold": f"{self.thresholds['response_time']}ms",
                        "severity": ("high" if avg_time > self.thresholds["response_time"] * 2 else "medium"),
                    }
                )

        # Check error rate anomalies
        if len(self.error_rates) > 10:
            error_count = len(self.error_rates)
            total_requests = len(self.throughput) + error_count
            error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0

            if error_rate > self.thresholds["error_rate"]:
                anomalies.append(
                    {
                        "type": "high_error_rate",
                        "metric": "error_rate",
                        "value": f"{error_rate:.2f}%",
                        "threshold": f"{self.thresholds['error_rate']}%",
                        "severity": ("critical" if error_rate > self.thresholds["error_rate"] * 3 else "high"),
                    }
                )

        # Check memory usage anomalies
        if len(self.memory_usage) > 5:
            recent_memory = [item["usage"] for item in self.memory_usage][-5:]
            avg_memory = statistics.mean(recent_memory)
            if avg_memory > self.thresholds["memory_usage"]:
                anomalies.append(
                    {
                        "type": "high_memory_usage",
                        "metric": "memory_usage",
                        "value": f"{avg_memory:.2f}%",
                        "threshold": f"{self.thresholds['memory_usage']}%",
                        "severity": ("high" if avg_memory > self.thresholds["memory_usage"] + 10 else "medium"),
                    }
                )

        # Check database performance anomalies
        if len(self.database_queries) > 10:
            recent_queries = [item["time"] for item in self.database_queries][-10:]
            avg_query_time = statistics.mean(recent_queries)
            if avg_query_time > self.thresholds["database_time"]:
                anomalies.append(
                    {
                        "type": "slow_database_queries",
                        "metric": "database_query_time",
                        "value": f"{avg_query_time:.2f}ms",
                        "threshold": f"{self.thresholds['database_time']}ms",
                        "severity": ("high" if avg_query_time > self.thresholds["database_time"] * 3 else "medium"),
                    }
                )

        return anomalies

    def get_metrics_summary(self) -> dict[str, Any]:
        """Get summary of performance metrics"""
        summary = {
            "response_time": self._get_response_time_summary(),
            "error_rate": self._get_error_rate_summary(),
            "throughput": self._get_throughput_summary(),
            "memory_usage": self._get_memory_summary(),
            "database_queries": self._get_database_summary(),
            "anomalies": self.check_anomalies(),
        }
        return summary

    def _get_response_time_summary(self) -> dict[str, Any]:
        """Get response time summary"""
        if not self.response_times:
            return {"avg": 0, "p50": 0, "p90": 0, "p99": 0, "count": 0}

        times = [item["time"] for item in self.response_times]
        return {
            "avg": statistics.mean(times),
            "p50": statistics.median(times),
            "p90": statistics.quantiles(times, n=10)[8],
            "p99": statistics.quantiles(times, n=100)[98],
            "count": len(times),
            "max": max(times),
            "min": min(times),
        }

    def _get_error_rate_summary(self) -> dict[str, Any]:
        """Get error rate summary"""
        error_count = len(self.error_rates)
        success_count = len(self.throughput)
        total = error_count + success_count

        return {
            "error_count": error_count,
            "success_count": success_count,
            "total_requests": total,
            "error_rate": (error_count / total * 100) if total > 0 else 0,
            "success_rate": (success_count / total * 100) if total > 0 else 0,
        }

    def _get_throughput_summary(self) -> dict[str, Any]:
        """Get throughput summary"""
        if len(self.throughput) < 2:
            return {"rps": 0, "trend": "stable"}

        # Calculate requests per second
        time_window = self.throughput[-1] - self.throughput[0]
        if time_window > 0:
            rps = len(self.throughput) / time_window
        else:
            rps = 0

        return {
            "rps": rps,
            "trend": "stable",  # Would compare with historical data
            "total_requests": len(self.throughput),
        }

    def _get_memory_summary(self) -> dict[str, Any]:
        """Get memory usage summary"""
        if not self.memory_usage:
            return {"avg": 0, "max": 0, "current": 0}

        usages = [item["usage"] for item in self.memory_usage]
        return {
            "avg": statistics.mean(usages),
            "max": max(usages),
            "current": usages[-1] if usages else 0,
            "trend": "stable",  # Would compare with historical data
        }

    def _get_database_summary(self) -> dict[str, Any]:
        """Get database query summary"""
        if not self.database_queries:
            return {"avg_time": 0, "count": 0, "by_type": {}}

        times = [item["time"] for item in self.database_queries]
        by_type: dict[str, list[float]] = {}
        for query in self.database_queries:
            if query["type"] not in by_type:
                by_type[query["type"]] = []
            by_type[query["type"]].append(query["time"])

        type_summary = {}
        for qtype, qtimes in by_type.items():
            type_summary[qtype] = {
                "avg": statistics.mean(qtimes),
                "count": len(qtimes),
                "max": max(qtimes),
            }

        return {
            "avg_time": statistics.mean(times),
            "count": len(times),
            "max_time": max(times),
            "by_type": type_summary,
        }


class PerformanceAlertManager:
    """Performance alert management"""

    def __init__(self):
        self.cache = get_cache_manager()
        self.alerts: list[dict[str, Any]] = []
        self.max_alerts = 100

    async def trigger_alert(self, alert_type: str, severity: str, message: str, context: dict[str, Any]):
        """Trigger performance alert"""
        alert_id = f"alert_{int(time.time())}_{len(self.alerts)}"
        alert = {
            "id": alert_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "type": alert_type,
            "severity": severity,
            "message": message,
            "context": context,
            "acknowledged": False,
            "resolved": False,
        }

        # Store alert
        self.alerts.append(alert)
        if len(self.alerts) > self.max_alerts:
            self.alerts.pop(0)

        # Cache alert
        await self.cache.set(f"performance_alert:{alert_id}", alert, 86400)  # 24h

        # Log alert
        log_level = self._get_log_level(severity)
        getattr(logger, log_level)(f"🚨 PERFORMANCE ALERT: {alert_type} - {message}")

        # Send notification
        await self._send_notification(alert)

        return alert_id

    def _get_log_level(self, severity: str) -> str:
        """Get log level for severity"""
        severity_levels = {
            "critical": "error",
            "high": "warning",
            "medium": "warning",
            "low": "info",
        }
        return severity_levels.get(severity.lower(), "info")

    async def _send_notification(self, alert: dict[str, Any]):
        """Send alert notification"""
        try:
            from apps.backend.services.zapier_client_master import MasterZapierClient

            zapier_client = MasterZapierClient()
            notification_message = (
                f"🚨 {alert['severity'].upper()} PERFORMANCE ALERT 🚨\n"
                f"Type: {alert['type']}\n"
                f"Message: {alert['message']}\n"
                f"Context: {alert['context']}"
            )

            success = await zapier_client.send_discord_notification(
                channel_name="alerts",
                message=notification_message,
                priority=str(alert["severity"]),
            )

            if success:
                logger.info("✅ Performance alert sent via Discord notification")
                return
            else:
                logger.warning("⚠️ Failed to send performance alert via Discord")

        except ImportError:
            logger.warning("⚠️ MasterZapierClient not available for notifications")
        except Exception as e:
            logger.error("❌ Error sending performance notification: %s", str(e))

        # Fallback to logging
        notification_message = (
            f"🚨 {alert['severity'].upper()} PERFORMANCE ALERT 🚨\n"
            f"Type: {alert['type']}\n"
            f"Message: {alert['message']}\n"
            f"Context: {alert['context']}"
        )
        logger.warning("Notification sent via fallback logging: %s", notification_message)

    async def get_recent_alerts(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent alerts"""
        return self.alerts[-limit:]

    async def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge alert"""
        for alert in self.alerts:
            if alert["id"] == alert_id:
                alert["acknowledged"] = True
                await self.cache.set(f"performance_alert:{alert_id}", alert, 86400)
                return True
        return False

    async def resolve_alert(self, alert_id: str) -> bool:
        """Resolve alert"""
        for alert in self.alerts:
            if alert["id"] == alert_id:
                alert["resolved"] = True
                await self.cache.set(f"performance_alert:{alert_id}", alert, 86400)
                return True
        return False


class ServiceHealthMonitor:
    """Service health monitoring"""

    def __init__(self):
        self.services: dict[str, dict[str, Any]] = {}
        self.cache = get_cache_manager()

    async def check_service_health(self, service_name: str) -> dict[str, Any]:
        """Check health of a specific service with real connectivity tests"""
        import time as _time

        start = _time.monotonic()

        try:
            if service_name == "database":
                return await self._check_database_health(start)
            elif service_name == "cache":
                return await self._check_redis_health(start)
            elif service_name == "api":
                elapsed = _time.monotonic() - start
                return {
                    "service": "api",
                    "status": "healthy",
                    "response_time": round(elapsed * 1000, 1),
                    "error_rate": 0.0,
                    "last_check": datetime.now(UTC).isoformat(),
                }
            else:
                # For services without specific checks, report as healthy with no data
                return {
                    "service": service_name,
                    "status": "healthy",
                    "response_time": 0,
                    "error_rate": 0.0,
                    "last_check": datetime.now(UTC).isoformat(),
                    "note": "No dedicated health check configured",
                }
        except Exception as e:
            elapsed = _time.monotonic() - start
            return {
                "service": service_name,
                "status": "unhealthy",
                "response_time": round(elapsed * 1000, 1),
                "error_rate": 100.0,
                "last_check": datetime.now(UTC).isoformat(),
                "error": type(e).__name__,
            }

    async def _check_database_health(self, start: float) -> dict[str, Any]:
        """Real database health check"""
        import time as _time

        try:
            from sqlalchemy import text

            async with get_db_session() as session:
                await session.execute(text("SELECT 1"))
                elapsed = _time.monotonic() - start
                return {
                    "service": "database",
                    "status": "healthy" if elapsed < 1.0 else "degraded",
                    "response_time": round(elapsed * 1000, 1),
                    "error_rate": 0.0,
                    "last_check": datetime.now(UTC).isoformat(),
                }
        except Exception as e:
            elapsed = _time.monotonic() - start
            return {
                "service": "database",
                "status": "unhealthy",
                "response_time": round(elapsed * 1000, 1),
                "error_rate": 100.0,
                "last_check": datetime.now(UTC).isoformat(),
                "error": type(e).__name__,
            }

    async def _check_redis_health(self, start: float) -> dict[str, Any]:
        """Real Redis health check"""
        import os
        import time as _time

        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            return {
                "service": "cache",
                "status": "degraded",
                "response_time": 0,
                "error_rate": 0.0,
                "last_check": datetime.now(UTC).isoformat(),
                "note": "REDIS_URL not configured",
            }
        try:
            import redis.asyncio as aioredis

            client = aioredis.from_url(redis_url, socket_timeout=3)
            await client.ping()
            elapsed = _time.monotonic() - start
            await client.aclose()  # type: ignore[attr-defined]
            return {
                "service": "cache",
                "status": "healthy" if elapsed < 0.5 else "degraded",
                "response_time": round(elapsed * 1000, 1),
                "error_rate": 0.0,
                "last_check": datetime.now(UTC).isoformat(),
            }
        except Exception as e:
            elapsed = _time.monotonic() - start
            return {
                "service": "cache",
                "status": "unhealthy",
                "response_time": round(elapsed * 1000, 1),
                "error_rate": 100.0,
                "last_check": datetime.now(UTC).isoformat(),
                "error": type(e).__name__,
            }

    async def check_all_services(self) -> dict[str, dict[str, Any]]:
        """Check health of all real backend services"""
        services = ["api", "database", "cache"]
        health = {}

        for service in services:
            health[service] = await self.check_service_health(service)

        return health

    async def get_service_status(self) -> dict[str, Any]:
        """Get overall service status"""
        services = await self.check_all_services()

        healthy = sum(1 for s in services.values() if s["status"] == "healthy")
        degraded = sum(1 for s in services.values() if s["status"] == "degraded")
        down = sum(1 for s in services.values() if s["status"] == "down")

        return {
            "total_services": len(services),
            "healthy": healthy,
            "degraded": degraded,
            "down": down,
            "uptime_percentage": (healthy / len(services) * 100) if services else 0,
            "services": services,
        }


class PerformanceMonitor:
    """Main performance monitoring system"""

    def __init__(self):
        self.metrics = PerformanceMetrics()
        self.alert_manager = PerformanceAlertManager()
        self.health_monitor = ServiceHealthMonitor()
        self.cache = get_cache_manager()
        self.metrics_history: list[dict[str, Any]] = []  # Rolling history for get_historical_data()

        # Start background monitoring
        self._start_background_monitoring()

    def _start_background_monitoring(self):
        """Start background monitoring tasks"""
        _task = asyncio.create_task(self._background_anomaly_detection())
        _background_tasks.add(_task)
        _task.add_done_callback(_background_tasks.discard)
        _task = asyncio.create_task(self._background_health_checks())
        _background_tasks.add(_task)
        _task.add_done_callback(_background_tasks.discard)

    async def _background_anomaly_detection(self):
        """Background task for anomaly detection"""
        while True:
            try:
                anomalies: list[dict[str, Any]] = self.metrics.check_anomalies()
                for anomaly in anomalies:
                    await self.alert_manager.trigger_alert(
                        anomaly["type"],
                        anomaly["severity"],
                        f"{anomaly['type']} detected: {anomaly['metric']} = {anomaly['value']}",
                        {"metric": anomaly["metric"], "value": anomaly["value"]},
                    )
            except Exception as e:
                logger.error("❌ Background anomaly detection failed: %s", str(e))

            await asyncio.sleep(60)  # Check every minute

    async def _background_health_checks(self):
        """Background task for health checks"""
        while True:
            try:
                status = await self.health_monitor.get_service_status()
                if status["down"] > 0:
                    await self.alert_manager.trigger_alert(
                        "service_down",
                        "critical",
                        f"{status['down']} services are down",
                        {"services": status["services"]},
                    )
            except Exception as e:
                logger.error("❌ Background health checks failed: %s", str(e))

            await asyncio.sleep(300)  # Check every 5 minutes

    async def record_api_call(self, endpoint: str, response_time: float, success: bool):
        """Record API call metrics"""
        if success:
            self.metrics.record_response_time(response_time, endpoint)
            self.metrics.record_request()
        else:
            self.metrics.record_error(endpoint)

        # Append to rolling history (keep last 1440 entries = 24h at 1/min)
        self.metrics_history.append(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "avg_response_time": response_time,
                "error_rate": 0.0 if success else 1.0,
                "requests_per_second": (
                    self.metrics.total_requests / max(1, (datetime.now(UTC) - self.metrics.start_time).total_seconds())
                    if hasattr(self.metrics, "start_time")
                    else 0
                ),
            }
        )
        if len(self.metrics_history) > 1440:
            self.metrics_history = self.metrics_history[-1440:]

    async def record_database_query(self, query_time: float, query_type: str = "select"):
        """Record database query"""
        self.metrics.record_database_query(query_time, query_type)

    async def get_performance_dashboard(self) -> dict[str, Any]:
        """Get performance dashboard data"""
        return {
            "metrics": self.metrics.get_metrics_summary(),
            "alerts": await self.alert_manager.get_recent_alerts(),
            "service_status": await self.health_monitor.get_service_status(),
            "last_updated": datetime.now(UTC).isoformat(),
        }

    async def get_historical_data(self, hours: int = 24) -> dict[str, Any]:
        """Get historical performance data from in-memory metrics history"""
        # Return data collected by the monitoring loop
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        history = [entry for entry in self.metrics_history if entry.get("timestamp", "") >= cutoff.isoformat()]

        response_times = []
        error_rates = []
        throughput = []

        for entry in history:
            ts = entry.get("timestamp", "")
            if "avg_response_time" in entry:
                response_times.append({"timestamp": ts, "value": entry["avg_response_time"]})
            if "error_rate" in entry:
                error_rates.append({"timestamp": ts, "value": entry["error_rate"]})
            if "requests_per_second" in entry:
                throughput.append({"timestamp": ts, "value": entry["requests_per_second"]})

        return {
            "response_times": response_times,
            "error_rates": error_rates,
            "throughput": throughput,
        }

    async def get_alert_history(self, days: int = 7) -> list[dict[str, Any]]:
        """Get alert history"""
        # This would query database for alert history
        # For now, return recent alerts
        return await self.alert_manager.get_recent_alerts()


# Global performance monitor instance
_performance_monitor: PerformanceMonitor | None = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get global performance monitor instance"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor


# Convenience functions
async def record_api_performance(endpoint: str, response_time: float, success: bool = True):
    """Record API performance"""
    monitor = get_performance_monitor()
    await monitor.record_api_call(endpoint, response_time, success)


async def record_db_performance(query_time: float, query_type: str = "select"):
    """Record database performance"""
    monitor = get_performance_monitor()
    await monitor.record_database_query(query_time, query_type)


async def get_performance_status() -> dict[str, Any]:
    """Get performance status"""
    monitor = get_performance_monitor()
    return await monitor.get_performance_dashboard()


async def get_performance_alerts() -> list[dict[str, Any]]:
    """Get performance alerts"""
    monitor = get_performance_monitor()
    return await monitor.get_alert_history()
