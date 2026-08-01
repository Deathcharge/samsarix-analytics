# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: MPL-2.0

"""Expose live demo metrics on a loopback Prometheus endpoint."""

from __future__ import annotations

import argparse
import time

from samsarix_analytics import MetricRegistry, start_metrics_server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=9464)
    parser.add_argument("--seconds", type=float, default=15.0)
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error("--seconds must be positive")

    registry = MetricRegistry()
    runs = registry.counter("demo_runs_total", "Completed demo loop iterations")
    elapsed = registry.gauge("demo_elapsed_seconds", "Elapsed demo time in seconds")
    started = time.monotonic()

    with start_metrics_server(registry, port=args.port) as server:
        print(f"Scrape {server.url}")
        while (age := time.monotonic() - started) < args.seconds:
            runs.inc()
            elapsed.set(age)
            time.sleep(min(1.0, args.seconds - age))


if __name__ == "__main__":
    main()
