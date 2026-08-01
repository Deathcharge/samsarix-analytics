# Performance and retention evidence

This is reproducible engineering evidence, not a universal performance guarantee.
Results depend on Python, operating system, CPU, power mode, labels, contention, and
metric configuration. Run the benchmark on the intended deployment hardware before
setting an overhead budget.

## Method

From repository revision `agent/competitive-observability` on August 1, 2026:

```bash
python -m benchmarks.benchmark_core --iterations 100000 --series 10
```

The script measures one thread updating ten labeled series. It then renders one
Prometheus snapshot, encodes one deterministic checkpoint, and asserts that histogram
retention equals the configured limit. It does not include HTTP framework overhead,
disk flush latency, lock contention across several threads, or a multi-hour soak.

## Observed result

Environment: Python 3.14.6 on `Windows-11-10.0.26200-SP0`.

- Counter updates: approximately 47,339/second.
- Histogram observations: approximately 37,774/second.
- Prometheus render: 9,478 bytes in 0.00550 seconds.
- Checkpoint encode: 63,013 bytes in 0.03153 seconds.
- Retained histogram samples: exactly 10,240 (`10 × 1,024`) after 100,000
  observations, confirming that old percentile samples were evicted at the configured
  bound while all-time count/sum/bucket aggregates remained available.

These figures are a single local run and should be interpreted as a regression
baseline. There is deliberately no timing assertion in CI because shared runners make
wall-clock thresholds noisy. Correctness tests enforce the retention and cardinality
invariants independently of speed.
