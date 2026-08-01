# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: MPL-2.0

"""Bounded in-process metrics and threshold alerting for Python applications."""

from .exposition import (
    PROMETHEUS_CONTENT_TYPE,
    ASGIApp,
    MetricsServer,
    WSGIApp,
    make_asgi_app,
    make_wsgi_app,
    start_metrics_server,
)
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
    "PROMETHEUS_CONTENT_TYPE",
    "ASGIApp",
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
    "MetricsServer",
    "WSGIApp",
    "__version__",
    "make_asgi_app",
    "make_wsgi_app",
    "start_metrics_server",
    "track_duration",
]
