"""
Alert System - Helix Collective v15.6
Intelligent alerting with escalation, deduplication, and automated remediation
"""

import json
import logging
import os
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status"""

    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class AlertChannel(Enum):
    """Alert notification channels"""

    LOG = "log"
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    SMS = "sms"
    DATABASE = "database"


class AlertRule:
    """
    Alert rule with conditions and actions
    """

    def __init__(
        self,
        name: str,
        description: str,
        condition: Callable[[dict[str, Any]], bool],
        severity: AlertSeverity,
        channels: list[AlertChannel],
        cooldown_minutes: int = 5,
        enabled: bool = True,
        auto_resolve: bool = False,
        tags: list[str] | None = None,
    ):
        """
        Initialize alert rule

        Parameters:
            name: Unique rule name
            description: Human-readable description
            condition: Function that returns True if alert should trigger
            severity: Alert severity level
            channels: Notification channels
            cooldown_minutes: Minimum time between alerts for same issue
            enabled: Whether rule is enabled
            auto_resolve: Whether to auto-resolve when condition clears
            tags: Optional tags for categorization
        """
        self.name = name
        self.description = description
        self.condition = condition
        self.severity = severity
        self.channels = channels
        self.cooldown_minutes = cooldown_minutes
        self.enabled = enabled
        self.auto_resolve = auto_resolve
        self.tags = tags or []

    def to_dict(self) -> dict[str, Any]:
        """Convert rule to dictionary"""
        return {
            "name": self.name,
            "description": self.description,
            "severity": self.severity.value,
            "channels": [c.value for c in self.channels],
            "cooldown_minutes": self.cooldown_minutes,
            "enabled": self.enabled,
            "auto_resolve": self.auto_resolve,
            "tags": self.tags,
        }


class Alert:
    """
    Alert instance with state and metadata
    """

    def __init__(
        self,
        rule_name: str,
        title: str,
        message: str,
        severity: AlertSeverity,
        source: str,
        component: str | None = None,
        metrics: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ):
        """
        Initialize alert

        Parameters:
            rule_name: Name of the rule that triggered this alert
            title: Alert title
            message: Detailed alert message
            severity: Alert severity
            source: Source system/component
            component: Specific component affected
            metrics: Related metrics data
            tags: Alert tags
        """
        self.id = f"alert_{int(datetime.now(UTC).timestamp() * 1000000)}"
        self.rule_name = rule_name
        self.title = title
        self.message = message
        self.severity = severity
        self.source = source
        self.component = component
        self.metrics = metrics or {}
        self.tags = tags or []

        # State
        self.status = AlertStatus.ACTIVE
        self.created_at = datetime.now(UTC)
        self.updated_at = self.created_at
        self.acknowledged_at = None
        self.acknowledged_by = None
        self.resolved_at = None
        self.resolved_by = None

        # Notifications
        self.notifications_sent = []
        self.suppressed_until = None

    def acknowledge(self, user_id: str | None = None):
        """Acknowledge the alert"""
        self.status = AlertStatus.ACKNOWLEDGED
        self.acknowledged_at = datetime.now(UTC)
        self.acknowledged_by = user_id
        self.updated_at = self.acknowledged_at

    def resolve(self, user_id: str | None = None):
        """Resolve the alert"""
        self.status = AlertStatus.RESOLVED
        self.resolved_at = datetime.now(UTC)
        self.resolved_by = user_id
        self.updated_at = self.resolved_at

    def suppress(self, until: datetime):
        """Suppress the alert until specified time"""
        self.status = AlertStatus.SUPPRESSED
        self.suppressed_until = until
        self.updated_at = datetime.now(UTC)

    def is_suppressed(self) -> bool:
        """Check if alert is currently suppressed"""
        if self.status == AlertStatus.SUPPRESSED and self.suppressed_until:
            return datetime.now(UTC) < self.suppressed_until
        return False

    def to_dict(self) -> dict[str, Any]:
        """Convert alert to dictionary"""
        return {
            "id": self.id,
            "rule_name": self.rule_name,
            "title": self.title,
            "message": self.message,
            "severity": self.severity.value,
            "status": self.status.value,
            "source": self.source,
            "component": self.component,
            "metrics": self.metrics,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "acknowledged_at": (self.acknowledged_at.isoformat() if self.acknowledged_at else None),
            "acknowledged_by": self.acknowledged_by,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": self.resolved_by,
            "suppressed_until": (self.suppressed_until.isoformat() if self.suppressed_until else None),
            "notifications_sent": self.notifications_sent,
        }

    def get_duration(self) -> float:
        """Get alert duration in seconds"""
        end_time = self.resolved_at or self.updated_at
        return (end_time - self.created_at).total_seconds()


class AlertSystem:
    """
    Comprehensive alert management system with escalation and remediation
    """

    def __init__(self):
        self.rules = {}  # rule_name -> AlertRule
        self.active_alerts = {}  # alert_id -> Alert
        self.alert_history = []  # List of resolved alerts
        self.max_history_size = 10000

        # Deduplication and cooldown tracking
        self.last_alert_times = {}  # (rule_name, key) -> timestamp
        self.alert_keys = {}  # alert_id -> deduplication_key

        # Escalation policies
        self.escalation_policies = {}

        # Notification channels
        self.notification_handlers = {
            AlertChannel.LOG: self._notify_log,
            AlertChannel.EMAIL: self._notify_email,
            AlertChannel.SLACK: self._notify_slack,
            AlertChannel.WEBHOOK: self._notify_webhook,
            AlertChannel.SMS: self._notify_sms,
            AlertChannel.DATABASE: self._notify_database,
        }

        # Register default alert rules
        self._register_default_rules()

        logger.info("🚨 Alert system initialized")

    def _register_default_rules(self):
        """Register default alert rules"""

        # System resource alerts
        self.add_rule(
            AlertRule(
                name="high_cpu_usage",
                description="High CPU usage detected",
                condition=lambda data: data.get("cpu_percent", 0) > 80,
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.LOG, AlertChannel.SLACK],
                cooldown_minutes=10,
            )
        )

        self.add_rule(
            AlertRule(
                name="critical_cpu_usage",
                description="Critical CPU usage detected",
                condition=lambda data: data.get("cpu_percent", 0) > 95,
                severity=AlertSeverity.CRITICAL,
                channels=[AlertChannel.LOG, AlertChannel.EMAIL, AlertChannel.SLACK],
                cooldown_minutes=5,
            )
        )

        # Memory alerts
        self.add_rule(
            AlertRule(
                name="high_memory_usage",
                description="High memory usage detected",
                condition=lambda data: data.get("memory_percent", 0) > 80,
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.LOG, AlertChannel.SLACK],
                cooldown_minutes=10,
            )
        )

        # Database alerts
        self.add_rule(
            AlertRule(
                name="database_connection_failure",
                description="Database connection failure",
                condition=lambda data: data.get("status") == "unhealthy" and data.get("component") == "database",
                severity=AlertSeverity.CRITICAL,
                channels=[AlertChannel.LOG, AlertChannel.EMAIL, AlertChannel.SLACK],
                cooldown_minutes=5,
            )
        )

        self.add_rule(
            AlertRule(
                name="slow_database_queries",
                description="High number of slow database queries",
                condition=lambda data: data.get("slow_queries", 0) > 10,
                severity=AlertSeverity.MEDIUM,
                channels=[AlertChannel.LOG],
                cooldown_minutes=15,
            )
        )

        # Agent system alerts
        self.add_rule(
            AlertRule(
                name="agent_unavailability",
                description="Agent system availability below threshold",
                condition=lambda data: data.get("availability_rate", 1.0) < 0.8,
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.LOG, AlertChannel.SLACK],
                cooldown_minutes=10,
            )
        )

        # Security alerts
        self.add_rule(
            AlertRule(
                name="failed_authentication_spike",
                description="Spike in failed authentication attempts",
                condition=lambda data: data.get("failed_attempts_per_minute", 0) > 10,
                severity=AlertSeverity.HIGH,
                channels=[AlertChannel.LOG, AlertChannel.EMAIL],
                cooldown_minutes=5,
            )
        )

    def add_rule(self, rule: AlertRule):
        """Add an alert rule"""
        self.rules[rule.name] = rule
        logger.info("✅ Alert rule added: %s", rule.name)

    def remove_rule(self, rule_name: str) -> bool:
        """Remove an alert rule"""
        if rule_name in self.rules:
            del self.rules[rule_name]

            # Clean up active alerts for this rule
            alerts_to_remove = [
                alert_id for alert_id, alert in self.active_alerts.items() if alert.rule_name == rule_name
            ]
            for alert_id in alerts_to_remove:
                del self.active_alerts[alert_id]

            logger.info("❌ Alert rule removed: %s", rule_name)
            return True
        return False

    async def evaluate_condition(self, rule_name: str, data: dict[str, Any], key: str | None = None) -> Alert | None:
        """
        Evaluate an alert condition

        Parameters:
            rule_name: Name of the rule to evaluate
            data: Data to evaluate against the rule condition
            key: Optional deduplication key

        Returns:
            Alert instance if condition met and not on cooldown, None otherwise
        """
        rule = self.rules.get(rule_name)
        if not rule or not rule.enabled:
            return None

        try:
            if not rule.condition(data):
                return None

            # Check cooldown
            cooldown_key = (rule_name, key) if key else (rule_name, None)
            last_alert_time = self.last_alert_times.get(cooldown_key)

            if last_alert_time:
                cooldown_end = last_alert_time + timedelta(minutes=rule.cooldown_minutes)
                if datetime.now(UTC) < cooldown_end:
                    return None  # Still in cooldown

            # Create alert
            alert = Alert(
                rule_name=rule_name,
                title=f"{rule.severity.value.upper()}: {rule.description}",
                message=self._generate_alert_message(rule, data),
                severity=rule.severity,
                source=data.get("source", "system"),
                component=data.get("component"),
                metrics=data,
                tags=rule.tags,
            )

            # Store deduplication info
            if key:
                self.alert_keys[alert.id] = key

            # Update last alert time
            self.last_alert_times[cooldown_key] = alert.created_at

            return alert

        except Exception as e:
            logger.error("Failed to evaluate alert condition for rule %s: %s", rule_name, e)
            return None

    async def trigger_alert(self, alert: Alert):
        """Trigger an alert and send notifications"""
        try:
            self.active_alerts[alert.id] = alert

            # Send notifications
            await self._send_notifications(alert)
            await self._publish_alert_event(alert)

            logger.warning("🚨 Alert triggered: %s (ID: %s)", alert.title, alert.id)

        except Exception as e:
            logger.error("Failed to trigger alert %s: %s", alert.id, e)

    async def acknowledge_alert(self, alert_id: str, user_id: str | None = None):
        """Acknowledge an alert"""
        alert = self.active_alerts.get(alert_id)
        if alert:
            alert.acknowledge(user_id)
            await self._publish_alert_event(alert)
            logger.info("✅ Alert acknowledged: %s", alert_id)

    async def resolve_alert(self, alert_id: str, user_id: str | None = None):
        """Resolve an alert"""
        alert = self.active_alerts.get(alert_id)
        if alert:
            alert.resolve(user_id)

            # Move to history
            self.alert_history.append(alert)
            del self.active_alerts[alert_id]

            # Keep history size manageable
            if len(self.alert_history) > self.max_history_size:
                self.alert_history = self.alert_history[-self.max_history_size :]

            await self._publish_alert_event(alert)
            logger.info("✅ Alert resolved: %s", alert_id)

    def suppress_alert(self, alert_id: str, duration_minutes: int):
        """Suppress an alert for specified duration"""
        alert = self.active_alerts.get(alert_id)
        if alert:
            suppress_until = datetime.now(UTC) + timedelta(minutes=duration_minutes)
            alert.suppress(suppress_until)
            logger.info("🔇 Alert suppressed: %s until %s", alert_id, suppress_until)

    def _generate_alert_message(self, rule: AlertRule, data: dict[str, Any]) -> str:
        """Generate detailed alert message"""
        message = rule.description

        # Add relevant metrics
        metrics_info = []
        if "cpu_percent" in data:
            metrics_info.append(".1f")
        if "memory_percent" in data:
            metrics_info.append(".1f")
        if "slow_queries" in data:
            metrics_info.append(f"{data['slow_queries']} slow queries")
        if "availability_rate" in data:
            metrics_info.append(".1%")

        if metrics_info:
            message += f" (Current: {', '.join(metrics_info)})"

        return message

    async def _send_notifications(self, alert: Alert):
        """Send alert notifications via configured channels"""
        rule = self.rules.get(alert.rule_name)
        if not rule:
            return

        for channel in rule.channels:
            try:
                handler = self.notification_handlers.get(channel)
                if handler:
                    await handler(alert)
                    alert.notifications_sent.append(
                        {
                            "channel": channel.value,
                            "timestamp": datetime.now(UTC).isoformat(),
                        }
                    )
            except Exception as e:
                logger.error("Failed to send %s notification for alert %s: %s", channel.value, alert.id, e)

    async def _publish_alert_event(self, alert: Alert) -> None:
        """Publish alert state changes to the shared event bus."""
        try:
            from apps.backend.services.event_bus import event_bus

            await event_bus.publish(
                "system_alert",
                {
                    "alert_id": alert.id,
                    "rule_name": alert.rule_name,
                    "title": alert.title,
                    "message": alert.message,
                    "severity": alert.severity.value,
                    "status": alert.status.value,
                    "source": alert.source,
                    "component": alert.component,
                    "metrics": alert.metrics,
                    "tags": alert.tags,
                    "created_at": alert.created_at.isoformat(),
                    "updated_at": alert.updated_at.isoformat(),
                },
                source_service="alert_system",
            )
        except Exception as exc:
            logger.warning("Failed to publish alert event for %s: %s", alert.id, exc)

    async def _notify_log(self, alert: Alert):
        """Send alert to log"""
        log_level = {
            AlertSeverity.LOW: logging.INFO,
            AlertSeverity.MEDIUM: logging.WARNING,
            AlertSeverity.HIGH: logging.ERROR,
            AlertSeverity.CRITICAL: logging.CRITICAL,
        }.get(alert.severity, logging.WARNING)

        logger.log(
            log_level,
            f"ALERT {alert.severity.value.upper()}: {alert.title} - {alert.message}",
        )

    async def _notify_email(self, alert: Alert):
        """Send alert via email service when available."""
        try:
            from apps.backend.services.email_service import email_service

            await email_service.send_email(
                to_email=os.environ.get("ALERT_EMAIL", "admin@helix.local"),
                subject="[Helix Alert] {}: {}".format(alert.severity.value.upper(), alert.title),
                body=alert.message,
            )
            logger.info("📧 Email alert sent: %s", alert.title)
        except ImportError:
            logger.warning("📧 Email service unavailable — alert logged only: %s", alert.title)
        except Exception as exc:
            logger.error("📧 Email alert failed: %s — %s", alert.title, exc)

    async def _notify_slack(self, alert: Alert):
        """Send alert via Slack webhook when SLACK_WEBHOOK_URL is set."""
        import os

        webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
        if not webhook_url:
            logger.debug("💬 Slack webhook not configured — alert logged: %s", alert.title)
            return
        try:
            import httpx

            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    webhook_url,
                    json={
                        "text": "[{}] {}\n{}".format(alert.severity.value.upper(), alert.title, alert.message),
                    },
                )
            logger.info("💬 Slack alert sent: %s", alert.title)
        except Exception as exc:
            logger.error("💬 Slack alert failed: %s — %s", alert.title, exc)

    async def _notify_webhook(self, alert: Alert):
        """Send alert to a generic webhook when ALERT_WEBHOOK_URL is set."""
        import os

        webhook_url = os.environ.get("ALERT_WEBHOOK_URL")
        if not webhook_url:
            logger.debug("🔗 Webhook not configured — alert logged: %s", alert.title)
            return
        try:
            import httpx

            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    webhook_url,
                    json={
                        "severity": alert.severity.value,
                        "title": alert.title,
                        "message": alert.message,
                        "timestamp": (alert.timestamp.isoformat() if hasattr(alert, "timestamp") else None),
                    },
                )
            logger.info("🔗 Webhook alert sent: %s", alert.title)
        except Exception as exc:
            logger.error("🔗 Webhook alert failed: %s — %s", alert.title, exc)

    async def _notify_sms(self, alert: Alert):
        """SMS alert — requires external service integration. Logs as structured warning."""
        logger.warning(
            "📱 SMS alert (delivery not configured): severity=%s title=%s message=%s",
            alert.severity.value,
            alert.title,
            alert.message,
        )

    async def _notify_database(self, alert: Alert):
        """Store alert in database via Database helper."""
        try:
            from apps.backend.core.database import Database

            await Database.execute(
                """INSERT INTO alerts (severity, title, message, created_at)
                   VALUES ($1, $2, $3, NOW())""",
                alert.severity.value,
                alert.title,
                alert.message,
            )
            logger.info("💾 Alert persisted to database: %s", alert.title)
        except ImportError:
            logger.debug("💾 Database module unavailable — alert logged: %s", alert.title)
        except Exception as exc:
            logger.warning("💾 Database alert storage failed: %s — %s", alert.title, exc)

    async def check_auto_resolve(self):
        """Check and auto-resolve alerts based on rules"""
        for alert in list(self.active_alerts.values()):
            rule = self.rules.get(alert.rule_name)
            if rule and rule.auto_resolve:
                try:
                    # This is a simplified version - in practice would need current metrics
                    should_resolve = not rule.condition(alert.metrics)

                    if should_resolve:
                        await self.resolve_alert(alert.id, "auto_resolve")
                        logger.info("🔄 Auto-resolved alert: %s", alert.id)

                except Exception as e:
                    logger.error("Auto-resolve check failed for alert %s: %s", alert.id, e)

    def get_active_alerts(
        self,
        severity_filter: AlertSeverity | None = None,
        component_filter: str | None = None,
    ) -> list[Alert]:
        """Get active alerts with optional filters"""
        alerts = list(self.active_alerts.values())

        if severity_filter:
            alerts = [a for a in alerts if a.severity == severity_filter]

        if component_filter:
            alerts = [a for a in alerts if a.component == component_filter]

        return sorted(alerts, key=lambda a: a.created_at, reverse=True)

    def get_alert_history(self, hours: int = 24, severity_filter: AlertSeverity | None = None) -> list[Alert]:
        """Get alert history with optional filters"""
        cutoff_time = datetime.now(UTC) - timedelta(hours=hours)

        alerts = [alert for alert in self.alert_history if alert.created_at >= cutoff_time]

        if severity_filter:
            alerts = [a for a in alerts if a.severity == severity_filter]

        return sorted(alerts, key=lambda a: a.created_at, reverse=True)

    def get_alert_stats(self) -> dict[str, Any]:
        """Get alert system statistics"""
        active_alerts = list(self.active_alerts.values())
        resolved_alerts = self.alert_history

        # Calculate statistics
        severity_counts = defaultdict(int)
        for alert in active_alerts + resolved_alerts:
            severity_counts[alert.severity.value] += 1

        status_counts = defaultdict(int)
        for alert in active_alerts:
            status_counts[alert.status.value] += 1

        # Average resolution time
        resolved_with_times = [a for a in resolved_alerts if a.resolved_at]
        avg_resolution_time = 0
        if resolved_with_times:
            total_time = sum(a.get_duration() for a in resolved_with_times)
            avg_resolution_time = total_time / len(resolved_with_times)

        return {
            "active_alerts": len(active_alerts),
            "total_alerts": len(active_alerts) + len(resolved_alerts),
            "severity_breakdown": dict(severity_counts),
            "status_breakdown": dict(status_counts),
            "avg_resolution_time_seconds": avg_resolution_time,
            "rules_enabled": len([r for r in self.rules.values() if r.enabled]),
            "rules_total": len(self.rules),
        }

    def export_alerts(self, format: str = "json") -> str:
        """Export alerts data"""
        all_alerts = list(self.active_alerts.values()) + self.alert_history

        if format == "json":
            return json.dumps([alert.to_dict() for alert in all_alerts], indent=2)
        elif format == "csv":
            # Simple CSV export
            lines = ["id,rule_name,title,severity,status,created_at"]
            for alert in all_alerts:
                lines.append(
                    ",".join(
                        [
                            alert.id,
                            alert.rule_name,
                            alert.title.replace(",", ";"),
                            alert.severity.value,
                            alert.status.value,
                            alert.created_at.isoformat(),
                        ]
                    )
                )
            return "\n".join(lines)

        return ""


# Global alert system instance
alert_system = AlertSystem()


def get_alert_system() -> AlertSystem:
    """Get the global alert system instance"""
    return alert_system


# Convenience functions
async def trigger_alert(rule_name: str, data: dict[str, Any], key: str | None = None):
    """Trigger an alert for a rule"""
    alert = await alert_system.evaluate_condition(rule_name, data, key)
    if alert:
        await alert_system.trigger_alert(alert)
        return alert
    return None


def get_alert_severity_counts() -> dict[str, int]:
    """Get counts of alerts by severity"""
    stats = alert_system.get_alert_stats()
    return stats.get("severity_breakdown", {})
