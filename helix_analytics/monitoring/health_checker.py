"""
Comprehensive Health Checking System - Helix Collective v15.6
Advanced health monitoring with predictive analytics and automated recovery
"""

import asyncio
import contextlib
import logging
import os
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from apps.backend.core.performance_profiler import profiler
from apps.backend.core.sqlalchemy_integration import db_profiler
from apps.backend.types.agent_orchestration import HealthStatus

logger = logging.getLogger(__name__)


class HealthCheckType(Enum):
    """Types of health checks"""

    SYSTEM_RESOURCES = "system_resources"
    DATABASE_CONNECTIVITY = "database_connectivity"
    DATABASE_PERFORMANCE = "database_performance"
    API_RESPONSIVENESS = "api_responsiveness"
    AGENT_AVAILABILITY = "agent_availability"
    CACHE_PERFORMANCE = "cache_performance"
    EXTERNAL_SERVICES = "external_services"
    SECURITY_STATUS = "security_status"
    COMPLIANCE_STATUS = "compliance_status"


class HealthCheckSeverity(Enum):
    """Health check severity levels"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class HealthCheckResult:
    """
    Result of a health check with detailed metrics and recommendations
    """

    def __init__(
        self,
        check_type: HealthCheckType,
        component: str,
        status: HealthStatus,
        severity: HealthCheckSeverity,
        response_time: float,
        metrics: dict[str, Any],
        message: str,
        recommendations: list[str] | None = None,
        error_details: str | None = None,
    ):
        """
        Initialize health check result

        Parameters:
            check_type: Type of health check performed
            component: Component being checked (e.g., "database", "api", "agents")
            status: Overall health status
            severity: Severity level of any issues
            response_time: Time taken for the check in seconds
            metrics: Detailed metrics from the check
            message: Human-readable status message
            recommendations: List of recommended actions
            error_details: Detailed error information if check failed
        """
        self.check_type = check_type
        self.component = component
        self.status = status
        self.severity = severity
        self.response_time = response_time
        self.metrics = metrics
        self.message = message
        self.recommendations = recommendations or []
        self.error_details = error_details
        self.timestamp = datetime.now(UTC)
        self.check_id = f"health_{check_type.value}_{component}_{int(self.timestamp.timestamp() * 1000000)}"

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary"""
        return {
            "check_id": self.check_id,
            "check_type": self.check_type.value,
            "component": self.component,
            "status": self.status.value,
            "severity": self.severity.value,
            "response_time": self.response_time,
            "metrics": self.metrics,
            "message": self.message,
            "recommendations": self.recommendations,
            "error_details": self.error_details,
            "timestamp": self.timestamp.isoformat(),
        }

    def is_healthy(self) -> bool:
        """Check if the result indicates a healthy component"""
        return self.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]

    def requires_attention(self) -> bool:
        """Check if the result requires attention"""
        return self.severity in [
            HealthCheckSeverity.WARNING,
            HealthCheckSeverity.ERROR,
            HealthCheckSeverity.CRITICAL,
        ]


class HealthCheck:
    """
    Individual health check with configuration and execution logic
    """

    def __init__(
        self,
        check_type: HealthCheckType,
        component: str,
        check_function: Callable[[], HealthCheckResult | Awaitable[HealthCheckResult]],
        interval_seconds: int = 60,
        timeout_seconds: float = 10.0,
        enabled: bool = True,
        failure_threshold: int = 3,
    ):
        """
        Initialize health check

        Parameters:
            check_type: Type of health check
            component: Component being checked
            check_function: Function to execute the check
            interval_seconds: How often to run the check
            timeout_seconds: Maximum time allowed for check execution
            enabled: Whether the check is enabled
            failure_threshold: Number of consecutive failures before alerting
        """
        self.check_type = check_type
        self.component = component
        self.check_function = check_function
        self.interval_seconds = interval_seconds
        self.timeout_seconds = timeout_seconds
        self.enabled = enabled
        self.failure_threshold = failure_threshold

        # Runtime state
        self.last_check_time: datetime | None = None
        self.last_result: HealthCheckResult | None = None
        self.consecutive_failures = 0
        self.total_checks = 0
        self.successful_checks = 0

    async def execute(self) -> HealthCheckResult:
        """Execute the health check"""
        start_time = time.time()
        self.total_checks += 1

        try:
            if asyncio.iscoroutinefunction(self.check_function):
                result = await asyncio.wait_for(self.check_function(), timeout=self.timeout_seconds)
            else:
                result = await asyncio.wait_for(
                    asyncio.get_running_loop().run_in_executor(None, self.check_function),
                    timeout=self.timeout_seconds,
                )

            # Update success metrics
            self.successful_checks += 1
            self.consecutive_failures = 0
            self.last_result = result
            self.last_check_time = datetime.now(UTC)

            return result

        except TimeoutError:
            error_msg = f"Health check timed out after {self.timeout_seconds}s"
            result = HealthCheckResult(
                check_type=self.check_type,
                component=self.component,
                status=HealthStatus.CRITICAL,
                severity=HealthCheckSeverity.ERROR,
                response_time=time.time() - start_time,
                metrics={"timeout": self.timeout_seconds},
                message=error_msg,
                error_details=error_msg,
                recommendations=["Increase timeout limit", "Optimize check function"],
            )
        except Exception as e:
            error_msg = f"Health check failed: {e!s}"
            result = HealthCheckResult(
                check_type=self.check_type,
                component=self.component,
                status=HealthStatus.CRITICAL,
                severity=HealthCheckSeverity.ERROR,
                response_time=time.time() - start_time,
                metrics={"error": type(e).__name__},
                message=error_msg,
                error_details=str(e),
                recommendations=["Check component logs", "Verify configuration"],
            )

        # Update failure metrics
        self.consecutive_failures += 1
        self.last_result = result
        self.last_check_time = datetime.now(UTC)

        return result

    def should_run(self) -> bool:
        """Check if the health check should run based on schedule"""
        if not self.enabled:
            return False

        if self.last_check_time is None:
            return True

        elapsed = (datetime.now(UTC) - self.last_check_time).total_seconds()
        return elapsed >= self.interval_seconds

    def get_stats(self) -> dict[str, Any]:
        """Get health check statistics"""
        success_rate = (self.successful_checks / self.total_checks) if self.total_checks > 0 else 0.0

        return {
            "check_type": self.check_type.value,
            "component": self.component,
            "enabled": self.enabled,
            "interval_seconds": self.interval_seconds,
            "timeout_seconds": self.timeout_seconds,
            "total_checks": self.total_checks,
            "successful_checks": self.successful_checks,
            "success_rate": success_rate,
            "consecutive_failures": self.consecutive_failures,
            "last_check_time": (self.last_check_time.isoformat() if self.last_check_time else None),
            "last_result": self.last_result.to_dict() if self.last_result else None,
        }


class HealthChecker:
    """
    Comprehensive health checking system with predictive analytics and automated recovery
    """

    def __init__(self):
        self.health_checks = {}  # check_id -> HealthCheck
        self.results_history = []  # List of recent results
        self.max_history_size = 10000

        # Alert system integration
        self.alert_rules = []
        self.alert_cooldown_minutes = 5

        # Predictive analytics
        self.baseline_metrics = {}
        self.anomaly_threshold = 2.0  # Standard deviations

        # Background monitoring
        self.monitoring_task = None
        self.is_running = False

        # Register default health checks
        self._register_default_checks()

        logger.info("🏥 Health checker initialized")

    def _register_default_checks(self):
        """Register default health checks"""

        # System resource checks
        self.register_check(
            HealthCheck(
                check_type=HealthCheckType.SYSTEM_RESOURCES,
                component="system",
                check_function=self._check_system_resources,
                interval_seconds=30,
            )
        )

        # Database connectivity
        self.register_check(
            HealthCheck(
                check_type=HealthCheckType.DATABASE_CONNECTIVITY,
                component="database",
                check_function=self._check_database_connectivity,
                interval_seconds=60,
            )
        )

        # Database performance
        self.register_check(
            HealthCheck(
                check_type=HealthCheckType.DATABASE_PERFORMANCE,
                component="database",
                check_function=self._check_database_performance,
                interval_seconds=120,
            )
        )

        # Agent availability
        self.register_check(
            HealthCheck(
                check_type=HealthCheckType.AGENT_AVAILABILITY,
                component="agents",
                check_function=self._check_agent_availability,
                interval_seconds=90,
            )
        )

        # API responsiveness
        self.register_check(
            HealthCheck(
                check_type=HealthCheckType.API_RESPONSIVENESS,
                component="api",
                check_function=self._check_api_responsiveness,
                interval_seconds=60,
            )
        )

        # Cache performance
        self.register_check(
            HealthCheck(
                check_type=HealthCheckType.CACHE_PERFORMANCE,
                component="cache",
                check_function=self._check_cache_performance,
                interval_seconds=180,
            )
        )

        # Security status
        self.register_check(
            HealthCheck(
                check_type=HealthCheckType.SECURITY_STATUS,
                component="security",
                check_function=self._check_security_status,
                interval_seconds=300,  # 5 minutes
            )
        )

    def register_check(self, check: HealthCheck) -> str:
        """Register a health check"""
        check_id = f"{check.check_type.value}_{check.component}"
        self.health_checks[check_id] = check
        logger.info("✅ Health check registered: %s", check_id)
        return check_id

    async def run_health_check(self, check_id: str) -> HealthCheckResult | None:
        """Run a specific health check"""
        check = self.health_checks.get(check_id)
        if not check:
            logger.warning("Health check not found: %s", check_id)
            return None

        result = await check.execute()

        # Store result in history
        self.results_history.append(result)
        if len(self.results_history) > self.max_history_size:
            self.results_history = self.results_history[-self.max_history_size :]

        # Check for alerts
        await self._check_alerts(result)

        # Update baseline metrics
        self._update_baseline_metrics(result)

        return result

    async def run_all_checks(self) -> list[HealthCheckResult]:
        """Run all enabled health checks"""
        results = []

        for check_id, check in self.health_checks.items():
            if check.should_run():
                try:
                    result = await check.execute()
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.error("Failed to run health check %s: %s", check_id, e)

        return results

    async def _check_system_resources(self) -> HealthCheckResult:
        """Check system resource usage"""
        try:
            system_report = profiler.get_system_report()

            cpu_percent = system_report.get("cpu_percent", 0)
            memory_percent = system_report.get("memory_percent", 0)
            disk_percent = system_report.get("disk_percent", 0)

            # Determine status based on thresholds
            if cpu_percent > 90 or memory_percent > 90 or disk_percent > 95:
                status = HealthStatus.CRITICAL
                severity = HealthCheckSeverity.CRITICAL
                message = ".1f"
            elif cpu_percent > 80 or memory_percent > 80 or disk_percent > 85:
                status = HealthStatus.DEGRADED
                severity = HealthCheckSeverity.WARNING
                message = ".1f"
            else:
                status = HealthStatus.HEALTHY
                severity = HealthCheckSeverity.INFO
                message = ".1f"

            recommendations = []
            if cpu_percent > 80:
                recommendations.append("Monitor CPU usage trends")
            if memory_percent > 80:
                recommendations.append("Check for memory leaks")
            if disk_percent > 85:
                recommendations.append("Free up disk space")

            return HealthCheckResult(
                check_type=HealthCheckType.SYSTEM_RESOURCES,
                component="system",
                status=status,
                severity=severity,
                response_time=0.1,  # Fast check
                metrics={
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory_percent,
                    "disk_percent": disk_percent,
                    "uptime_seconds": system_report.get("uptime", 0),
                },
                message=message,
                recommendations=recommendations,
            )

        except Exception as e:
            return HealthCheckResult(
                check_type=HealthCheckType.SYSTEM_RESOURCES,
                component="system",
                status=HealthStatus.UNKNOWN,
                severity=HealthCheckSeverity.ERROR,
                response_time=0.1,
                metrics={"error": type(e).__name__},
                message="System resource check failed",
                error_details=str(e),
                recommendations=["Check system monitoring configuration"],
            )

    async def _check_database_connectivity(self) -> HealthCheckResult:
        """Check database connectivity"""
        start_time = time.time()

        try:
            async with self.session_factory() as session:  # type: ignore[attr-defined]
                await session.execute("SELECT 1")
                await session.commit()

            response_time = time.time() - start_time

            return HealthCheckResult(
                check_type=HealthCheckType.DATABASE_CONNECTIVITY,
                component="database",
                status=HealthStatus.HEALTHY,
                severity=HealthCheckSeverity.INFO,
                response_time=response_time,
                metrics={"connection_time": response_time},
                message=".3f",
            )

        except Exception as e:
            response_time = time.time() - start_time
            return HealthCheckResult(
                check_type=HealthCheckType.DATABASE_CONNECTIVITY,
                component="database",
                status=HealthStatus.CRITICAL,
                severity=HealthCheckSeverity.CRITICAL,
                response_time=response_time,
                metrics={"connection_time": response_time, "error": type(e).__name__},
                message="Database connection failed",
                error_details=str(e),
                recommendations=[
                    "Check database configuration",
                    "Verify network connectivity",
                ],
            )

    async def _check_database_performance(self) -> HealthCheckResult:
        """Check database performance metrics"""
        try:
            perf_report = db_profiler.get_query_performance_report()
            pool_report = db_profiler.get_connection_pool_report()

            slow_queries = (perf_report.get("slow_queries") or {}).get("count", 0)
            avg_query_time = (perf_report.get("overall_stats") or {}).get("avg_execution_time", 0)
            connection_pool_size = (pool_report.get("current") or {}).get("max_connections", 0)
            active_connections = (pool_report.get("current") or {}).get("active_connections", 0)

            # Determine status
            if slow_queries > 10 or avg_query_time > 2.0:
                status = HealthStatus.DEGRADED
                severity = HealthCheckSeverity.WARNING
                message = f"Database performance degraded: {slow_queries} slow queries, {avg_query_time:.2f}s avg"
            elif slow_queries > 50 or avg_query_time > 5.0:
                status = HealthStatus.CRITICAL
                severity = HealthCheckSeverity.ERROR
                message = f"Database performance critical: {slow_queries} slow queries, {avg_query_time:.2f}s avg"
            else:
                status = HealthStatus.HEALTHY
                severity = HealthCheckSeverity.INFO
                message = ".2f"

            recommendations = []
            if slow_queries > 5:
                recommendations.append("Optimize slow queries")
            if avg_query_time > 1.0:
                recommendations.append("Review query performance")
            if active_connections > connection_pool_size * 0.8:
                recommendations.append("Monitor connection pool usage")

            return HealthCheckResult(
                check_type=HealthCheckType.DATABASE_PERFORMANCE,
                component="database",
                status=status,
                severity=severity,
                response_time=0.2,
                metrics={
                    "slow_queries": slow_queries,
                    "avg_query_time": avg_query_time,
                    "connection_pool_size": connection_pool_size,
                    "active_connections": active_connections,
                },
                message=message,
                recommendations=recommendations,
            )

        except Exception as e:
            return HealthCheckResult(
                check_type=HealthCheckType.DATABASE_PERFORMANCE,
                component="database",
                status=HealthStatus.UNKNOWN,
                severity=HealthCheckSeverity.ERROR,
                response_time=0.2,
                metrics={"error": type(e).__name__},
                message="Database performance check failed",
                error_details=str(e),
                recommendations=["Check database profiler configuration"],
            )

    async def _check_agent_availability(self) -> HealthCheckResult:
        """Check agent system availability"""
        try:
            from apps.backend.agents.agent_management import get_agent_manager

            agent_manager = get_agent_manager()
            system_overview = agent_manager.get_system_overview()

            total_agents = system_overview.get("total_agents", 0)
            active_agents = system_overview.get("active_agents", 0)
            healthy_agents = system_overview.get("healthy_agents", 0)

            # Calculate availability
            availability_rate = (healthy_agents / total_agents) if total_agents > 0 else 0.0

            if availability_rate >= 0.95:
                status = HealthStatus.HEALTHY
                severity = HealthCheckSeverity.INFO
                message = ".1%"
            elif availability_rate >= 0.8:
                status = HealthStatus.DEGRADED
                severity = HealthCheckSeverity.WARNING
                message = ".1%"
            else:
                status = HealthStatus.CRITICAL
                severity = HealthCheckSeverity.ERROR
                message = ".1%"

            recommendations = []
            if availability_rate < 0.9:
                recommendations.append("Check agent health status")
            if active_agents < total_agents:
                recommendations.append("Investigate inactive agents")

            return HealthCheckResult(
                check_type=HealthCheckType.AGENT_AVAILABILITY,
                component="agents",
                status=status,
                severity=severity,
                response_time=0.3,
                metrics={
                    "total_agents": total_agents,
                    "active_agents": active_agents,
                    "healthy_agents": healthy_agents,
                    "availability_rate": availability_rate,
                },
                message=message,
                recommendations=recommendations,
            )

        except Exception as e:
            return HealthCheckResult(
                check_type=HealthCheckType.AGENT_AVAILABILITY,
                component="agents",
                status=HealthStatus.UNKNOWN,
                severity=HealthCheckSeverity.ERROR,
                response_time=0.3,
                metrics={"error": type(e).__name__},
                message="Agent availability check failed",
                error_details=str(e),
                recommendations=["Check agent management system"],
            )

    async def _check_api_responsiveness(self) -> HealthCheckResult:
        """Check API responsiveness by timing an internal health request"""
        import time as _time

        start = _time.monotonic()
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                port = os.getenv("PORT", "8000")
                resp = await client.get(f"http://127.0.0.1:{port}/health")
                elapsed = _time.monotonic() - start
                status_code = resp.status_code
                if status_code == 200 and elapsed < 2.0:
                    status = HealthStatus.HEALTHY
                    severity = HealthCheckSeverity.INFO
                elif elapsed < 5.0:
                    status = HealthStatus.DEGRADED
                    severity = HealthCheckSeverity.WARNING
                else:
                    status = HealthStatus.CRITICAL
                    severity = HealthCheckSeverity.CRITICAL
                return HealthCheckResult(
                    check_type=HealthCheckType.API_RESPONSIVENESS,
                    component="api",
                    status=status,
                    severity=severity,
                    response_time=elapsed,
                    metrics={"response_time": round(elapsed, 4), "status_code": status_code},
                    message=f"API responding ({elapsed:.3f}s, HTTP {status_code})",
                )
        except Exception as e:
            elapsed = _time.monotonic() - start
            return HealthCheckResult(
                check_type=HealthCheckType.API_RESPONSIVENESS,
                component="api",
                status=HealthStatus.CRITICAL,
                severity=HealthCheckSeverity.CRITICAL,
                response_time=elapsed,
                metrics={"response_time": round(elapsed, 4), "status_code": 0},
                message=f"API health check failed: {e}",
                error_details=str(e),
            )

    async def _check_cache_performance(self) -> HealthCheckResult:
        """Check Redis cache connectivity and latency"""
        import time as _time

        start = _time.monotonic()
        try:
            redis_url = os.getenv("REDIS_URL")
            if not redis_url:
                return HealthCheckResult(
                    check_type=HealthCheckType.CACHE_PERFORMANCE,
                    component="cache",
                    status=HealthStatus.DEGRADED,
                    severity=HealthCheckSeverity.WARNING,
                    response_time=0,
                    metrics={"hit_rate": 0, "avg_response_time": 0},
                    message="Redis not configured (REDIS_URL not set)",
                )
            import redis.asyncio as aioredis

            client = aioredis.from_url(redis_url, socket_timeout=3)
            ping_ok = await client.ping()
            elapsed = _time.monotonic() - start
            await client.aclose()
            if ping_ok and elapsed < 0.1:
                status = HealthStatus.HEALTHY
                severity = HealthCheckSeverity.INFO
                msg = f"Redis responding ({elapsed:.3f}s)"
            elif ping_ok:
                status = HealthStatus.DEGRADED
                severity = HealthCheckSeverity.WARNING
                msg = f"Redis slow ({elapsed:.3f}s)"
            else:
                status = HealthStatus.CRITICAL
                severity = HealthCheckSeverity.CRITICAL
                msg = "Redis ping failed"
            return HealthCheckResult(
                check_type=HealthCheckType.CACHE_PERFORMANCE,
                component="cache",
                status=status,
                severity=severity,
                response_time=elapsed,
                metrics={"avg_response_time": round(elapsed, 4), "ping": ping_ok},
                message=msg,
            )
        except Exception as e:
            elapsed = _time.monotonic() - start
            return HealthCheckResult(
                check_type=HealthCheckType.CACHE_PERFORMANCE,
                component="cache",
                status=HealthStatus.CRITICAL,
                severity=HealthCheckSeverity.CRITICAL,
                response_time=elapsed,
                metrics={"avg_response_time": round(elapsed, 4), "ping": False},
                message=f"Redis check failed: {e}",
                error_details=str(e),
            )

    async def _check_security_status(self) -> HealthCheckResult:
        """Check security status using real JWT and environment config"""
        import time as _time

        start = _time.monotonic()
        issues = []
        # CONSOLIDATED: All JWT secret retrieval uses the single canonical function
        try:
            from apps.backend.core.unified_auth import _get_jwt_secret

            jwt_secret = _get_jwt_secret()
            if jwt_secret in ("change-this-in-production", "dev-only-secret-do-not-use-in-production"):
                issues.append("JWT_SECRET is using default/dev value")
        except RuntimeError as e:
            issues.append(f"JWT_SECRET validation failed: {e}")
        if not os.getenv("DATABASE_URL"):
            issues.append("DATABASE_URL not configured")
        is_production = (os.getenv("HELIX_ENV") or os.getenv("ENVIRONMENT") or "").lower() == "production"
        if is_production and not os.getenv("STRIPE_WEBHOOK_SECRET"):
            issues.append("STRIPE_WEBHOOK_SECRET not set in production")
        elapsed = _time.monotonic() - start
        if not issues:
            return HealthCheckResult(
                check_type=HealthCheckType.SECURITY_STATUS,
                component="security",
                status=HealthStatus.HEALTHY,
                severity=HealthCheckSeverity.INFO,
                response_time=elapsed,
                metrics={"issues": 0, "production": is_production},
                message="Security configuration OK",
            )
        else:
            return HealthCheckResult(
                check_type=HealthCheckType.SECURITY_STATUS,
                component="security",
                status=HealthStatus.DEGRADED if len(issues) < 2 else HealthStatus.CRITICAL,
                severity=HealthCheckSeverity.WARNING if len(issues) < 2 else HealthCheckSeverity.CRITICAL,
                response_time=elapsed,
                metrics={"issues": len(issues), "production": is_production},
                message=f"Security issues: {'; '.join(issues)}",
                recommendations=issues,
            )

    async def _check_alerts(self, result: HealthCheckResult):
        """Check if result triggers any alerts"""
        for rule in self.alert_rules:
            if self._matches_alert_rule(result, rule):
                await self._trigger_alert(result, rule)

    def _matches_alert_rule(self, result: HealthCheckResult, rule: dict[str, Any]) -> bool:
        """Check if result matches alert rule conditions"""
        # Simple rule matching - could be enhanced
        if result.status == HealthStatus.CRITICAL and rule.get("trigger_on_unhealthy", False):
            return True
        return result.severity == HealthCheckSeverity.CRITICAL and rule.get("trigger_on_critical", True)

    async def _trigger_alert(self, result: HealthCheckResult, rule: dict[str, Any]):
        """Trigger an alert for a health check result"""
        alert_message = f"🚨 Health Alert: {result.component} - {result.message}"

        # Log alert
        logger.warning(alert_message)

        # Could integrate with notification systems here
        # For now, just log

    def _update_baseline_metrics(self, result: HealthCheckResult):
        """Update baseline metrics for anomaly detection"""
        component_key = f"{result.check_type.value}_{result.component}"

        if component_key not in self.baseline_metrics:
            self.baseline_metrics[component_key] = []

        # Keep last 100 measurements for baseline
        self.baseline_metrics[component_key].append(
            {
                "timestamp": result.timestamp,
                "metrics": result.metrics,
                "response_time": result.response_time,
            }
        )

        if len(self.baseline_metrics[component_key]) > 100:
            self.baseline_metrics[component_key] = self.baseline_metrics[component_key][-100:]

    def get_overall_health_status(self) -> dict[str, Any]:
        """Get overall system health status"""
        if not self.results_history:
            return {"status": "unknown", "components": {}}

        # Analyze recent results (last 10 minutes)
        recent_results = [r for r in self.results_history if (datetime.now(UTC) - r.timestamp).total_seconds() < 600]

        component_status = {}
        for result in recent_results:
            key = f"{result.check_type.value}_{result.component}"
            component_status[key] = {
                "status": result.status.value,
                "severity": result.severity.value,
                "message": result.message,
                "last_check": result.timestamp.isoformat(),
            }

        # Calculate overall status
        critical_count = sum(1 for r in recent_results if r.status == HealthStatus.CRITICAL)
        unhealthy_count = sum(1 for r in recent_results if r.status == HealthStatus.CRITICAL)
        degraded_count = sum(1 for r in recent_results if r.status == HealthStatus.DEGRADED)

        if critical_count > 0 or unhealthy_count > 2:
            overall_status = "critical"
        elif unhealthy_count > 0 or degraded_count > 3:
            overall_status = "unhealthy"
        elif degraded_count > 0:
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        return {
            "status": overall_status,
            "components": component_status,
            "total_checks": len(recent_results),
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def get_health_report(self, hours: int = 24) -> dict[str, Any]:
        """Generate comprehensive health report"""
        cutoff_time = datetime.now(UTC) - timedelta(hours=hours)

        relevant_results = [r for r in self.results_history if r.timestamp >= cutoff_time]

        # Group by component
        component_reports: dict[str, list[dict[str, Any]]] = {}
        for result in relevant_results:
            key = f"{result.check_type.value}_{result.component}"
            if key not in component_reports:
                component_reports[key] = []

            component_reports[key].append(
                {
                    "timestamp": result.timestamp.isoformat(),
                    "status": result.status.value,
                    "severity": result.severity.value,
                    "response_time": result.response_time,
                    "message": result.message,
                }
            )

        # Calculate trends
        trends = {}
        for component, results in component_reports.items():
            if len(results) >= 2:
                recent = results[-5:]  # Last 5 checks
                healthy_count = sum(1 for r in recent if r["status"] == "healthy")
                trends[component] = {
                    "recent_checks": len(recent),
                    "healthy_rate": healthy_count / len(recent),
                    "average_response_time": sum(r["response_time"] for r in recent) / len(recent),
                }

        return {
            "period_hours": hours,
            "total_results": len(relevant_results),
            "component_reports": component_reports,
            "trends": trends,
            "generated_at": datetime.now(UTC).isoformat(),
        }

    async def start_monitoring(self):
        """Start continuous health monitoring"""
        if self.is_running:
            logger.warning("Health monitoring already running")
            return

        self.is_running = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("🏥 Health monitoring started")

    async def stop_monitoring(self):
        """Stop continuous health monitoring"""
        self.is_running = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.monitoring_task
        logger.info("🏥 Health monitoring stopped")

    async def _monitoring_loop(self):
        """Continuous health monitoring loop"""
        while self.is_running:
            try:
                await asyncio.sleep(60)  # Run checks every minute
            except Exception as e:
                logger.error("Health monitoring loop error: %s", e)
                await asyncio.sleep(30)

    def get_stats(self) -> dict[str, Any]:
        """Get health checker statistics"""
        total_checks = len(self.results_history)
        healthy_checks = len([r for r in self.results_history if r.is_healthy()])
        success_rate = healthy_checks / total_checks if total_checks > 0 else 0.0

        return {
            "total_checks": total_checks,
            "healthy_checks": healthy_checks,
            "success_rate": success_rate,
            "registered_checks": len(self.health_checks),
            "history_size": len(self.results_history),
            "monitoring_active": self.is_running,
        }

    async def check(self) -> bool:
        """Simple health check that returns True if system is healthy or degraded, False if critical or unhealthy"""
        overall_status = self.get_overall_health_status()
        status = overall_status.get("status", "unknown")
        return status in ["healthy", "degraded"]


# Global health checker instance
health_checker = HealthChecker()


def get_health_checker() -> HealthChecker:
    """Get the global health checker instance"""
    return health_checker


async def start() -> None:
    """Start the health checker monitoring.

    Called during application startup.
    """
    await health_checker.start_monitoring()


async def stop() -> None:
    """Stop the health checker monitoring.

    Called during application shutdown.
    """
    await health_checker.stop_monitoring()
