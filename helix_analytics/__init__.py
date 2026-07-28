"""Bounded in-process metrics and threshold alerting for Python applications."""

from .monitoring import (
    Alert,
    AlertManager,
    AlertRule,
    AlertSeverity,
    AlertStatus,
    CardinalityLimitError,
    Comparison,
    Counter,
    EvaluationResult,
    Gauge,
    Histogram,
    MetricError,
    MetricRegistry,
    MetricSample,
    track_duration,
)

__version__ = "0.2.0"

__all__ = [
    "Alert",
    "AlertManager",
    "AlertRule",
    "AlertSeverity",
    "AlertStatus",
    "CardinalityLimitError",
    "Comparison",
    "Counter",
    "EvaluationResult",
    "Gauge",
    "Histogram",
    "MetricError",
    "MetricRegistry",
    "MetricSample",
    "__version__",
    "track_duration",
]
