# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.verify_distributions import distribution_manifest
from scripts.verify_release import repository_versions, verify_release


def test_repository_release_versions_agree() -> None:
    root = Path(__file__).resolve().parents[1]
    assert repository_versions(root) == {
        "pyproject.toml": "0.3.0",
        "samsarix_analytics/__init__.py": "0.3.0",
        "CITATION.cff": "0.3.0",
    }
    assert verify_release(root, tag="v0.3.0") == "0.3.0"


def test_release_verification_rejects_mismatched_metadata_and_tag(tmp_path: Path) -> None:
    (tmp_path / "samsarix_analytics").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "example"\nversion = "1.2.3"\n', encoding="utf-8"
    )
    (tmp_path / "samsarix_analytics" / "__init__.py").write_text(
        '__version__ = "1.2.4"\n', encoding="utf-8"
    )
    (tmp_path / "CITATION.cff").write_text("version: 1.2.3\n", encoding="utf-8")

    with pytest.raises(ValueError, match="do not match"):
        verify_release(tmp_path)

    (tmp_path / "samsarix_analytics" / "__init__.py").write_text(
        '__version__ = "1.2.3"\n', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="must equal"):
        verify_release(tmp_path, tag="v1.2.4")


def test_distribution_manifest_requires_exact_release_artifacts(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    dist = tmp_path / "dist"
    dist.mkdir()
    wheel = dist / "samsarix_analytics-0.3.0-py3-none-any.whl"
    sdist = dist / "samsarix_analytics-0.3.0.tar.gz"
    wheel.write_bytes(b"wheel")
    sdist.write_bytes(b"sdist")

    manifest = distribution_manifest(root, dist)
    assert set(manifest) == {wheel.name, sdist.name}
    (dist / "unexpected.txt").write_text("unexpected", encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected"):
        distribution_manifest(root, dist)


def test_installed_smoke_rejects_source_checkout_import() -> None:
    root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(root)

    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "smoke_installed.py"), "--version", "0.3.0"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "imported the source checkout" in result.stderr
