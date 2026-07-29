# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: MPL-2.0

"""Command-line evaluation path for samsarix-analytics."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from . import __version__
from .monitoring import AlertManager, AlertRule, AlertSeverity, Comparison, MetricRegistry


def build_demo() -> tuple[MetricRegistry, AlertManager, dict[str, object]]:
    """Build a deterministic example with one genuinely triggered alert."""

    registry = MetricRegistry(max_series_per_metric=20, max_histogram_samples=100)
    requests = registry.counter(
        "demo_http_requests_total",
        "Demo HTTP requests processed",
        ("method", "status"),
    )
    latency = registry.histogram(
        "demo_http_request_duration_seconds",
        "Demo HTTP request latency in seconds",
        ("route",),
        buckets=(0.1, 0.25, 0.5, 1.0),
    )

    for status, duration in (("200", 0.08), ("200", 0.12), ("500", 0.72)):
        requests.inc(method="GET", status=status)
        latency.observe(duration, route="/demo")

    alerts = AlertManager(max_history=100)
    alerts.add_rule(
        AlertRule(
            name="demo_high_p95_latency",
            metric=latency.name,
            aggregation="p95",
            operator=Comparison.GT,
            threshold=0.5,
            severity=AlertSeverity.WARNING,
            labels={"route": "/demo"},
            cooldown_seconds=60,
        )
    )
    evaluation = alerts.evaluate(registry)
    output: dict[str, object] = {
        "schema_version": "samsarix-analytics-demo/v1",
        "metrics": registry.snapshot(),
        "alerts": alerts.snapshot(),
        "evaluation": evaluation.to_dict(),
    }
    return registry, alerts, output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="samsarix-analytics",
        description="Inspect a deterministic Samsarix Analytics metrics and alerting demo.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command")
    demo = subparsers.add_parser("demo", help="record demo metrics and evaluate an alert")
    demo.add_argument(
        "--format",
        choices=("json", "prometheus"),
        default="json",
        help="output format (default: json)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface and return a process exit code."""

    parser = _parser()
    args = parser.parse_args(argv)
    if args.command != "demo":
        parser.print_help()
        return 0

    registry, _alerts, output = build_demo()
    if args.format == "prometheus":
        print(registry.to_prometheus(), end="")
    else:
        print(json.dumps(output, indent=2, sort_keys=True))
    return 0
