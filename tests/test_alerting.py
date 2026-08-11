# Copyright 2026 Samsarix LLC
# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Event, Thread

import pytest

from samsarix_analytics import (
    AlertManager,
    AlertRule,
    AlertSeverity,
    AlertStatus,
    Comparison,
    MetricRegistry,
    MetricSample,
)


def test_alert_lifecycle_cooldown_and_handler_isolation(caplog: pytest.LogCaptureFixture) -> None:
    registry = MetricRegistry()
    queue = registry.gauge("queue_depth", "Queue depth", ("queue",))
    queue.set(12, queue="critical")
    manager = AlertManager(max_history=1)
    manager.add_rule(
        AlertRule(
            name="queue_backlog",
            metric="queue_depth",
            operator=Comparison.GT,
            threshold=10,
            severity=AlertSeverity.ERROR,
            labels={"queue": "critical"},
            cooldown_seconds=60,
        )
    )
    observed: list[AlertStatus] = []
    manager.add_handler(lambda alert: observed.append(alert.status))

    def broken_handler(_alert: object) -> None:
        raise RuntimeError("handler failed")

    manager.add_handler(broken_handler)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)

    first = manager.evaluate(registry, now=start)
    assert len(first.triggered) == 1
    alert = first.triggered[0]
    assert manager.acknowledge(alert.id, now=start + timedelta(seconds=1))
    assert alert.status is AlertStatus.ACKNOWLEDGED

    queue.set(4, queue="critical")
    cleared = manager.evaluate(registry, now=start + timedelta(seconds=2))
    assert cleared.resolved == (alert,)
    assert alert.status is AlertStatus.RESOLVED

    queue.set(20, queue="critical")
    cooling = manager.evaluate(registry, now=start + timedelta(seconds=30))
    assert not cooling.triggered
    retriggered = manager.evaluate(registry, now=start + timedelta(seconds=61))
    assert len(retriggered.triggered) == 1
    assert observed == [AlertStatus.ACTIVE, AlertStatus.RESOLVED, AlertStatus.ACTIVE]
    assert "alert handler failed" in caplog.text
    assert manager.snapshot()["limits"] == {
        "max_history": 1,
        "max_rules": 100,
        "max_handlers": 20,
    }


def test_evaluation_errors_are_explicit() -> None:
    manager = AlertManager()
    manager.add_rule(
        AlertRule(
            name="missing_metric",
            metric="missing",
            operator=Comparison.GE,
            threshold=1,
        )
    )
    result = manager.evaluate(MetricRegistry())
    assert "not registered" in result.errors["missing_metric"]


def test_rule_and_manager_validation() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        AlertRule("", "metric", Comparison.EQ, 1)
    with pytest.raises(ValueError, match="finite"):
        AlertRule("name", "metric", Comparison.EQ, float("nan"))
    with pytest.raises(ValueError, match="non-negative"):
        AlertRule("name", "metric", Comparison.EQ, 1, cooldown_seconds=-1)
    with pytest.raises(ValueError, match="at least 1"):
        AlertManager(max_history=0)
    with pytest.raises(ValueError, match="at least 1"):
        AlertManager(max_rules=0)
    with pytest.raises(ValueError, match="at least 1"):
        AlertManager(max_handlers=0)
    with pytest.raises(ValueError, match="operator"):
        AlertRule("name", "metric", ">", 1)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="severity"):
        AlertRule(
            "name",
            "metric",
            Comparison.GT,
            1,
            severity="warning",  # type: ignore[arg-type]
        )

    manager = AlertManager()
    rule = AlertRule("duplicate", "metric", Comparison.EQ, 1)
    manager.add_rule(rule)
    with pytest.raises(ValueError, match="already registered"):
        manager.add_rule(rule)
    manager.add_rule(rule, replace=True)
    assert manager.remove_rule("duplicate")
    assert not manager.remove_rule("duplicate")
    assert not manager.acknowledge("missing")
    assert not manager.resolve("missing")
    with pytest.raises(ValueError, match="timezone-aware"):
        manager.evaluate(MetricRegistry(), now=datetime(2026, 1, 1))


def test_rule_and_handler_limits() -> None:
    manager = AlertManager(max_rules=1, max_handlers=1)
    manager.add_rule(AlertRule("one", "metric", Comparison.EQ, 1))
    with pytest.raises(ValueError, match="rule limit"):
        manager.add_rule(AlertRule("two", "metric", Comparison.EQ, 1))
    manager.add_handler(lambda _alert: None)
    with pytest.raises(ValueError, match="handler limit"):
        manager.add_handler(lambda _alert: None)


@pytest.mark.parametrize(
    ("operator", "value", "threshold", "expected"),
    [
        (Comparison.GT, 2, 1, True),
        (Comparison.GE, 1, 1, True),
        (Comparison.LT, 0, 1, True),
        (Comparison.LE, 1, 1, True),
        (Comparison.EQ, 1, 1, True),
        (Comparison.EQ, 2, 1, False),
    ],
)
def test_comparisons(operator: Comparison, value: float, threshold: float, expected: bool) -> None:
    assert operator.matches(value, threshold) is expected


def test_nonmatching_labels_active_update_no_auto_resolve_and_manual_resolve() -> None:
    registry = MetricRegistry()
    gauge = registry.gauge("load", "Load", ("host",))
    gauge.set(8, host="one")
    gauge.set(9, host="two")
    manager = AlertManager()
    manager.add_rule(
        AlertRule(
            "host_one_load",
            "load",
            Comparison.GT,
            5,
            labels={"host": "one"},
            auto_resolve=False,
        )
    )

    first = manager.evaluate(registry)
    assert len(first.triggered) == 1
    alert = first.triggered[0]
    gauge.set(10, host="one")
    assert not manager.evaluate(registry).triggered
    assert alert.current_value == 10
    gauge.set(0, host="one")
    assert not manager.evaluate(registry).resolved
    assert manager.resolve(alert.id)
    assert alert.status is AlertStatus.RESOLVED


def test_removing_or_replacing_rule_discards_retained_series_state() -> None:
    registry = MetricRegistry()
    gauge = registry.gauge("queue_depth", "Queue depth", ("queue",))
    gauge.set(10, queue="jobs")
    manager = AlertManager()
    manager.add_rule(
        AlertRule(
            "queue_high",
            gauge.name,
            Comparison.GT,
            5,
            labels={"queue": "jobs"},
        )
    )
    assert len(manager.evaluate(registry).triggered) == 1

    manager.add_rule(
        AlertRule("queue_high", gauge.name, Comparison.GT, 20),
        replace=True,
    )
    assert manager.snapshot()["active"] == []

    gauge.set(30, queue="jobs")
    assert len(manager.evaluate(registry).triggered) == 1
    assert manager.remove_rule("queue_high") is True
    assert manager.snapshot()["active"] == []


def test_rule_removed_during_query_cannot_recreate_alert_state() -> None:
    query_started = Event()
    continue_query = Event()

    class PausedRegistry(MetricRegistry):
        def query(self, name: str, aggregation: str = "value") -> list[MetricSample]:
            samples = super().query(name, aggregation)
            query_started.set()
            assert continue_query.wait(2)
            return samples

    registry = PausedRegistry()
    registry.gauge("queue_depth", "Queue depth").set(10)
    manager = AlertManager()
    manager.add_rule(AlertRule("queue_high", "queue_depth", Comparison.GT, 5))
    results = []
    evaluator = Thread(target=lambda: results.append(manager.evaluate(registry)))
    evaluator.start()
    assert query_started.wait(2)
    assert manager.remove_rule("queue_high")
    continue_query.set()
    evaluator.join(2)

    assert not evaluator.is_alive()
    assert results and results[0].triggered == ()
    assert manager.snapshot()["active"] == []
