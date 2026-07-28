"""Copy-pasteable metrics, alerting, and export example."""

import json

from helix_analytics import AlertManager, AlertRule, Comparison, MetricRegistry

registry = MetricRegistry(max_series_per_metric=50)
jobs = registry.counter("jobs_total", "Jobs processed", ("status",))
duration = registry.histogram(
    "job_duration_seconds",
    "Job duration in seconds",
    ("queue",),
    buckets=(0.1, 0.5, 1.0, 5.0),
)

jobs.inc(status="ok")
jobs.inc(status="failed")
duration.observe(1.4, queue="default")

alerts = AlertManager()
alerts.add_rule(
    AlertRule(
        name="slow_default_queue",
        metric="job_duration_seconds",
        aggregation="p95",
        operator=Comparison.GT,
        threshold=1.0,
        labels={"queue": "default"},
    )
)
evaluation = alerts.evaluate(registry)

print(json.dumps(evaluation.to_dict(), indent=2))
print(registry.to_prometheus())
