# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import json
from pathlib import Path

import pytest

from samsarix_analytics import MetricRegistry, __version__, save_checkpoint
from samsarix_analytics.cli import main


def test_demo_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["demo", "--format", "json"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["schema_version"] == "samsarix-analytics-demo/v1"
    assert len(output["evaluation"]["triggered"]) == 1
    assert output["evaluation"]["errors"] == {}


def test_demo_prometheus(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["demo", "--format", "prometheus"]) == 0
    output = capsys.readouterr().out
    assert "# TYPE demo_http_requests_total counter" in output
    assert "demo_http_request_duration_seconds_bucket" in output


def test_help_and_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "usage: samsarix-analytics" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="0"):
        main(["--version"])
    assert __version__ in capsys.readouterr().out


def test_inspect_checkpoint_json_and_prometheus(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    registry = MetricRegistry()
    registry.counter("saved_total", "Saved").inc(2)
    target = tmp_path / "state.json"
    save_checkpoint(registry, target)

    assert main(["inspect", str(target)]) == 0
    assert json.loads(capsys.readouterr().out)["metrics"][0]["name"] == "saved_total"
    assert main(["inspect", str(target), "--format", "prometheus"]) == 0
    assert "saved_total 2" in capsys.readouterr().out


def test_inspect_checkpoint_reports_actionable_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "missing.json"
    assert main(["inspect", str(missing)]) == 2
    assert "No such file" in capsys.readouterr().err

    target = tmp_path / "large.json"
    target.write_text("{}", encoding="utf-8")
    assert main(["inspect", str(target), "--max-bytes", "0"]) == 2
    assert "positive integer" in capsys.readouterr().err
