"""
👁️ Helix Collective v21.0 - Enhanced Observability System
backend/observability/enhanced_observability.py

Advanced observability features for self-managing platform:
- Real-time coordination health monitoring
- Predictive performance analytics
- Automated anomaly correlation
- Self-healing orchestration
- Intelligent alerting with context

Author: Helix Collective
Version: 21.0.0
"""

import asyncio
import logging
import statistics
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# DATA STRUCTURES
# ============================================================================


class HealthStatus(Enum):
    """System health status levels"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class AlertPriority(Enum):
    """Alert priority levels"""

    P1 = "P1"  # Critical - Immediate action required
    P2 = "P2"  # High - Action required within 1 hour
    P3 = "P3"  # Medium - Action required within 24 hours
    P4 = "P4"  # Low - Informational


@dataclass
class SystemHealthSnapshot:
    """Snapshot of system health at a point in time"""

    timestamp: datetime
    overall_status: HealthStatus
    coordination_score: float
    agent_health: dict[str, HealthStatus]
    workflow_health: dict[str, float]
    resource_utilization: dict[str, float]
    active_anomalies: int
    recent_insights: int
    auto_healing_attempts: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "overall_status": self.overall_status.value,
            "coordination_score": round(self.coordination_score, 3),
            "agent_health": {k: v.value for k, v in self.agent_health.items()},
            "workflow_health": self.workflow_health,
            "resource_utilization": self.resource_utilization,
            "active_anomalies": self.active_anomalies,
            "recent_insights": self.recent_insights,
            "auto_healing_attempts": self.auto_healing_attempts,
        }


@dataclass
class ObservabilityAlert:
    """Intelligent alert with context and recommendations"""

    timestamp: datetime
    alert_id: str
    priority: AlertPriority
    title: str
    description: str
    affected_components: list[str]
    root_cause_analysis: str
    recommended_actions: list[str]
    correlation_id: str | None = None
    auto_resolved: bool = False
    resolution_time: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "alert_id": self.alert_id,
            "priority": self.priority.value,
            "title": self.title,
            "description": self.description,
            "affected_components": self.affected_components,
            "root_cause_analysis": self.root_cause_analysis,
            "recommended_actions": self.recommended_actions,
            "correlation_id": self.correlation_id,
            "auto_resolved": self.auto_resolved,
            "resolution_time": self.resolution_time.isoformat() if self.resolution_time else None,
        }


@dataclass
class PerformancePrediction:
    """Predictive performance analytics"""

    metric_name: str
    current_value: float
    predicted_value_1h: float
    predicted_value_24h: float
    confidence: float
    trend: str  # "improving", "declining", "stable"
    recommendation: str
    threshold_breach_time: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "metric_name": self.metric_name,
            "current_value": round(self.current_value, 3),
            "predicted_value_1h": round(self.predicted_value_1h, 3),
            "predicted_value_24h": round(self.predicted_value_24h, 3),
            "confidence": round(self.confidence, 3),
            "trend": self.trend,
            "threshold_breach_time": self.threshold_breach_time.isoformat() if self.threshold_breach_time else None,
            "recommendation": self.recommendation,
        }


# ============================================================================
# ENHANCED OBSERVABILITY SYSTEM
# ============================================================================


class EnhancedObservabilitySystem:
    """
    Advanced observability system for self-managing platform.

    Provides:
    - Real-time health monitoring with intelligent status aggregation
    - Predictive performance analytics using trend analysis
    - Automated anomaly correlation and root cause analysis
    - Self-healing orchestration with feedback loops
    - Intelligent alerting with context and recommendations
    """

    def __init__(
        self,
        coordination_intelligence: Any = None,
        ucf_calculator: Any = None,
    ):
        """
        Initialize the enhanced observability system.

        Args:
            coordination_intelligence: Coordination Intelligence Integration instance
            ucf_calculator: UCF Calculator instance
        """
        self.coordination_intelligence = coordination_intelligence
        self.ucf_calculator = ucf_calculator

        # Health tracking
        self._health_history: deque[SystemHealthSnapshot] = deque(maxlen=100)
        self._current_health: SystemHealthSnapshot | None = None

        # Alert management
        self._active_alerts: dict[str, ObservabilityAlert] = {}
        self._alert_history: deque[ObservabilityAlert] = deque(maxlen=500)
        self._alert_correlation_map: dict[str, list[str]] = {}

        # Performance predictions
        self._metric_history: dict[str, deque[float]] = {
            "harmony": deque(maxlen=100),
            "friction": deque(maxlen=100),
            "throughput": deque(maxlen=100),
            "focus": deque(maxlen=100),
            "resilience": deque(maxlen=100),
        }

        # Self-healing tracking
        self._healing_attempts: deque[dict[str, Any]] = deque(maxlen=100)
        self._healing_success_rate: float = 0.0

        # Background monitoring
        self._monitoring_task: asyncio.Task | None = None
        self._monitoring_interval = 30  # seconds

        logger.info("👁️ Enhanced Observability System initialized")

    # ========================================================================
    # HEALTH MONITORING
    # ========================================================================

    async def collect_health_snapshot(self) -> SystemHealthSnapshot:
        """
        Collect comprehensive system health snapshot.

        Returns:
            SystemHealthSnapshot with current health status
        """
        timestamp = datetime.now(UTC)

        # Get coordination metrics
        coordination_score = 0.0
        if self.ucf_calculator:
            try:
                metrics = self.ucf_calculator.get_state()
                harmony = metrics.get("harmony", 0)
                friction = metrics.get("friction", 0)
                throughput = metrics.get("throughput", 0)

                # Calculate composite coordination score
                coordination_score = (harmony * 0.4) + ((1 - friction) * 0.3) + (throughput * 0.3)

                # Update metric history
                for metric_name, value in metrics.items():
                    if metric_name in self._metric_history:
                        self._metric_history[metric_name].append(value)

            except Exception as e:
                logger.error("Failed to get coordination metrics: %s", e)

        # Determine overall health status
        overall_status = self._calculate_overall_status(coordination_score)

        # Get agent health (placeholder - would integrate with agent system)
        agent_health = self._get_agent_health()

        # Get workflow health (placeholder - would integrate with workflow system)
        workflow_health = self._get_workflow_health()

        # Get resource utilization (placeholder - would integrate with system metrics)
        resource_utilization = self._get_resource_utilization()

        # Count active anomalies
        active_anomalies = len(self._active_alerts)

        # Count recent insights
        recent_insights = 0
        if self.coordination_intelligence:
            try:
                insights = self.coordination_intelligence.get_real_time_insights()
                recent_insights = len(insights)
            except Exception as e:
                logger.debug("Real-time insights unavailable: %s", e)

        # Count auto-healing attempts
        auto_healing_attempts = len(
            [
                a
                for a in self._healing_attempts
                if (timestamp - datetime.fromisoformat(a["timestamp"])).total_seconds() < 3600
            ]
        )

        snapshot = SystemHealthSnapshot(
            timestamp=timestamp,
            overall_status=overall_status,
            coordination_score=coordination_score,
            agent_health=agent_health,
            workflow_health=workflow_health,
            resource_utilization=resource_utilization,
            active_anomalies=active_anomalies,
            recent_insights=recent_insights,
            auto_healing_attempts=auto_healing_attempts,
        )

        self._health_history.append(snapshot)
        self._current_health = snapshot

        return snapshot

    def _calculate_overall_status(self, coordination_score: float) -> HealthStatus:
        """Calculate overall system health status"""
        if coordination_score >= 0.8:
            return HealthStatus.HEALTHY
        elif coordination_score >= 0.6:
            return HealthStatus.DEGRADED
        elif coordination_score >= 0.4:
            return HealthStatus.WARNING
        elif coordination_score > 0:
            return HealthStatus.CRITICAL
        else:
            return HealthStatus.UNKNOWN

    def _get_agent_health(self) -> dict[str, HealthStatus]:
        """Get health status of all agents"""
        # Placeholder - would integrate with agent system
        return {
            "Kael": HealthStatus.HEALTHY,
            "Lumina": HealthStatus.HEALTHY,
            "Vega": HealthStatus.HEALTHY,
        }

    def _get_workflow_health(self) -> dict[str, float]:
        """Get health metrics of workflows"""
        # Placeholder - would integrate with workflow system
        return {
            "success_rate": 0.95,
            "avg_execution_time": 2.5,
            "active_workflows": 12,
        }

    def _get_resource_utilization(self) -> dict[str, float]:
        """Get system resource utilization"""
        # Placeholder - would integrate with system metrics
        return {
            "cpu_percent": 45.0,
            "memory_percent": 62.0,
            "disk_percent": 38.0,
        }

    # ========================================================================
    # PREDICTIVE ANALYTICS
    # ========================================================================

    def generate_performance_predictions(self) -> list[PerformancePrediction]:
        """
        Generate predictive performance analytics for key metrics.

        Returns:
            List of performance predictions with trends and recommendations
        """
        predictions = []

        for metric_name, history in self._metric_history.items():
            if len(history) < 10:
                continue

            values = list(history)
            current_value = values[-1]

            # Calculate trend using linear regression
            trend_slope = self._calculate_trend_slope(values)

            # Predict future values
            predicted_1h = current_value + (trend_slope * 2)  # Assuming 30s intervals, 2 = 1 hour
            predicted_24h = current_value + (trend_slope * 48)  # 48 = 24 hours

            # Clamp predictions to valid range
            predicted_1h = max(0.0, min(1.0, predicted_1h))
            predicted_24h = max(0.0, min(1.0, predicted_24h))

            # Determine trend direction
            if trend_slope > 0.01:
                trend = "improving"
            elif trend_slope < -0.01:
                trend = "declining"
            else:
                trend = "stable"

            # Calculate confidence based on data consistency
            volatility = statistics.stdev(values) if len(values) > 1 else 0
            confidence = max(0.5, 1.0 - volatility)

            # Check for threshold breach prediction
            threshold_breach_time = None
            if metric_name == "friction" and trend_slope > 0:
                # Predict when friction might exceed 0.7
                if predicted_24h > 0.7:
                    hours_to_breach = (0.7 - current_value) / (trend_slope * 2) if trend_slope > 0 else None
                    if hours_to_breach and hours_to_breach > 0:
                        threshold_breach_time = datetime.now(UTC) + timedelta(hours=hours_to_breach)

            elif metric_name == "harmony" and trend_slope < 0 and predicted_24h < 0.5:
                # Predict when harmony might drop below 0.5
                hours_to_breach = (current_value - 0.5) / (-trend_slope * 2) if trend_slope < 0 else None
                if hours_to_breach and hours_to_breach > 0:
                    threshold_breach_time = datetime.now(UTC) + timedelta(hours=hours_to_breach)

            # Generate recommendation
            recommendation = self._generate_prediction_recommendation(
                metric_name, trend, predicted_24h, threshold_breach_time
            )

            prediction = PerformancePrediction(
                metric_name=metric_name,
                current_value=current_value,
                predicted_value_1h=predicted_1h,
                predicted_value_24h=predicted_24h,
                confidence=confidence,
                trend=trend,
                threshold_breach_time=threshold_breach_time,
                recommendation=recommendation,
            )

            predictions.append(prediction)

        return predictions

    def _calculate_trend_slope(self, values: list[float]) -> float:
        """Calculate trend slope using linear regression"""
        if len(values) < 2:
            return 0.0

        # Simple linear regression
        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n

        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0.0

        return numerator / denominator

    def _generate_prediction_recommendation(
        self,
        metric_name: str,
        trend: str,
        predicted_24h: float,
        threshold_breach_time: datetime | None,
    ) -> str:
        """Generate recommendation based on prediction"""
        if threshold_breach_time:
            hours_until_breach = (threshold_breach_time - datetime.now(UTC)).total_seconds() / 3600
            if hours_until_breach < 6:
                return f"URGENT: {metric_name} predicted to breach threshold within {hours_until_breach:.1f} hours"
            else:
                return f"WARNING: {metric_name} trending toward threshold breach in {hours_until_breach:.1f} hours"

        if trend == "declining" and metric_name in ["harmony", "throughput"]:
            return f"Monitor {metric_name} closely - declining trend detected"
        elif trend == "improving" and metric_name == "friction":
            return f"Positive trend - {metric_name} is improving"
        elif trend == "stable":
            return f"{metric_name} is stable - continue monitoring"
        else:
            return f"{metric_name} trend: {trend}"

    # ========================================================================
    # INTELLIGENT ALERTING
    # ========================================================================

    async def create_intelligent_alert(
        self,
        title: str,
        description: str,
        priority: AlertPriority,
        affected_components: list[str],
        root_cause: str = "",
        recommendations: list[str] | None = None,
    ) -> ObservabilityAlert:
        """
        Create an intelligent alert with context and recommendations.

        Args:
            title: Alert title
            description: Detailed description
            priority: Alert priority level
            affected_components: List of affected system components
            root_cause: Root cause analysis
            recommendations: Recommended actions

        Returns:
            Created ObservabilityAlert
        """
        import uuid

        alert_id = f"alert-{uuid.uuid4().hex[:8]}"
        timestamp = datetime.now(UTC)

        # Attempt to correlate with existing alerts
        correlation_id = self._find_correlated_alert(affected_components)

        alert = ObservabilityAlert(
            timestamp=timestamp,
            alert_id=alert_id,
            priority=priority,
            title=title,
            description=description,
            affected_components=affected_components,
            root_cause_analysis=root_cause or "Under investigation",
            recommended_actions=recommendations or ["Investigate and resolve"],
            correlation_id=correlation_id,
        )

        self._active_alerts[alert_id] = alert
        self._alert_history.append(alert)

        # Update correlation map
        if correlation_id:
            if correlation_id not in self._alert_correlation_map:
                self._alert_correlation_map[correlation_id] = []
            self._alert_correlation_map[correlation_id].append(alert_id)

        logger.warning(
            "🚨 Alert created: %s (priority: %s, components: %s)",
            title,
            priority.value,
            ", ".join(affected_components),
        )

        return alert

    def _find_correlated_alert(self, affected_components: list[str]) -> str | None:
        """Find correlated alert based on affected components"""
        for alert_id, alert in self._active_alerts.items():
            if (
                any(comp in alert.affected_components for comp in affected_components)
                and (datetime.now(UTC) - alert.timestamp).total_seconds() < 3600
            ):
                return alert.correlation_id or alert_id
        return None

    async def resolve_alert(self, alert_id: str, resolution_notes: str = "") -> bool:
        """
        Resolve an active alert.

        Args:
            alert_id: ID of alert to resolve
            resolution_notes: Notes about resolution

        Returns:
            True if alert was resolved, False if not found
        """
        if alert_id not in self._active_alerts:
            return False

        alert = self._active_alerts[alert_id]
        alert.auto_resolved = True
        alert.resolution_time = datetime.now(UTC)

        # Move to history
        del self._active_alerts[alert_id]

        logger.info("✅ Alert resolved: %s (%s)", alert.title, resolution_notes or "manual")

        return True

    # ========================================================================
    # SELF-HEALING ORCHESTRATION
    # ========================================================================

    async def orchestrate_self_healing(self) -> dict[str, Any]:
        """
        Orchestrate self-healing actions based on current health state.

        Returns:
            Summary of healing actions taken
        """
        if not self._current_health:
            await self.collect_health_snapshot()

        healing_actions = []

        # Check coordination intelligence for anomalies
        if self.coordination_intelligence:
            try:
                anomalies = self.coordination_intelligence.get_anomaly_history(limit=5)
                for anomaly in anomalies:
                    if not anomaly.get("auto_resolved"):
                        # Attempt auto-healing
                        healing_result = await self._attempt_healing(anomaly)
                        healing_actions.append(healing_result)
            except Exception as e:
                logger.error("Failed to orchestrate healing from coordination intelligence: %s", e)

        # Check health status for issues
        if self._current_health and self._current_health.overall_status in [
            HealthStatus.WARNING,
            HealthStatus.CRITICAL,
        ]:
            healing_actions.append(
                {
                    "action": "health_alert",
                    "status": self._current_health.overall_status.value,
                    "coordination_score": self._current_health.coordination_score,
                }
            )

        # Update healing success rate
        if healing_actions:
            success_count = sum(1 for a in healing_actions if a.get("success", False))
            self._healing_success_rate = success_count / len(healing_actions)

        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "healing_actions": healing_actions,
            "success_rate": self._healing_success_rate,
        }

    async def _attempt_healing(self, anomaly: dict[str, Any]) -> dict[str, Any]:
        """Attempt to heal a specific anomaly"""
        anomaly_type = anomaly.get("anomaly_type", "unknown")

        # Record healing attempt
        attempt = {
            "timestamp": datetime.now(UTC).isoformat(),
            "anomaly_type": anomaly_type,
            "action": f"auto_heal_{anomaly_type}",
            "success": True,  # Placeholder - would check actual result
        }

        self._healing_attempts.append(attempt)

        return attempt

    # ========================================================================
    # BACKGROUND MONITORING
    # ========================================================================

    async def start_monitoring(self) -> None:
        """Start continuous observability monitoring"""
        if self._monitoring_task and not self._monitoring_task.done():
            logger.warning("⚠️ Monitoring already running")
            return

        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("👁️ Started enhanced observability monitoring (interval: %ds)", self._monitoring_interval)

    async def stop_monitoring(self) -> None:
        """Stop continuous monitoring"""
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            import contextlib

            with contextlib.suppress(asyncio.CancelledError):
                await self._monitoring_task
            logger.info("👁️ Stopped enhanced observability monitoring")

    async def _monitoring_loop(self) -> None:
        """Continuous monitoring loop"""
        while True:
            try:
                # Collect health snapshot
                await self.collect_health_snapshot()

                # Generate predictions
                predictions = self.generate_performance_predictions()

                # Check for threshold breaches
                for prediction in predictions:
                    if prediction.threshold_breach_time:
                        hours_until = (prediction.threshold_breach_time - datetime.now(UTC)).total_seconds() / 3600
                        if hours_until < 6:
                            # Create predictive alert
                            await self.create_intelligent_alert(
                                title=f"Predictive Alert: {prediction.metric_name} Threshold Breach",
                                description=f"{prediction.metric_name} predicted to breach threshold in {hours_until:.1f} hours",
                                priority=AlertPriority.P2 if hours_until < 2 else AlertPriority.P3,
                                affected_components=["coordination", prediction.metric_name],
                                root_cause=f"Trend analysis shows {prediction.trend} pattern",
                                recommendations=[prediction.recommendation],
                            )

                # Orchestrate self-healing
                await self.orchestrate_self_healing()

                await asyncio.sleep(self._monitoring_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("❌ Error in observability monitoring loop: %s", e)
                await asyncio.sleep(self._monitoring_interval)

    # ========================================================================
    # PUBLIC API
    # ========================================================================

    def get_observability_dashboard(self) -> dict[str, Any]:
        """
        Get comprehensive observability dashboard data.

        Returns:
            Complete observability data including health, predictions, and alerts
        """
        return {
            "current_health": self._current_health.to_dict() if self._current_health else None,
            "health_history": [h.to_dict() for h in list(self._health_history)[-20:]],
            "active_alerts": [a.to_dict() for a in self._active_alerts.values()],
            "recent_alerts": [a.to_dict() for a in list(self._alert_history)[-20:]],
            "performance_predictions": [p.to_dict() for p in self.generate_performance_predictions()],
            "healing_stats": {
                "total_attempts": len(self._healing_attempts),
                "success_rate": self._healing_success_rate,
                "recent_attempts": list(self._healing_attempts)[-10:],
            },
        }

    def get_active_alerts(self) -> list[dict[str, Any]]:
        """Get all active alerts"""
        return [a.to_dict() for a in self._active_alerts.values()]

    def get_performance_predictions(self) -> list[dict[str, Any]]:
        """Get all performance predictions"""
        return [p.to_dict() for p in self.generate_performance_predictions()]


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_observability_system: EnhancedObservabilitySystem | None = None


def get_observability_system() -> EnhancedObservabilitySystem:
    """Get or create the observability system singleton"""
    global _observability_system
    if _observability_system is None:
        _observability_system = EnhancedObservabilitySystem()
    return _observability_system


def initialize_observability_system(
    coordination_intelligence: Any = None,
    ucf_calculator: Any = None,
) -> EnhancedObservabilitySystem:
    """
    Initialize the enhanced observability system.

    Args:
        coordination_intelligence: Coordination Intelligence Integration instance
        ucf_calculator: UCF Calculator instance

    Returns:
        Initialized observability system instance
    """
    global _observability_system
    _observability_system = EnhancedObservabilitySystem(
        coordination_intelligence=coordination_intelligence,
        ucf_calculator=ucf_calculator,
    )
    return _observability_system
