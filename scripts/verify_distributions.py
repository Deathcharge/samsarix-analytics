# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: MPL-2.0

"""Verify the exact release artifact set and print its SHA-256 manifest."""

from __future__ import annotations

import argparse
import hashlib
from collections.abc import Sequence
from pathlib import Path

from scripts.verify_release import verify_release


def distribution_manifest(root: Path, dist_dir: Path | None = None) -> dict[str, str]:
    """Return verified release filenames mapped to their SHA-256 digests."""

    version = verify_release(root)
    directory = dist_dir or root / "dist"
    expected = {
        f"samsarix_analytics-{version}-py3-none-any.whl",
        f"samsarix_analytics-{version}.tar.gz",
    }
    if not directory.is_dir():
        raise ValueError(f"distribution directory does not exist: {directory}")
    files = {path.name: path for path in directory.iterdir() if path.is_file()}
    if set(files) != expected:
        missing = sorted(expected - set(files))
        unexpected = sorted(set(files) - expected)
        details = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if unexpected:
            details.append(f"unexpected: {', '.join(unexpected)}")
        raise ValueError("invalid distribution artifact set (" + "; ".join(details) + ")")
    return {name: hashlib.sha256(files[name].read_bytes()).hexdigest() for name in sorted(files)}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--dist-dir", type=Path)
    args = parser.parse_args(argv)
    manifest = distribution_manifest(args.root.resolve(), args.dist_dir)
    for name, digest in manifest.items():
        print(f"{digest}  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
