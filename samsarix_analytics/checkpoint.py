# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: MPL-2.0

"""Bounded, atomic JSON checkpoints for local metric registries."""

from __future__ import annotations

import hashlib
import json
import math
import os
import stat
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from .monitoring.metrics import Counter, Gauge, Histogram, MetricError, MetricRegistry

CHECKPOINT_SCHEMA_VERSION = "samsarix-analytics-checkpoint/v1"


class CheckpointError(MetricError):
    """Raised when checkpoint data is malformed, unsafe, or incompatible."""


def _positive_integer(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise CheckpointError(f"{field_name} must be a positive integer")
    return value


@dataclass(frozen=True)
class CheckpointPolicy:
    """Hard limits applied before checkpoint data becomes live Python state."""

    max_file_bytes: int = 10 * 1024 * 1024
    max_metrics: int = 1000
    max_series_per_metric: int = 100
    max_histogram_samples: int = 1024
    max_label_value_length: int = 200

    def __post_init__(self) -> None:
        for name in (
            "max_file_bytes",
            "max_metrics",
            "max_series_per_metric",
            "max_histogram_samples",
            "max_label_value_length",
        ):
            _positive_integer(getattr(self, name), field_name=name)


@dataclass(frozen=True)
class CheckpointInfo:
    """Integrity and location details for a completed atomic checkpoint write."""

    path: Path
    bytes_written: int
    sha256: str
    schema_version: str = CHECKPOINT_SCHEMA_VERSION


def _object(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise CheckpointError(f"{path} must be a JSON object with string keys")
    return cast(Mapping[str, object], value)


def _array(value: object, path: str) -> list[object]:
    if not isinstance(value, list):
        raise CheckpointError(f"{path} must be a JSON array")
    return cast(list[object], value)


def _string(value: object, path: str) -> str:
    if not isinstance(value, str):
        raise CheckpointError(f"{path} must be a string")
    return value


def _integer(value: object, path: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise CheckpointError(f"{path} must be an integer greater than or equal to {minimum}")
    return value


def _number(value: object, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CheckpointError(f"{path} must be a finite number")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise CheckpointError(f"{path} must be a finite number")
    return normalized


def _limit(limits: Mapping[str, object], name: str, policy_limit: int) -> int:
    value = _integer(limits.get(name), f"limits.{name}", minimum=1)
    if value > policy_limit:
        raise CheckpointError(
            f"limits.{name}={value} exceeds the load policy limit of {policy_limit}"
        )
    return value


def _label_names(value: object, path: str) -> tuple[str, ...]:
    items = _array(value, path)
    return tuple(_string(item, f"{path}[{index}]") for index, item in enumerate(items))


def _labels(value: object, path: str) -> dict[str, str]:
    raw = _object(value, path)
    return {name: _string(label, f"{path}.{name}") for name, label in raw.items()}


def _common_definition(
    raw_metric: Mapping[str, object],
    *,
    path: str,
    registry: MetricRegistry,
    policy: CheckpointPolicy,
) -> tuple[str, str, tuple[str, ...], int]:
    name = _string(raw_metric.get("name"), f"{path}.name")
    description = _string(raw_metric.get("description"), f"{path}.description")
    label_names = _label_names(raw_metric.get("label_names"), f"{path}.label_names")
    max_series = _integer(raw_metric.get("max_series"), f"{path}.max_series", minimum=1)
    if max_series > policy.max_series_per_metric:
        raise CheckpointError(
            f"{path}.max_series={max_series} exceeds the load policy limit of "
            f"{policy.max_series_per_metric}"
        )
    label_limit = _integer(
        raw_metric.get("max_label_value_length"),
        f"{path}.max_label_value_length",
        minimum=1,
    )
    if label_limit != registry.max_label_value_length:
        raise CheckpointError(
            f"{path}.max_label_value_length does not match the registry definition"
        )
    return name, description, label_names, max_series


def _restore_scalar_series(
    instrument: Counter | Gauge,
    raw_series: object,
    *,
    path: str,
    label_names: Sequence[str],
    max_series: int,
) -> None:
    series = _array(raw_series, path)
    if len(series) > max_series:
        raise CheckpointError(f"{path} contains more than {max_series} series")
    seen: set[tuple[str, ...]] = set()
    for index, raw_item in enumerate(series):
        item_path = f"{path}[{index}]"
        item = _object(raw_item, item_path)
        labels = _labels(item.get("labels"), f"{item_path}.labels")
        key = tuple(labels.get(name, "") for name in label_names)
        if key in seen:
            raise CheckpointError(f"{item_path} duplicates an earlier label set")
        seen.add(key)
        value = _number(item.get("value"), f"{item_path}.value")
        if isinstance(instrument, Counter) and value < 0:
            raise CheckpointError(f"{item_path}.value cannot be negative for a counter")
        try:
            if isinstance(instrument, Counter):
                instrument.inc(value, **labels)
            else:
                instrument.set(value, **labels)
        except MetricError as exc:
            raise CheckpointError(f"{item_path} is invalid: {exc}") from exc


def _restore_histogram_series(
    histogram: Histogram,
    raw_series: object,
    *,
    path: str,
    max_series: int,
) -> None:
    series = _array(raw_series, path)
    if len(series) > max_series:
        raise CheckpointError(f"{path} contains more than {max_series} series")
    for index, raw_item in enumerate(series):
        item_path = f"{path}[{index}]"
        item = _object(raw_item, item_path)
        bucket_counts = [
            _integer(value, f"{item_path}.bucket_counts[{bucket_index}]")
            for bucket_index, value in enumerate(
                _array(item.get("bucket_counts"), f"{item_path}.bucket_counts")
            )
        ]
        recent = [
            _number(value, f"{item_path}.recent[{recent_index}]")
            for recent_index, value in enumerate(_array(item.get("recent"), f"{item_path}.recent"))
        ]
        try:
            histogram._restore_checkpoint_series(
                labels=_labels(item.get("labels"), f"{item_path}.labels"),
                count=_integer(item.get("count"), f"{item_path}.count", minimum=1),
                total=_number(item.get("sum"), f"{item_path}.sum"),
                minimum=_number(item.get("min"), f"{item_path}.min"),
                maximum=_number(item.get("max"), f"{item_path}.max"),
                bucket_counts=bucket_counts,
                recent=recent,
            )
        except MetricError as exc:
            raise CheckpointError(f"{item_path} is invalid: {exc}") from exc


def _restore_registry(root: Mapping[str, object], policy: CheckpointPolicy) -> MetricRegistry:
    schema = _string(root.get("schema_version"), "schema_version")
    if schema != CHECKPOINT_SCHEMA_VERSION:
        raise CheckpointError(
            f"unsupported checkpoint schema {schema!r}; expected {CHECKPOINT_SCHEMA_VERSION!r}"
        )
    limits = _object(root.get("limits"), "limits")
    registry = MetricRegistry(
        max_metrics=_limit(limits, "max_metrics", policy.max_metrics),
        max_series_per_metric=_limit(limits, "max_series_per_metric", policy.max_series_per_metric),
        max_histogram_samples=_limit(limits, "max_histogram_samples", policy.max_histogram_samples),
        max_label_value_length=_limit(
            limits, "max_label_value_length", policy.max_label_value_length
        ),
    )
    metrics = _array(root.get("metrics"), "metrics")
    if len(metrics) > registry.max_metrics:
        raise CheckpointError(f"metrics contains more than {registry.max_metrics} definitions")

    seen_names: set[str] = set()
    for index, raw_metric in enumerate(metrics):
        path = f"metrics[{index}]"
        metric = _object(raw_metric, path)
        name, description, label_names, max_series = _common_definition(
            metric, path=path, registry=registry, policy=policy
        )
        if name in seen_names:
            raise CheckpointError(f"{path}.name duplicates metric {name!r}")
        seen_names.add(name)
        kind = _string(metric.get("type"), f"{path}.type")
        try:
            if kind == "counter":
                counter = registry.counter(name, description, label_names, max_series=max_series)
                _restore_scalar_series(
                    counter,
                    metric.get("series"),
                    path=f"{path}.series",
                    label_names=label_names,
                    max_series=max_series,
                )
            elif kind == "gauge":
                gauge = registry.gauge(name, description, label_names, max_series=max_series)
                _restore_scalar_series(
                    gauge,
                    metric.get("series"),
                    path=f"{path}.series",
                    label_names=label_names,
                    max_series=max_series,
                )
            elif kind == "histogram":
                buckets = [
                    _number(value, f"{path}.buckets[{bucket_index}]")
                    for bucket_index, value in enumerate(
                        _array(metric.get("buckets"), f"{path}.buckets")
                    )
                ]
                max_samples = _integer(metric.get("max_samples"), f"{path}.max_samples", minimum=1)
                if max_samples > policy.max_histogram_samples:
                    raise CheckpointError(
                        f"{path}.max_samples={max_samples} exceeds the load policy limit of "
                        f"{policy.max_histogram_samples}"
                    )
                histogram = registry.histogram(
                    name,
                    description,
                    label_names,
                    buckets=buckets,
                    max_series=max_series,
                    max_samples=max_samples,
                )
                _restore_histogram_series(
                    histogram,
                    metric.get("series"),
                    path=f"{path}.series",
                    max_series=max_series,
                )
            else:
                raise CheckpointError(f"{path}.type has unsupported value {kind!r}")
        except MetricError as exc:
            if isinstance(exc, CheckpointError):
                raise
            raise CheckpointError(f"{path} has an invalid metric definition: {exc}") from exc
    return registry


def encode_checkpoint(
    registry: MetricRegistry,
    *,
    indent: int | None = None,
    max_bytes: int = 10 * 1024 * 1024,
) -> bytes:
    """Encode a deterministic JSON checkpoint without performing file I/O."""

    _positive_integer(max_bytes, field_name="max_bytes")
    try:
        payload = (
            json.dumps(
                registry._checkpoint_state(),
                allow_nan=False,
                indent=indent,
                separators=(",", ":") if indent is None else None,
                sort_keys=True,
            ).encode("utf-8")
            + b"\n"
        )
    except (TypeError, ValueError) as exc:
        raise CheckpointError(f"registry state cannot be encoded: {exc}") from exc
    if len(payload) > max_bytes:
        raise CheckpointError(
            f"encoded checkpoint is {len(payload)} bytes and exceeds max_bytes={max_bytes}"
        )
    return payload


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise CheckpointError(f"checkpoint contains duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise CheckpointError(f"checkpoint contains non-finite JSON constant {value!r}")


def decode_checkpoint(
    data: bytes,
    *,
    policy: CheckpointPolicy | None = None,
) -> MetricRegistry:
    """Validate and restore registry state from bounded UTF-8 JSON bytes."""

    policy = policy or CheckpointPolicy()
    if not isinstance(data, bytes):
        raise TypeError("checkpoint data must be bytes")
    if len(data) > policy.max_file_bytes:
        raise CheckpointError(
            f"checkpoint is {len(data)} bytes and exceeds "
            f"policy.max_file_bytes={policy.max_file_bytes}"
        )
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CheckpointError("checkpoint must be valid UTF-8") from exc
    try:
        parsed = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except CheckpointError:
        raise
    except (ValueError, RecursionError) as exc:
        raise CheckpointError(f"checkpoint is not valid bounded JSON: {exc}") from exc
    return _restore_registry(_object(cast(object, parsed), "checkpoint"), policy)


def save_checkpoint(
    registry: MetricRegistry,
    path: str | os.PathLike[str],
    *,
    indent: int | None = None,
    max_bytes: int = 10 * 1024 * 1024,
) -> CheckpointInfo:
    """Atomically replace ``path`` with a private, flushed registry checkpoint."""

    target = Path(path)
    if not target.parent.is_dir():
        raise FileNotFoundError(f"checkpoint parent directory does not exist: {target.parent}")
    if target.is_dir():
        raise IsADirectoryError(f"checkpoint path is a directory: {target}")
    payload = encode_checkpoint(registry, indent=indent, max_bytes=max_bytes)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return CheckpointInfo(
        path=target.absolute(),
        bytes_written=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
    )


def load_checkpoint(
    path: str | os.PathLike[str],
    *,
    policy: CheckpointPolicy | None = None,
) -> MetricRegistry:
    """Read at most the configured byte limit and restore a validated registry."""

    policy = policy or CheckpointPolicy()
    target = Path(path)
    if target.is_dir():
        raise CheckpointError(f"checkpoint path must be a regular file: {target}")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(target, flags)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise CheckpointError(f"checkpoint path must be a regular file: {target}")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = -1
            payload = handle.read(policy.max_file_bytes + 1)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    return decode_checkpoint(payload, policy=policy)


__all__ = [
    "CHECKPOINT_SCHEMA_VERSION",
    "CheckpointError",
    "CheckpointInfo",
    "CheckpointPolicy",
    "decode_checkpoint",
    "encode_checkpoint",
    "load_checkpoint",
    "save_checkpoint",
]
