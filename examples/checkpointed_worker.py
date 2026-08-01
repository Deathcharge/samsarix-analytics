# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: MPL-2.0

"""Resume bounded worker metrics from an explicit local checkpoint."""

from __future__ import annotations

import argparse
from pathlib import Path

from samsarix_analytics import MetricRegistry, load_checkpoint, save_checkpoint


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("state", type=Path, help="checkpoint file to create or resume")
    parser.add_argument("--jobs", type=int, default=3, help="jobs completed in this run")
    args = parser.parse_args()
    if args.jobs < 0:
        parser.error("--jobs cannot be negative")

    registry = load_checkpoint(args.state) if args.state.exists() else MetricRegistry()
    jobs = registry.counter("worker_jobs_total", "Jobs completed across checkpointed runs")
    jobs.inc(args.jobs)
    checkpoint = save_checkpoint(registry, args.state, indent=2)

    print(f"jobs_total={jobs.value():g}")
    print(f"checkpoint={checkpoint.path}")
    print(f"sha256={checkpoint.sha256}")


if __name__ == "__main__":
    main()
