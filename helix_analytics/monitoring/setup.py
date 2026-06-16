"""
Copyright (c) 2025 Andrew John Ward. All Rights Reserved.
PROPRIETARY AND CONFIDENTIAL - See LICENSE file for terms.

🌀 Helix Collective - Monitoring Infrastructure Setup
Comprehensive monitoring system initialization and configuration
"""

import logging
import threading
import time
from datetime import UTC, datetime
from typing import Any

from apps.backend.core.performance_profiler import profiler
from apps.backend.core.sqlalchemy_integration import db_profiler
from apps.backend.types.agent_orchestration import (
    AlertRule,
    EventLog,
    EventType,
    HealthStatus,
    MonitoringConfig,
    SystemHealth,
)

logger = logging.getLogger(__name__)


class MonitoringSystem:
    """Central monitoring system for Helix Collective"""

    def __init__(self, config: MonitoringConfig):
        self.config = config
        self.is_running = False
        self.monitoring_thread: threading.Thread | None = None
        self.health_check_interval = config.health_check_interval_seconds
        self.metrics_interval = config.metrics_interval_seconds
        self.slow_query_threshold = config.slow_query_threshold_seconds
        self.memory_threshold = config.memory_threshold_mb
        self.cpu_threshold = config.cpu_threshold_percent

        # Monitoring state
        self.last_health_check: float | None = None
        self.health_history: list[Any] = []
        self.alert_rules: list[Any] = []
        self.event_log: list[Any] = []

        # Performance tracking
        self.performance_baseline: dict[str, Any] = {}
        self.anomaly_detection_enabled = True

        logger.info("🔧 Monitoring system initialized")

    def start(self) -> None:
        """Start the monitoring system"""
        if self.is_running:
            logger.warning("⚠️ Monitoring system already running")
            return

        self.is_running = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()

        logger.info("🚀 Monitoring system started")

    def stop(self) -> None:
        """Stop the monitoring system"""
        self.is_running = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)

        logger.info("🛑 Monitoring system stopped")

    def _monitoring_loop(self) -> None:
        """Main monitoring loop"""
        while self.is_running:
            try:
                if time.time() - (self.last_health_check or 0) > self.health_check_interval:
                    self._perform_health_check()
                    self.last_health_check = time.time()

                # Collect metrics
                self._collect_metrics()

                # Check alerts
                self._check_alerts()

                # Clean up old data
                self._cleanup_old_data()

                time.sleep(self.metrics_interval)

            except Exception as e:
                logger.error("Monitoring loop error: %s", e)
                time.sleep(5)  # Wait before retrying

    def _perform_health_check(self) -> None:
        """Perform comprehensive system health check"""
        try:
            system_health = profiler.get_system_report()

            # Get database health
            db_health = db_profiler.get_connection_pool_report()

            # Get agent health
            agent_health = self._get_agent_health()

            # Determine overall health
            overall_health = self._calculate_overall_health(system_health, db_health, agent_health)

            # Create health record
            health_record = SystemHealth(
                timestamp=datetime.now(UTC),
                overall_status=overall_health,
                database_status=self._get_health_status(db_health),
                redis_status=HealthStatus.HEALTHY,  # Assume healthy for now
                websocket_status=HealthStatus.HEALTHY,
                agent_network_status=self._get_health_status(agent_health),
                memory_usage_percent=system_health.get("memory_percent", 0),
                cpu_usage_percent=system_health.get("cpu_percent", 0),
                disk_usage_percent=system_health.get("disk_percent", 0),
                active_agents=agent_health.get("active_count", 0),
                total_agents=agent_health.get("total_count", 0),
                slow_queries_count=db_health.get("slow_query_count", 0),
                error_rate=agent_health.get("error_rate", 0),
                uptime_seconds=system_health.get("uptime", 0),
            )

            self.health_history.append(health_record)

            # Log health status
            logger.info(
                f"🏥 Health check: {health_record.overall_status.value} "
                f"(CPU: {health_record.cpu_usage_percent:.1f}%, "
                f"Memory: {health_record.memory_usage_percent:.1f}%)"
            )

        except Exception as e:
            logger.error("Health check failed: %s", e)

    def _get_agent_health(self) -> dict[str, Any]:
        """Get agent network health status from AgentFactory"""
        try:
            from apps.backend.helix_agent_swarm.agent_factory import AgentFactory

            agents = AgentFactory.create_all_agents()
            total_count = len(agents)
            active_count = sum(1 for a in agents if getattr(a, "status", "active") == "active")
            error_count = sum(1 for a in agents if getattr(a, "status", "") == "error")
            error_rate = error_count / total_count if total_count > 0 else 0.0

            return {
                "active_count": active_count,
                "total_count": total_count,
                "error_rate": error_rate,
                "avg_response_time": 0.5,
                "status": "healthy" if error_rate < 0.2 else "degraded",
            }
        except Exception as e:
            logger.warning("Could not get agent health: %s", e)
            return {
                "active_count": 0,
                "total_count": 0,
                "error_rate": 0.0,
                "avg_response_time": 0.0,
                "status": "unknown",
            }

    def _get_health_status(self, health_data: dict[str, Any]) -> HealthStatus:
        """Determine health status from health data"""
        status_str = health_data.get("status", "unknown")
        try:
            return HealthStatus(status_str.upper())
        except ValueError:
            return HealthStatus.UNKNOWN

    def _calculate_overall_health(
        self,
        system_health: dict[str, Any],
        db_health: dict[str, Any],
        agent_health: dict[str, Any],
    ) -> HealthStatus:
        """Calculate overall system health based on component health"""
        # Check critical thresholds
        cpu_usage = system_health.get("cpu_percent", 0)
        memory_usage = system_health.get("memory_percent", 0)
        disk_usage = system_health.get("disk_percent", 0)
        error_rate = agent_health.get("error_rate", 0)

        # Critical thresholds
        if cpu_usage > 95 or memory_usage > 95 or disk_usage > 95 or error_rate > 0.2:
            return HealthStatus.CRITICAL
        elif cpu_usage > 80 or memory_usage > 80 or disk_usage > 80 or error_rate > 0.1:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY

    def _collect_metrics(self) -> None:
        """Collect system metrics"""
        try:
            perf_metrics = profiler.get_process_report()

            # Collect database metrics
            db_metrics = db_profiler.get_query_performance_report()

            # Store metrics for analysis
            self._store_metrics(perf_metrics, db_metrics)

        except Exception as e:
            logger.error("Metrics collection failed: %s", e)

    def _store_metrics(self, perf_metrics: dict[str, Any], db_metrics: dict[str, Any]):
        """Store collected metrics for analysis"""
        # This would store metrics in a time-series database
        # For now, just log key metrics
        logger.debug(
            f"📊 Metrics: CPU={perf_metrics.get('cpu_percent', 0):.1f}%, "
            f"Memory={perf_metrics.get('memory_rss_mb', 0):.1f}MB"
        )

    def _check_alerts(self) -> None:
        """Check alert rules and trigger notifications"""
        try:
            system_health = profiler.get_system_report()

            # Check each alert rule
            for rule in self.alert_rules:
                if not rule.enabled:
                    continue

                # Evaluate alert condition
                if self._evaluate_alert_rule(rule, system_health):
                    self._trigger_alert(rule, system_health)

        except Exception as e:
            logger.error("Alert checking failed: %s", e)

    def _evaluate_alert_rule(self, rule: AlertRule, metrics: dict[str, Any]) -> bool:
        """Evaluate if an alert rule should trigger"""
        try:
            # Get the metric value from the metrics dict
            metric_value = metrics.get(rule.metric, 0)

            # Compare based on operator
            if rule.operator == ">":
                return metric_value > rule.threshold
            elif rule.operator == "<":
                return metric_value < rule.threshold
            elif rule.operator == ">=":
                return metric_value >= rule.threshold
            elif rule.operator == "<=":
                return metric_value <= rule.threshold
            elif rule.operator == "==":
                return metric_value == rule.threshold

            return False

        except Exception as e:
            logger.error("Alert rule evaluation failed: %s", e)
            return False

    def _trigger_alert(self, rule: AlertRule, metrics: dict[str, Any]) -> None:
        """Trigger an alert notification"""
        try:
            # Create alert message
            metric_value = metrics.get(rule.metric, 0)
            alert_message = (
                f"Alert '{rule.name}': {rule.metric} = {metric_value} (threshold: {rule.operator} {rule.threshold})"
            )

            # Log alert
            logger.warning(alert_message)

            # Send notifications to configured channels
            for channel in rule.notification_channels:
                self._send_notification(channel, alert_message, rule.severity)

            # Log event
            self._log_event(
                EventType.PERFORMANCE_ALERT,
                "monitoring_system",
                alert_message,
                {
                    "rule": rule.name,
                    "metric": rule.metric,
                    "value": metrics.get(rule.metric, 0),
                },
            )

        except Exception as e:
            logger.error("Alert triggering failed: %s", e)

    def _send_notification(self, channel: str, message: str, severity: str) -> None:
        """Send notification to specified channel"""
        # This would integrate with notification services
        # For now, just log
        logger.info("📢 Notification (%s): %s", channel, message)

    def _log_event(self, event_type: EventType, source: str, message: str, details: dict[str, Any]) -> None:
        """Log system event"""
        event = EventLog(
            event_type=event_type,
            timestamp=datetime.now(UTC),
            source=source,
            message=message,
            details=details,
            severity="info",  # Could be determined from event type
        )

        self.event_log.append(event)

        # Keep only last 1000 events
        if len(self.event_log) > 1000:
            self.event_log = self.event_log[-1000:]

    def _cleanup_old_data(self) -> None:
        """Clean up old monitoring data"""
        # Clean up old health records (keep last 1000)
        if len(self.health_history) > 1000:
            self.health_history = self.health_history[-1000:]

        # Clean up old events (keep last 1000)
        if len(self.event_log) > 1000:
            self.event_log = self.event_log[-1000:]

    def add_alert_rule(self, rule: AlertRule) -> None:
        """Add an alert rule"""
        self.alert_rules.append(rule)
        logger.info("✅ Alert rule added: %s", rule.name)

    def remove_alert_rule(self, rule_name: str) -> None:
        """Remove an alert rule"""
        self.alert_rules = [r for r in self.alert_rules if r.name != rule_name]
        logger.info("❌ Alert rule removed: %s", rule_name)

    def get_monitoring_report(self) -> dict[str, Any]:
        """Get comprehensive monitoring report"""
        return {
            "system_health": self.health_history[-1] if self.health_history else None,
            "health_history": self.health_history[-10:],  # Last 10 health checks
            "event_log": self.event_log[-50:],  # Last 50 events
            "alert_rules": [rule.model_dump() for rule in self.alert_rules],
            "monitoring_status": "running" if self.is_running else "stopped",
            "performance_metrics": profiler.get_process_report(),
            "database_metrics": db_profiler.get_query_performance_report(),
        }

    def get_performance_baseline(self) -> dict[str, Any]:
        """Get performance baseline for comparison"""
        return self.performance_baseline

    def update_performance_baseline(self) -> None:
        """Update performance baseline with current metrics"""
        try:
            # Get current metrics from profiler
            current_report = profiler.get_process_report()
            current_metrics = {
                "cpu_percent": current_report.get("cpu_percent", 0),
                "memory_rss_mb": current_report.get("memory_rss_mb", 0),
            }

            self.performance_baseline = {
                "cpu_baseline": current_metrics.get("cpu_percent", 0),
                "memory_baseline": current_metrics.get("memory_rss_mb", 0),
                "timestamp": datetime.now(UTC).isoformat(),
            }
            logger.info("Performance baseline updated")
        except Exception as e:
            logger.error("Failed to update performance baseline: %s", e)

    def enable_anomaly_detection(self) -> None:
        """Enable anomaly detection"""
        self.anomaly_detection_enabled = True
        logger.info("🔍 Anomaly detection enabled")

    def disable_anomaly_detection(self) -> None:
        """Disable anomaly detection"""
        self.anomaly_detection_enabled = False
        logger.info("🔍 Anomaly detection disabled")


# Global monitoring system instance
monitoring_system = None


def initialize_monitoring(config: MonitoringConfig) -> MonitoringSystem:
    """Initialize and start the monitoring system"""
    global monitoring_system

    if monitoring_system is None:
        monitoring_system = MonitoringSystem(config)
        monitoring_system.start()

    return monitoring_system


def get_monitoring_system() -> MonitoringSystem | None:
    """Get the global monitoring system instance"""
    return monitoring_system


def stop_monitoring() -> None:
    """Stop the monitoring system"""
    global monitoring_system

    if monitoring_system:
        monitoring_system.stop()
        monitoring_system = None
        logger.info("🛑 Global monitoring system stopped")


# Default alert rules
DEFAULT_ALERT_RULES = [
    AlertRule(
        name="High CPU Usage",
        metric="cpu_percent",
        threshold=80.0,
        operator=">",
        duration_seconds=60,
        severity="warning",
        enabled=True,
        notification_channels=["log"],
    ),
    AlertRule(
        name="Critical CPU Usage",
        metric="cpu_percent",
        threshold=95.0,
        operator=">",
        duration_seconds=30,
        severity="critical",
        enabled=True,
        notification_channels=["log"],
    ),
    AlertRule(
        name="High Memory Usage",
        metric="memory_percent",
        threshold=80.0,
        operator=">",
        duration_seconds=60,
        severity="warning",
        enabled=True,
        notification_channels=["log"],
    ),
    AlertRule(
        name="Critical Memory Usage",
        metric="memory_percent",
        threshold=95.0,
        operator=">",
        duration_seconds=30,
        severity="critical",
        enabled=True,
        notification_channels=["log"],
    ),
    AlertRule(
        name="High Error Rate",
        metric="error_rate",
        threshold=0.2,
        operator=">",
        duration_seconds=120,
        severity="critical",
        enabled=True,
        notification_channels=["log"],
    ),
]


def setup_default_monitoring() -> MonitoringSystem:
    """Setup monitoring with default configuration"""
    from apps.backend.types.agent_orchestration import MonitoringConfig

    default_config = MonitoringConfig(
        enabled=True,
        metrics_interval_seconds=60,
        health_check_interval_seconds=30,
        slow_query_threshold_seconds=1.0,
        memory_threshold_mb=1024,
        cpu_threshold_percent=80.0,
        log_level="INFO",
        alert_rules=DEFAULT_ALERT_RULES,
    )

    monitoring = initialize_monitoring(default_config)

    # Add default alert rules
    for rule in DEFAULT_ALERT_RULES:
        monitoring.add_alert_rule(rule)

    return monitoring
