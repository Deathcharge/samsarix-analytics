# Changelog

All notable changes are documented here. The project follows Semantic Versioning while
the public API remains pre-1.0.

## 0.2.0 - Unreleased

### Added

- Typed, bounded counters, gauges, and histograms.
- JSON snapshot and Prometheus text export.
- Threshold alerts with label selection, histogram aggregations, cooldown,
  acknowledgement, auto-resolution, bounded history, and callback isolation.
- Deterministic CLI demo, runnable example, tests, CI, security guidance, and
  productization record.

### Changed

- Reframed the repository as a dependency-free embedded Python telemetry library.
- Consolidated package configuration in `pyproject.toml` and raised the actual minimum
  Python version to 3.10.
- Corrected package metadata and documentation to reference the existing
  source-available license rather than MIT.

### Removed

- Unpublished `helix-hub-shared` and unrelated application-stack dependencies.
- Extracted monorepo modules that imported private `apps.backend.*` code, fabricated
  health/self-healing output, or duplicated incompatible metric and alert systems.
- Redundant `setup.py` metadata.
