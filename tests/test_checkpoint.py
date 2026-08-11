# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

import samsarix_analytics.checkpoint as checkpoint_module
from samsarix_analytics import MetricRegistry
from samsarix_analytics.checkpoint import (
    CHECKPOINT_SCHEMA_VERSION,
    CheckpointError,
    CheckpointPolicy,
    decode_checkpoint,
    encode_checkpoint,
    load_checkpoint,
    save_checkpoint,
)


def _populated_registry() -> MetricRegistry:
    registry = MetricRegistry(
        max_metrics=10,
        max_series_per_metric=3,
        max_histogram_samples=2,
        max_label_value_length=20,
    )
    counter = registry.counter("jobs_total", "Jobs", ("status",))
    counter.inc(3, status="ok")
    counter.inc(0, status="empty")
    registry.gauge("queue_depth", "Queue depth", ("queue",)).set(-2, queue="default")
    histogram = registry.histogram(
        "job_seconds",
        "Job duration",
        ("queue",),
        buckets=(0.1, 0.5, 1.0),
    )
    for value in (0.05, 0.4, 1.2):
        histogram.observe(value, queue="default")
    return registry


def test_checkpoint_bytes_are_deterministic_and_round_trip_exact_state() -> None:
    registry = _populated_registry()
    payload = encode_checkpoint(registry)

    assert payload == encode_checkpoint(registry)
    assert payload.endswith(b"\n")
    assert json.loads(payload)["schema_version"] == CHECKPOINT_SCHEMA_VERSION

    restored = decode_checkpoint(payload)
    assert restored.snapshot() == registry.snapshot()
    assert restored.to_prometheus() == registry.to_prometheus()
    assert restored.query("job_seconds", "p95") == registry.query("job_seconds", "p95")

    restored_histogram = restored.histogram(
        "job_seconds",
        "Job duration",
        ("queue",),
        buckets=(0.1, 0.5, 1.0),
    )
    restored_histogram.observe(0.2, queue="default")
    summary = restored_histogram.summary(queue="default")
    assert summary is not None
    assert summary["count"] == 4
    assert summary["recent_count"] == 2


def test_checkpoint_loads_v1_payload_without_new_bucket_limit() -> None:
    state = json.loads(encode_checkpoint(_populated_registry()))
    del state["limits"]["max_histogram_buckets"]

    restored = decode_checkpoint(json.dumps(state).encode())

    assert restored.snapshot() == _populated_registry().snapshot()


def test_checkpoint_policy_preserves_legacy_positional_argument_order() -> None:
    policy = CheckpointPolicy(1, 2, 3, 4, 5)

    assert policy.max_label_value_length == 5
    assert policy.max_histogram_buckets == 64


def test_save_is_atomic_private_and_returns_integrity_metadata(tmp_path: Path) -> None:
    target = tmp_path / "state" / "metrics.json"
    target.parent.mkdir()
    registry = _populated_registry()

    info = save_checkpoint(registry, target, indent=2)

    payload = target.read_bytes()
    assert info.path == target.absolute()
    assert info.bytes_written == len(payload)
    assert info.sha256 == hashlib.sha256(payload).hexdigest()
    assert info.schema_version == CHECKPOINT_SCHEMA_VERSION
    assert load_checkpoint(target).snapshot() == registry.snapshot()
    assert list(target.parent.glob(f".{target.name}.*.tmp")) == []


def test_failed_replace_preserves_previous_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "metrics.json"
    target.write_bytes(b"previous checkpoint")

    def fail_replace(_source: object, _target: object) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(checkpoint_module.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated"):
        save_checkpoint(_populated_registry(), target)

    assert target.read_bytes() == b"previous checkpoint"
    assert list(tmp_path.glob(f".{target.name}.*.tmp")) == []


def test_checkpoint_size_and_load_policy_are_enforced(tmp_path: Path) -> None:
    payload = encode_checkpoint(_populated_registry())
    with pytest.raises(CheckpointError, match="max_bytes"):
        encode_checkpoint(_populated_registry(), max_bytes=len(payload) - 1)
    with pytest.raises(CheckpointError, match="max_file_bytes"):
        decode_checkpoint(payload, policy=CheckpointPolicy(max_file_bytes=len(payload) - 1))
    with pytest.raises(CheckpointError, match="max_metrics"):
        decode_checkpoint(payload, policy=CheckpointPolicy(max_metrics=5))
    with pytest.raises(CheckpointError, match="max_series_per_metric"):
        decode_checkpoint(payload, policy=CheckpointPolicy(max_series_per_metric=2))
    with pytest.raises(CheckpointError, match="max_histogram_samples"):
        decode_checkpoint(payload, policy=CheckpointPolicy(max_histogram_samples=1))
    with pytest.raises(CheckpointError, match="max_histogram_buckets"):
        decode_checkpoint(payload, policy=CheckpointPolicy(max_histogram_buckets=2))
    with pytest.raises(CheckpointError, match="max_label_value_length"):
        decode_checkpoint(payload, policy=CheckpointPolicy(max_label_value_length=10))

    target = tmp_path / "oversized.json"
    target.write_bytes(payload)
    with pytest.raises(CheckpointError, match="max_file_bytes"):
        load_checkpoint(target, policy=CheckpointPolicy(max_file_bytes=len(payload) - 1))


@pytest.mark.parametrize(
    "data",
    [
        b"not json",
        b"\xff",
        b'{"schema_version": NaN}',
        b'{"schema_version":"one","schema_version":"two"}',
        b"[]",
    ],
)
def test_malformed_checkpoint_bytes_are_rejected(data: bytes) -> None:
    with pytest.raises(CheckpointError):
        decode_checkpoint(data)


def test_checkpoint_schema_and_series_invariants_are_validated() -> None:
    state = json.loads(encode_checkpoint(_populated_registry()))
    state["schema_version"] = "future/v99"
    with pytest.raises(CheckpointError, match="unsupported checkpoint schema"):
        decode_checkpoint(json.dumps(state).encode())

    state = json.loads(encode_checkpoint(_populated_registry()))
    state["metrics"].append(state["metrics"][0])
    with pytest.raises(CheckpointError, match="duplicates metric"):
        decode_checkpoint(json.dumps(state).encode())

    state = json.loads(encode_checkpoint(_populated_registry()))
    counter = next(metric for metric in state["metrics"] if metric["type"] == "counter")
    counter["series"][0]["value"] = -1
    with pytest.raises(CheckpointError, match="cannot be negative"):
        decode_checkpoint(json.dumps(state).encode())

    state = json.loads(encode_checkpoint(_populated_registry()))
    histogram = next(metric for metric in state["metrics"] if metric["type"] == "histogram")
    histogram["series"][0]["bucket_counts"] = [3, 1, 2]
    with pytest.raises(CheckpointError, match="cumulative"):
        decode_checkpoint(json.dumps(state).encode())

    state = json.loads(encode_checkpoint(_populated_registry()))
    histogram = next(metric for metric in state["metrics"] if metric["type"] == "histogram")
    histogram["series"][0]["sum"] = 100
    with pytest.raises(CheckpointError, match="mean must be within"):
        decode_checkpoint(json.dumps(state).encode())

    state = json.loads(encode_checkpoint(_populated_registry()))
    histogram = next(metric for metric in state["metrics"] if metric["type"] == "histogram")
    histogram["series"][0]["bucket_counts"][:2] = [0, 0]
    with pytest.raises(CheckpointError, match="cannot be empty"):
        decode_checkpoint(json.dumps(state).encode())

    state = json.loads(encode_checkpoint(_populated_registry()))
    histogram = next(metric for metric in state["metrics"] if metric["type"] == "histogram")
    histogram["series"][0]["min"] = 0.2
    with pytest.raises(CheckpointError, match="below min must be empty"):
        decode_checkpoint(json.dumps(state).encode())

    state = json.loads(encode_checkpoint(_populated_registry()))
    histogram = next(metric for metric in state["metrics"] if metric["type"] == "histogram")
    histogram["buckets"][-1] = 2.0
    with pytest.raises(CheckpointError, match="at or above max"):
        decode_checkpoint(json.dumps(state).encode())

    state = json.loads(encode_checkpoint(_populated_registry()))
    histogram = next(metric for metric in state["metrics"] if metric["type"] == "histogram")
    histogram["series"][0]["count"] = 2**63
    with pytest.raises(CheckpointError, match="signed 64-bit"):
        decode_checkpoint(json.dumps(state).encode())

    state = json.loads(encode_checkpoint(_populated_registry()))
    counter = next(metric for metric in state["metrics"] if metric["type"] == "counter")
    counter["series"][0]["value"] = 10**400
    with pytest.raises(CheckpointError, match="finite number"):
        decode_checkpoint(json.dumps(state).encode())

    state = json.loads(encode_checkpoint(_populated_registry()))
    counter = next(metric for metric in state["metrics"] if metric["type"] == "counter")
    counter["series"][0]["labels"]["status"] = "\ud800"
    with pytest.raises(CheckpointError, match="valid UTF-8"):
        decode_checkpoint(json.dumps(state).encode())


def test_truncated_histogram_extrema_must_match_bucket_counts() -> None:
    registry = MetricRegistry(max_histogram_samples=1)
    histogram = registry.histogram("latency", "Latency", buckets=(5.0,))
    histogram.observe(10)
    histogram.observe(0)
    state = json.loads(encode_checkpoint(registry))
    state["metrics"][0]["series"][0]["bucket_counts"] = [2]

    with pytest.raises(CheckpointError, match="below max cannot contain count"):
        decode_checkpoint(json.dumps(state).encode())


def test_checkpoint_rejects_bucket_arrays_before_element_conversion() -> None:
    state = json.loads(encode_checkpoint(_populated_registry()))
    state["limits"]["max_histogram_buckets"] = 2
    histogram = next(metric for metric in state["metrics"] if metric["type"] == "histogram")
    histogram["buckets"] = [1.0, 2.0, 10**400]

    with pytest.raises(CheckpointError, match="more than 2 buckets"):
        decode_checkpoint(json.dumps(state).encode())


def test_checkpoint_path_and_argument_validation(tmp_path: Path) -> None:
    with pytest.raises(CheckpointError, match="positive integer"):
        CheckpointPolicy(max_file_bytes=0)
    with pytest.raises(CheckpointError, match="positive integer"):
        encode_checkpoint(_populated_registry(), max_bytes=0)
    with pytest.raises(TypeError, match="must be bytes"):
        decode_checkpoint("not bytes")  # type: ignore[arg-type]
    with pytest.raises(FileNotFoundError, match="parent directory"):
        save_checkpoint(_populated_registry(), tmp_path / "missing" / "state.json")
    with pytest.raises(IsADirectoryError, match="directory"):
        save_checkpoint(_populated_registry(), tmp_path)
    with pytest.raises(CheckpointError, match="regular file"):
        load_checkpoint(tmp_path)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFOs are not available on this platform")
def test_checkpoint_loader_rejects_fifo_without_blocking(tmp_path: Path) -> None:
    fifo = tmp_path / "checkpoint.fifo"
    os.mkfifo(fifo)
    with pytest.raises(CheckpointError, match="regular file"):
        load_checkpoint(fifo)
