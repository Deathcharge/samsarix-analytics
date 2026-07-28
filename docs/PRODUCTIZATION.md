# Productization record

This document is the living release record for `helix-analytics`. It distinguishes
implemented behavior from inherited claims and owner-controlled work.

## Repository assessment

The repository was extracted from `helix-unified` in June 2026. At audit start it
contained 6,600 lines across several overlapping monitoring implementations, but no
tests, examples, CI workflow, package root, or standalone entry point. Most of the
larger modules imported the private `apps.backend.*` tree from the original monorepo.
The built wheel therefore contained metadata only, while the README claimed a
production-ready package, examples, documentation, CI, and MIT licensing that did not
exist or contradicted `LICENSE`.

The defensible product is a small embedded Python library for developers who need to
record bounded in-process counters, gauges, and histograms, evaluate deterministic
threshold alerts, and export JSON or Prometheus text without operating another
service. It is intentionally not a hosted observability platform, dashboard, database,
agent monitor, or replacement for OpenTelemetry.

## Target user and primary use case

- Target user: a Python application or library developer who wants local telemetry
  for a process, test harness, CLI, worker, or small service.
- Primary journey: install the package, define labeled metrics with explicit memory
  limits, record values, evaluate a threshold rule, then serialize a JSON snapshot or
  expose Prometheus-compatible text.
- Independent reason to exist: a dependency-free local store is useful before or
  without adopting an OpenTelemetry SDK, collector, Prometheus client runtime, or
  Helix service.

## Product and architecture decisions

- The public API is explicit and small: `MetricRegistry`, `Counter`, `Gauge`,
  `Histogram`, `AlertManager`, and `AlertRule`.
- Metric names and label names are validated. Values must be finite. Counters cannot
  decrease.
- Series cardinality, histogram sample retention, label length, metric count, and
  alert history are bounded to prevent accidental process-memory amplification.
- JSON and Prometheus export are local, synchronous operations with no network,
  telemetry, credentials, or automatic background threads.
- Prometheus export escapes untrusted label values and help text. High-cardinality
  identifiers and personal data are documented as unsafe label choices.
- OpenTelemetry metrics for Python are stable, so an OTel adapter is a plausible P2
  extension. It is deliberately not a core dependency because the first release is a
  lightweight embedded store.
- The obsolete extracted modules were removed rather than shipped as misleading
  placeholders. The previous wheel did not contain them, so there is no published
  package API to preserve.
- Python 3.10 is the minimum because the existing code already used Python 3.10 union
  syntax. The CI target is Python 3.10 through 3.14.
- `pyproject.toml` is the single packaging source of truth; the duplicate `setup.py`
  was removed.

## Assumptions

- No released PyPI artifact or documented external consumer relies on the extracted
  `apps.backend.*` modules. If one exists, compatibility adapters should be built from
  real consumer evidence rather than preserving nonfunctional source paths.
- Metric definitions are developer-controlled. Metric label values and observations
  may be influenced by application users and are therefore validated and bounded.
- `LICENSE` expresses owner intent even though its `Licensed Work` parameter names
  “Helix Licensing System” rather than this repository. That mismatch requires owner
  or legal review and is not silently rewritten here.

## Baseline results (revision `4f1fdfb`)

| Command | Actual result |
| --- | --- |
| `python --version` | Passed: Python 3.11.9. |
| `python -m compileall -q .` | Passed, proving syntax only. |
| clean-venv `python -m pip install -e .` | Failed: unpublished `helix-hub-shared>=0.1.0`. |
| clean-venv `python -m pip install -r requirements.txt` | Failed: pinned `anthropic==0.7.10` unavailable. |
| `python -m pytest tests/ -v --cov=src` | Failed: `tests/` did not exist. |
| `python -m pytest -q` | Failed: no tests collected. |
| `python -m black --check helix_analytics` | Failed: 10 files required formatting. |
| `python -m flake8 helix_analytics` | Failed with hundreds of style violations. |
| `python -m mypy helix_analytics` | Failed with 30 errors in 7 files. |
| `python -m build` | Exited 0, but the wheel contained only five metadata files and no importable package. |

## Prioritized findings

### P0

- [x] Remove the unpublished `helix-hub-shared` runtime dependency.
- [x] Add a real package root and configure package discovery.
- [x] Remove private `apps.backend.*` runtime imports from the release surface.
- [x] Replace documentation claims for missing examples, tests, docs, and CI.
- [x] Complete the install-record-alert-export journey and package-level tests.

### P1

- [x] Remove duplicate alert/metrics/health implementations with contradictory behavior.
- [x] Remove fabricated health, workflow, agent, and self-healing results.
- [x] Bound all memory-amplification paths and validate metric/label input.
- [x] Correct threshold rule evaluation, cooldown, resolution, and handler isolation.
- [x] Add type checking, linting, coverage, wheel-content verification, and CI.
- [x] Correct package metadata to reference the existing source-available license rather
  than MIT.

### P2

- [ ] Optional OpenTelemetry adapter.
- [ ] Optional ASGI/WSGI endpoint helpers for Prometheus output.
- [ ] Persistence adapter for process restarts.
- [ ] Multiprocess metric aggregation.

## Implementation checklist

- [x] Deliberate typed public API.
- [x] Bounded labeled counters, gauges, and histograms.
- [x] Deterministic JSON and Prometheus export.
- [x] Threshold alerting with cooldown and auto-resolution.
- [x] Runnable CLI demo and source example.
- [x] Unit, integration, CLI, and installed-wheel tests.
- [x] CI across supported Python versions.
- [x] Accurate README, contribution, security, and changelog documents.
- [x] Adversarial review and final clean-environment verification.

## Release acceptance criteria

- A new Python 3.10+ virtual environment can install the source tree and built wheel.
- The documented demo produces a metric snapshot and a real triggered alert.
- JSON output is serializable and Prometheus text follows the supported exposition
  subset, including label escaping.
- Metric and alert storage cannot grow beyond configured limits.
- Invalid metric names, labels, values, thresholds, and counter decrements fail clearly.
- Lint, format check, strict type check, tests with at least 90% branch coverage, build,
  wheel inspection, and metadata validation pass.
- No local P0 remains and no core-path placeholder is shipped.

## Completed work

- Protected-worktree, history, file inventory, source, manifest, documentation, and
  baseline audit.
- Bounded official-document research covering current Prometheus cardinality guidance,
  stable OpenTelemetry Python metrics, and modern `pyproject.toml` license metadata.
- Removal of extracted modules that required private Helix infrastructure or returned
  fabricated product behavior.
- Packaging and dependency metadata consolidation around a single `pyproject.toml`.
- A typed, thread-safe metrics registry with explicit caps on metrics, labeled series,
  label lengths, histogram samples, alert rules, callbacks, and alert history.
- Real threshold evaluation, cooldown and resolution behavior, callback isolation,
  deterministic export, a CLI demo, and a source example.
- A 36-test suite with branch coverage above the 90% release gate, strict type and lint
  checks, distribution-content checks, and a Python 3.10-3.14 CI workflow.

## Release disposition

The engineering result is a release candidate: the local acceptance criteria pass and
there is no known core-path P0. Public publication remains blocked on owner/legal
confirmation of the repository-specific modified BSL parameters and on owner-controlled
PyPI credentials and name ownership. Until those gates are closed, do not describe the
package as generally available or production-deployed.

## Deferred and externally blocked work

- Owner/legal: confirm that the modified BSL text applies to `helix-analytics`, correct
  the `Licensed Work` name, and confirm the production-use threshold and pricing URL.
- Owner/release: confirm PyPI name ownership, publication credentials, release tag, and
  whether publishing a source-available package to PyPI is desired.
- Production deployment is not applicable to the core library. No package publication,
  live infrastructure, credentials, or external accounts are created by this work.

## Known risks

- This is a pre-1.0 API rebuilt from an unpublished/nonfunctional package shape; users
  evaluating source imports from the old tree will need to migrate.
- In-process metrics disappear on restart and are not suitable for multiprocess
  aggregation.
- Percentiles are calculated over a configured bounded recent sample window, not an
  all-time streaming quantile sketch.
- Prometheus labels can expose sensitive data or create costly cardinality when chosen
  poorly; limits reduce but do not eliminate the need for sound label design.

## Distribution and sustainability

The simplest distribution is a pure-Python wheel and sdist built from
`pyproject.toml`. There is no hosted operating cost: the library performs no network
requests and stores data only in the host process. A plausible sustainability model is
owner-supported source-available distribution plus paid support or commercial license
terms, subject to resolving the current license wording. Hosted subscriptions are out
of scope and would add cost and operational obligations unsupported by this code.
