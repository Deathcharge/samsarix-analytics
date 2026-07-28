from __future__ import annotations

import json

import pytest

from helix_analytics import __version__
from helix_analytics.cli import main


def test_demo_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["demo", "--format", "json"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["schema_version"] == "helix-analytics-demo/v1"
    assert len(output["evaluation"]["triggered"]) == 1
    assert output["evaluation"]["errors"] == {}


def test_demo_prometheus(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["demo", "--format", "prometheus"]) == 0
    output = capsys.readouterr().out
    assert "# TYPE demo_http_requests_total counter" in output
    assert "demo_http_request_duration_seconds_bucket" in output


def test_help_and_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "usage: helix-analytics" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="0"):
        main(["--version"])
    assert __version__ in capsys.readouterr().out
