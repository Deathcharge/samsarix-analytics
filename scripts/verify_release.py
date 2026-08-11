# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: MPL-2.0

"""Verify that release versions agree across repository metadata."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

_VERSION = r"[0-9]+\.[0-9]+\.[0-9]+(?:[a-zA-Z0-9.+-]*)"


def _match_version(text: str, pattern: str, *, source: str) -> str:
    match = re.search(pattern, text, flags=re.MULTILINE)
    if match is None:
        raise ValueError(f"could not find a version in {source}")
    return match.group(1)


def repository_versions(root: Path) -> dict[str, str]:
    """Return release versions from each authoritative metadata file."""

    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    project_section = re.search(
        r"^\[project\]\s*$\n(?P<body>.*?)(?=^\[|\Z)",
        pyproject,
        flags=re.MULTILINE | re.DOTALL,
    )
    if project_section is None:
        raise ValueError("could not find [project] in pyproject.toml")

    return {
        "pyproject.toml": _match_version(
            project_section.group("body"),
            rf'^version\s*=\s*"({_VERSION})"\s*$',
            source="pyproject.toml",
        ),
        "samsarix_analytics/__init__.py": _match_version(
            (root / "samsarix_analytics" / "__init__.py").read_text(encoding="utf-8"),
            rf'^__version__\s*=\s*"({_VERSION})"\s*$',
            source="samsarix_analytics/__init__.py",
        ),
        "CITATION.cff": _match_version(
            (root / "CITATION.cff").read_text(encoding="utf-8"),
            rf"^version:\s*({_VERSION})\s*$",
            source="CITATION.cff",
        ),
    }


def verify_release(root: Path, *, tag: str | None = None) -> str:
    """Return the synchronized version or raise for a mismatch or invalid tag."""

    versions = repository_versions(root)
    unique_versions = set(versions.values())
    if len(unique_versions) != 1:
        details = ", ".join(f"{source}={version}" for source, version in versions.items())
        raise ValueError(f"release versions do not match: {details}")

    version = unique_versions.pop()
    if tag is not None and tag != f"v{version}":
        raise ValueError(f"release tag {tag!r} must equal 'v{version}'")
    return version


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--tag", help="Git release tag, expected to be v<project version>")
    arguments = parser.parse_args()

    try:
        version = verify_release(arguments.root.resolve(), tag=arguments.tag)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"release verification failed: {exc}\n")
    print(f"release metadata agrees on {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
