"""
Helix Alerting System
Alert configuration and notification for Helix Collective
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Alert data structure."""

    id: str
    severity: AlertSeverity
    title: str
    message: str
    timestamp: datetime
    source: str
    metadata: dict[str, Any]
    resolved: bool = False
    resolved_at: datetime | None = None


@dataclass
class AlertRule:
    """Alert rule configuration."""

    name: str
    condition: Callable[[dict[str, Any]], bool]
    severity: AlertSeverity
    message_template: str
    cooldown_seconds: int = 300
    last_triggered: datetime | None = None


class AlertManager:
    """Central alert manager for monitoring and notifications."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.alerts: list[Alert] = []
        self.rules: dict[str, AlertRule] = {}
        self.alert_handlers: list[Callable[[Alert], None]] = []
        self._running = False
        self._task: asyncio.Task | None = None

    def add_rule(self, rule: AlertRule):
        """Add an alert rule."""
        self.rules[rule.name] = rule
        self.logger.info("Added alert rule: %s", rule.name)

    def remove_rule(self, rule_name: str):
        """Remove an alert rule."""
        if rule_name in self.rules:
            del self.rules[rule_name]
            self.logger.info("Removed alert rule: %s", rule_name)

    def add_handler(self, handler: Callable[[Alert], None]):
        """Add an alert handler (notification method)."""
        self.alert_handlers.append(handler)

    async def check_rules(self, metrics: dict[str, Any]):
        """Check all alert rules against current metrics."""
        for _rule_name, rule in self.rules.items():
            # Check cooldown
            if rule.last_triggered:
                cooldown_end = rule.last_triggered + timedelta(seconds=rule.cooldown_seconds)
                if datetime.now(UTC) < cooldown_end:
                    continue

            # Check condition
            try:
                await self._trigger_alert(rule, metrics)
            except Exception as e:
                self.logger.error("Error checking rule %s: %s", rule.name, e)

    async def _trigger_alert(self, rule: AlertRule, metrics: dict[str, Any]):
        """Trigger an alert."""
        alert = Alert(
            id=f"{rule.name}_{datetime.now(UTC).timestamp()}",
            severity=rule.severity,
            title=rule.name,
            message=rule.message_template.format(**metrics),
            timestamp=datetime.now(UTC),
            source="alert_manager",
            metadata=metrics.copy(),
        )

        self.alerts.append(alert)
        rule.last_triggered = datetime.now(UTC)

        self.logger.warning("Alert triggered: %s - %s", alert.title, alert.message)

        # Notify handlers
        for handler in self.alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                self.logger.error("Error in alert handler: %s", e)

    def resolve_alert(self, alert_id: str):
        """Resolve an alert."""
        for alert in self.alerts:
            if alert.id == alert_id and not alert.resolved:
                alert.resolved = True
                alert.resolved_at = datetime.now(UTC)
                self.logger.info("Alert resolved: %s", alert.title)
                break

    def get_active_alerts(self) -> list[Alert]:
        """Get all active (unresolved) alerts."""
        return [a for a in self.alerts if not a.resolved]

    def get_alert_history(self, limit: int = 100) -> list[Alert]:
        """Get alert history."""
        return self.alerts[-limit:]

    async def start_monitoring(self, check_interval: int = 60, metrics_provider: Callable | None = None):
        """Start continuous monitoring."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._monitoring_loop(check_interval, metrics_provider))
        self.logger.info("Alert monitoring started")

    async def stop_monitoring(self):
        """Stop continuous monitoring."""
        if self._task:
            self._task.cancel()
            self._running = False
            self.logger.info("Alert monitoring stopped")

    async def _monitoring_loop(self, check_interval: int, metrics_provider: Callable | None):
        """Monitoring loop."""
        while self._running:
            try:
                if metrics_provider is None:
                    await asyncio.sleep(check_interval)
                    continue
                metrics = metrics_provider()
                await self.check_rules(metrics)
            except Exception as e:
                self.logger.error("Error in monitoring loop: %s", e)

            await asyncio.sleep(check_interval)


class DefaultAlertRules:
    """Default alert rules for Helix system."""

    @staticmethod
    def get_rules() -> list[AlertRule]:
        """Get default alert rules."""
        return [
            AlertRule(
                name="high_cache_miss_rate",
                condition=lambda m: m.get("cache", {}).get("hit_rate", 100) < 50,
                severity=AlertSeverity.WARNING,
                message_template="Cache miss rate is {cache[hit_rate]:.1f}%",
                cooldown_seconds=300,
            ),
            AlertRule(
                name="critical_cache_miss_rate",
                condition=lambda m: m.get("cache", {}).get("hit_rate", 100) < 20,
                severity=AlertSeverity.CRITICAL,
                message_template="Critical cache miss rate: {cache[hit_rate]:.1f}%",
                cooldown_seconds=60,
            ),
            AlertRule(
                name="high_http_error_rate",
                condition=lambda m: m.get("http", {}).get("errors_5xx", 0) > 10,
                severity=AlertSeverity.ERROR,
                message_template="High HTTP 5xx error rate: {http[errors_5xx]} errors",
                cooldown_seconds=300,
            ),
            AlertRule(
                name="agent_execution_failure",
                condition=lambda m: m.get("agents", {}).get("success_rate", 100) < 80,
                severity=AlertSeverity.WARNING,
                message_template="Agent execution success rate: {agents[success_rate]:.1f}%",
                cooldown_seconds=300,
            ),
            AlertRule(
                name="low_speedup",
                condition=lambda m: m.get("system", {}).get("speedup_factor", 0) < 3.0,
                severity=AlertSeverity.INFO,
                message_template="System speedup factor: {system[speedup_factor]:.2f}x",
                cooldown_seconds=600,
            ),
        ]


class LogAlertHandler:
    """Log-based alert handler."""

    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or logging.getLogger(__name__)

    def __call__(self, alert: Alert):
        """Handle alert by logging."""
        if alert.severity == AlertSeverity.CRITICAL:
            self.logger.critical("[CRITICAL] %s: %s", alert.title, alert.message)
        elif alert.severity == AlertSeverity.ERROR:
            self.logger.error("[ERROR] %s: %s", alert.title, alert.message)
        elif alert.severity == AlertSeverity.WARNING:
            self.logger.warning("[WARNING] %s: %s", alert.title, alert.message)
        else:
            self.logger.info("[INFO] %s: %s", alert.title, alert.message)


def get_alert_manager() -> AlertManager:
    """Get global alert manager instance."""
    # In production, this would be a singleton
    manager = AlertManager()

    # Add default rules
    for rule in DefaultAlertRules.get_rules():
        manager.add_rule(rule)

    # Add log handler
    manager.add_handler(LogAlertHandler())

    return manager
