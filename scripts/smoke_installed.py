# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: MPL-2.0

"""Exercise the installed public package without importing the source checkout."""

from __future__ import annotations

import argparse
import tempfile
import urllib.request
from importlib.util import find_spec
from pathlib import Path


def _assert_installed_origin() -> None:
    spec = find_spec("samsarix_analytics")
    if spec is None or spec.origin is None:
        raise RuntimeError("could not locate the installed samsarix_analytics package")
    source_package = Path(__file__).resolve().parents[1] / "samsarix_analytics"
    imported_origin = Path(spec.origin).resolve()
    if imported_origin.is_relative_to(source_package):
        raise RuntimeError("smoke test imported the source checkout instead of an installed wheel")


_assert_installed_origin()

from samsarix_analytics import (  # noqa: E402
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
