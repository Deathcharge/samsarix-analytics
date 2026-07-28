"""Deterministic threshold alerts over a :mod:`helix_analytics` metric registry."""

from __future__ import annotations

import logging
import math
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from threading import RLock
from types import MappingProxyType
from uuid import uuid4

from .metrics import MetricError, MetricRegistry, MetricSample

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Severity selected by the rule author."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """Lifecycle state of an alert."""

    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class Comparison(str, Enum):
    """Supported numeric threshold comparisons."""

    GT = ">"
    GE = ">="
    LT = "<"
    LE = "<="
    EQ = "=="

    def matches(self, value: float, threshold: float) -> bool:
        if self is Comparison.GT:
            return value > threshold
        if self is Comparison.GE:
            return value >= threshold
        if self is Comparison.LT:
            return value < threshold
        if self is Comparison.LE:
            return value <= threshold
        return value == threshold


@dataclass(frozen=True)
class AlertRule:
    """A threshold rule evaluated independently for each matching metric series."""

    name: str
    metric: str
    operator: Comparison
    threshold: float
    severity: AlertSeverity = AlertSeverity.WARNING
    aggregation: str = "value"
    labels: Mapping[str, str] = field(default_factory=dict)
    cooldown_seconds: float = 300
    auto_resolve: bool = True

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("alert rule name cannot be empty")
        if not self.metric.strip():
            raise ValueError("alert rule metric cannot be empty")
        if not isinstance(self.operator, Comparison):
            raise ValueError("operator must be a Comparison")
        if not isinstance(self.severity, AlertSeverity):
            raise ValueError("severity must be an AlertSeverity")
        if not isinstance(self.threshold, (int, float)) or isinstance(self.threshold, bool):
            raise ValueError("alert threshold must be a finite number")
        if not math.isfinite(float(self.threshold)):
            raise ValueError("alert threshold must be a finite number")
        if self.cooldown_seconds < 0 or not math.isfinite(self.cooldown_seconds):
            raise ValueError("cooldown_seconds must be a finite non-negative number")
        if not self.aggregation:
            raise ValueError("aggregation cannot be empty")
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "metric", self.metric.strip())
        object.__setattr__(self, "threshold", float(self.threshold))
        object.__setattr__(self, "labels", MappingProxyType(dict(self.labels)))

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "metric": self.metric,
            "operator": self.operator.value,
            "threshold": self.threshold,
            "severity": self.severity.value,
            "aggregation": self.aggregation,
            "labels": dict(self.labels),
            "cooldown_seconds": self.cooldown_seconds,
            "auto_resolve": self.auto_resolve,
        }


@dataclass
class Alert:
    """One independently triggered rule/series instance."""

    id: str
    rule_name: str
    metric: str
    labels: dict[str, str]
    aggregation: str
    operator: Comparison
    threshold: float
    current_value: float
    severity: AlertSeverity
    status: AlertStatus
    triggered_at: datetime
    last_observed_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "rule_name": self.rule_name,
            "metric": self.metric,
            "labels": dict(self.labels),
            "aggregation": self.aggregation,
            "operator": self.operator.value,
            "threshold": self.threshold,
            "current_value": self.current_value,
            "severity": self.severity.value,
            "status": self.status.value,
            "triggered_at": self.triggered_at.isoformat(),
            "last_observed_at": self.last_observed_at.isoformat(),
            "acknowledged_at": (self.acknowledged_at.isoformat() if self.acknowledged_at else None),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


@dataclass(frozen=True)
class EvaluationResult:
    """Events and rule errors produced by one evaluation pass."""

    triggered: tuple[Alert, ...] = ()
    resolved: tuple[Alert, ...] = ()
    errors: Mapping[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "triggered": [alert.to_dict() for alert in self.triggered],
            "resolved": [alert.to_dict() for alert in self.resolved],
            "errors": dict(self.errors),
        }


AlertHandler = Callable[[Alert], None]
_AlertKey = tuple[str, tuple[tuple[str, str], ...]]


class AlertManager:
    """Evaluates threshold rules with deduplication, cooldown, and bounded history."""

    def __init__(
        self,
        *,
        max_history: int = 1000,
        max_rules: int = 100,
        max_handlers: int = 20,
    ) -> None:
        if max_history < 1:
            raise ValueError("max_history must be at least 1")
        if max_rules < 1:
            raise ValueError("max_rules must be at least 1")
        if max_handlers < 1:
            raise ValueError("max_handlers must be at least 1")
        self.max_history = max_history
        self.max_rules = max_rules
        self.max_handlers = max_handlers
        self._rules: dict[str, AlertRule] = {}
        self._active: dict[_AlertKey, Alert] = {}
        self._history: deque[Alert] = deque(maxlen=max_history)
        self._last_triggered: dict[_AlertKey, datetime] = {}
        self._handlers: list[AlertHandler] = []
        self._lock = RLock()

    def add_rule(self, rule: AlertRule, *, replace: bool = False) -> None:
        with self._lock:
            if rule.name in self._rules and not replace:
                raise ValueError(f"alert rule {rule.name!r} is already registered")
            if rule.name not in self._rules and len(self._rules) >= self.max_rules:
                raise ValueError(f"alert manager reached its {self.max_rules}-rule limit")
            if rule.name in self._rules:
                self._discard_rule_state(rule.name)
            self._rules[rule.name] = rule

    def remove_rule(self, name: str) -> bool:
        with self._lock:
            removed = self._rules.pop(name, None) is not None
            if removed:
                self._discard_rule_state(name)
            return removed

    def _discard_rule_state(self, name: str) -> None:
        for key in tuple(self._active):
            if key[0] == name:
                del self._active[key]
        for key in tuple(self._last_triggered):
            if key[0] == name:
                del self._last_triggered[key]

    def add_handler(self, handler: AlertHandler) -> None:
        with self._lock:
            if len(self._handlers) >= self.max_handlers:
                raise ValueError(f"alert manager reached its {self.max_handlers}-handler limit")
            self._handlers.append(handler)

    @staticmethod
    def _matches_labels(sample: MetricSample, rule: AlertRule) -> bool:
        return all(sample.labels.get(name) == value for name, value in rule.labels.items())

    @staticmethod
    def _key(rule: AlertRule, sample: MetricSample) -> _AlertKey:
        return (rule.name, tuple(sorted(sample.labels.items())))

    @staticmethod
    def _validate_now(now: datetime | None) -> datetime:
        value = now or datetime.now(timezone.utc)
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evaluation time must be timezone-aware")
        return value

    def evaluate(
        self, registry: MetricRegistry, *, now: datetime | None = None
    ) -> EvaluationResult:
        evaluated_at = self._validate_now(now)
        with self._lock:
            rules = tuple(self._rules.values())

        triggered: list[Alert] = []
        resolved: list[Alert] = []
        errors: dict[str, str] = {}

        for rule in rules:
            try:
                samples = registry.query(rule.metric, rule.aggregation)
            except MetricError as exc:
                errors[rule.name] = str(exc)
                continue

            for sample in samples:
                if not self._matches_labels(sample, rule):
                    continue
                key = self._key(rule, sample)
                is_triggered = rule.operator.matches(sample.value, rule.threshold)
                with self._lock:
                    active = self._active.get(key)
                    if is_triggered:
                        if active is not None:
                            active.current_value = sample.value
                            active.last_observed_at = evaluated_at
                            continue

                        last_triggered = self._last_triggered.get(key)
                        if last_triggered is not None:
                            cooldown_end = last_triggered + timedelta(seconds=rule.cooldown_seconds)
                            if evaluated_at < cooldown_end:
                                continue

                        alert = Alert(
                            id=f"alert_{uuid4().hex}",
                            rule_name=rule.name,
                            metric=sample.metric,
                            labels=dict(sample.labels),
                            aggregation=sample.aggregation,
                            operator=rule.operator,
                            threshold=rule.threshold,
                            current_value=sample.value,
                            severity=rule.severity,
                            status=AlertStatus.ACTIVE,
                            triggered_at=evaluated_at,
                            last_observed_at=evaluated_at,
                        )
                        self._active[key] = alert
                        self._last_triggered[key] = evaluated_at
                        triggered.append(alert)
                    elif active is not None and rule.auto_resolve:
                        active.current_value = sample.value
                        active.last_observed_at = evaluated_at
                        active.status = AlertStatus.RESOLVED
                        active.resolved_at = evaluated_at
                        del self._active[key]
                        self._history.append(active)
                        resolved.append(active)

        self._notify((*triggered, *resolved))
        return EvaluationResult(tuple(triggered), tuple(resolved), MappingProxyType(errors))

    def _notify(self, alerts: tuple[Alert, ...]) -> None:
        with self._lock:
            handlers = tuple(self._handlers)
        for alert in alerts:
            for handler in handlers:
                try:
                    handler(alert)
                except Exception:
                    logger.exception("alert handler failed for %s", alert.id)

    def acknowledge(self, alert_id: str, *, now: datetime | None = None) -> bool:
        acknowledged_at = self._validate_now(now)
        with self._lock:
            for alert in self._active.values():
                if alert.id == alert_id:
                    alert.status = AlertStatus.ACKNOWLEDGED
                    alert.acknowledged_at = acknowledged_at
                    return True
        return False

    def resolve(self, alert_id: str, *, now: datetime | None = None) -> bool:
        resolved_at = self._validate_now(now)
        with self._lock:
            for key, alert in tuple(self._active.items()):
                if alert.id == alert_id:
                    alert.status = AlertStatus.RESOLVED
                    alert.resolved_at = resolved_at
                    alert.last_observed_at = resolved_at
                    del self._active[key]
                    self._history.append(alert)
                    return True
        return False

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            rules = [rule.to_dict() for rule in self._rules.values()]
            active = [alert.to_dict() for alert in self._active.values()]
            history = [alert.to_dict() for alert in self._history]
        return {
            "rules": rules,
            "active": active,
            "history": history,
            "limits": {
                "max_history": self.max_history,
                "max_rules": self.max_rules,
                "max_handlers": self.max_handlers,
            },
        }
