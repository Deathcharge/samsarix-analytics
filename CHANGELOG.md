# Changelog

All notable changes are documented here. The project follows Semantic Versioning while
the public API remains pre-1.0.

## 0.3.0 - Unreleased

### Added

- Dependency-free WSGI and ASGI Prometheus endpoint factories.
- Explicit loopback-by-default standalone metrics server with deterministic shutdown.
- Optional bearer-token protection and strict HTTP method/path behavior.
- Framework-neutral WSGI/ASGI request middleware with bounded method/status-class
  labels and isolated recording failures.
- Deterministic JSON registry checkpoints with bounded decoding, strict restoration,
  atomic replacement, and SHA-256 integrity metadata.
- CLI checkpoint inspection plus scrapeable-server and restartable-worker examples.
- Evidence-backed competitive positioning and `0.3.0` acceptance criteria.
- Reproducible recording, rendering, checkpoint, and retention benchmark.
- Hardened bearer-token validation, regular-file checkpoint loading, and restored
  histogram consistency checks.
- Added a default 10 MiB byte budget to Prometheus HTTP rendering.
- Added synchronized release-metadata verification and an installed-wheel compatibility
  smoke test.
- Added a least-privilege GitHub Release workflow with immutable action pins,
  provenance attestations, release assets, and explicitly gated PyPI Trusted Publishing.
- Added strict UTF-8/string label validation, bounded histogram bucket definitions,
  linear-time checkpoint reconciliation, and complete truncated-history invariants.
- Added slow-client-resistant threaded HTTP serving, bounded credential parsing, and
  single-owner WSGI response cleanup.
- Added a hash-locked release builder set, exact distribution-manifest verification,
  injection-safe release metadata handling, and immutable GitHub release assets.

### Changed

- Expanded the product wedge from local metric collection to a small embedded
  observability control loop that interoperates with existing Prometheus deployments.
- Updated the verified development toolchain to build 1.5.0, mypy 2.3.0, pytest 9.1.1,
  pytest-cov 7.1.0, Ruff 0.16.2, and Twine 7.0.0.
- Label values must now be strings; implicit conversion of arbitrary objects was
  removed before the first public release to keep rejection work bounded.

## 0.2.0 - Unpublished productization baseline

### Added

- Typed, bounded counters, gauges, and histograms.
- JSON snapshot and Prometheus text export.
- Threshold alerts with label selection, histogram aggregations, cooldown,
  acknowledgement, auto-resolution, bounded history, and callback isolation.
- Deterministic CLI demo, runnable example, tests, CI, security guidance, and
  productization record.
- MPL-2.0 licensing, Samsarix LLC attribution, and explicit trademark guidance.

### Changed

- Reframed the repository as a dependency-free embedded Python telemetry library.
- Consolidated package configuration in `pyproject.toml` and raised the actual minimum
  Python version to 3.10.
- Corrected package metadata and documentation to reference the existing
  project license rather than MIT.
- Renamed the unreleased distribution, import package, CLI, and export schema from
  `helix-analytics` / `helix_analytics` to `samsarix-analytics` /
  `samsarix_analytics` before the first functional release.
- Replaced the mismatched customized BSL terms with standard MPL-2.0 file-level
  copyleft so distributed changes to covered source files remain available while
  larger applications can use the library under their own terms.

### Removed

- Unpublished `helix-hub-shared` and unrelated application-stack dependencies.
- Extracted monorepo modules that imported private `apps.backend.*` code, fabricated
  health/self-healing output, or duplicated incompatible metric and alert systems.
- Redundant `setup.py` metadata.
