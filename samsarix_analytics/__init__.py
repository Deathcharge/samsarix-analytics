# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: MPL-2.0

"""Bounded in-process metrics and threshold alerting for Python applications."""

from .checkpoint import (
    CHECKPOINT_SCHEMA_VERSION,
    CheckpointError,
    CheckpointInfo,
    CheckpointPolicy,
    decode_checkpoint,
    encode_checkpoint,
    load_checkpoint,
    save_checkpoint,
)
from .exposition import (
    PROMETHEUS_CONTENT_TYPE,
    ASGIApp,
    MetricsServer,
    WSGIApp,
    make_asgi_app,
    make_wsgi_app,
    start_metrics_server,
)
from .instrumentation import HTTPMetrics, instrument_asgi, instrument_wsgi
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

__version__ = "0.3.0"

__all__ = [
    "CHECKPOINT_SCHEMA_VERSION",
    "PROMETHEUS_CONTENT_TYPE",
    "ASGIApp",
    "Alert",
    "AlertManager",
    "AlertRule",
    "AlertSeverity",
    "AlertStatus",
    "CardinalityLimitError",
    "CheckpointError",
    "CheckpointInfo",
    "CheckpointPolicy",
    "Comparison",
    "Counter",
    "EvaluationResult",
    "Gauge",
    "HTTPMetrics",
    "Histogram",
    "MetricError",
    "MetricRegistry",
    "MetricSample",
    "MetricsServer",
    "WSGIApp",
    "__version__",
    "decode_checkpoint",
    "encode_checkpoint",
    "instrument_asgi",
    "instrument_wsgi",
    "load_checkpoint",
    "make_asgi_app",
    "make_wsgi_app",
    "save_checkpoint",
    "start_metrics_server",
    "track_duration",
]
