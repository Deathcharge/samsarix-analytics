# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: MPL-2.0

"""Exercise the installed public package without importing the source checkout."""

from __future__ import annotations

import argparse
import tempfile
import urllib.request
from pathlib import Path

from samsarix_analytics import (
    MetricRegistry,
    __version__,
    load_checkpoint,
    save_checkpoint,
    start_metrics_server,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="Expected installed package version")
    arguments = parser.parse_args()
    if __version__ != arguments.version:
        parser.error(f"installed version is {__version__}, expected {arguments.version}")

    registry = MetricRegistry()
    registry.counter("release_jobs_total", "Completed release smoke jobs").inc(2)
    with tempfile.TemporaryDirectory(prefix="samsarix-release-smoke-") as directory:
        checkpoint = Path(directory) / "registry.json"
        save_checkpoint(registry, checkpoint)
        restored = load_checkpoint(checkpoint)

    with (
        start_metrics_server(restored, port=0) as server,
        urllib.request.urlopen(server.url, timeout=5) as response,
    ):
        output = response.read().decode("utf-8")

    if "release_jobs_total 2" not in output:
        parser.error("installed package did not preserve and expose the smoke metric")
    print(f"installed samsarix-analytics {__version__} smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
