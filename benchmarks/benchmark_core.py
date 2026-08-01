# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: MPL-2.0

"""Measure core recording, rendering, checkpoint, and retention behavior."""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from typing import cast

from samsarix_analytics import MetricRegistry, encode_checkpoint


def _rate(iterations: int, elapsed: float) -> float:
    return iterations / elapsed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=100_000)
    parser.add_argument("--series", type=int, default=10)
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("--iterations must be positive")
    if args.series < 1:
        parser.error("--series must be positive")

    registry = MetricRegistry(
        max_metrics=10,
        max_series_per_metric=args.series,
        max_histogram_samples=1024,
    )
    counter = registry.counter("benchmark_operations_total", "Benchmark operations", ("slot",))
    histogram = registry.histogram(
        "benchmark_operation_seconds",
        "Synthetic benchmark observations",
        ("slot",),
    )

    started = time.perf_counter()
    for index in range(args.iterations):
        counter.inc(slot=str(index % args.series))
    counter_elapsed = time.perf_counter() - started

    started = time.perf_counter()
    for index in range(args.iterations):
        histogram.observe((index % 1000) / 1000, slot=str(index % args.series))
    histogram_elapsed = time.perf_counter() - started

    started = time.perf_counter()
    prometheus = registry.to_prometheus()
    prometheus_elapsed = time.perf_counter() - started

    started = time.perf_counter()
    checkpoint = encode_checkpoint(registry)
    checkpoint_elapsed = time.perf_counter() - started

    retained_samples = 0
    for slot in range(args.series):
        summary = histogram.summary(slot=str(slot))
        if summary is None:
            raise RuntimeError(f"missing benchmark histogram series {slot}")
        retained_samples += cast(int, summary["recent_count"])
    expected_retained = min(args.iterations, args.series * histogram.max_samples)
    if retained_samples != expected_retained:
        raise RuntimeError(
            f"retention invariant failed: retained {retained_samples}, expected {expected_retained}"
        )

    print(
        json.dumps(
            {
                "checkpoint_bytes": len(checkpoint),
                "checkpoint_encode_seconds": checkpoint_elapsed,
                "counter_updates_per_second": _rate(args.iterations, counter_elapsed),
                "histogram_observations_per_second": _rate(args.iterations, histogram_elapsed),
                "iterations": args.iterations,
                "platform": platform.platform(),
                "prometheus_bytes": len(prometheus.encode("utf-8")),
                "prometheus_render_seconds": prometheus_elapsed,
                "python": sys.version.split()[0],
                "retained_histogram_samples": retained_samples,
                "series": args.series,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
