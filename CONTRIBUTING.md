# Contributing to helix-analytics

Thanks for improving the project. Keep changes focused on the embedded metrics and
threshold-alerting product described in the README; hosted services, dashboards,
databases, authentication, and Helix-private integrations require an evidence-backed
product decision before implementation.

## Setup

```bash
git clone https://github.com/Deathcharge/helix-analytics.git
cd helix-analytics
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

## Quality checks

Run the same checks as CI:

```bash
python -m ruff format --check .
python -m ruff check .
python -m mypy helix_analytics
python -m pytest --cov=helix_analytics --cov-report=term-missing
python -m build
python -m twine check dist/*
```

New behavior needs tests for the successful path and the important validation,
capacity, or failure path. Public functions and classes need type annotations and
concise docstrings. Keep the runtime dependency-free unless a dependency creates a
clear, documented benefit that cannot be achieved safely in the standard library.

## Compatibility and public API

`helix_analytics.__all__` and `helix_analytics.monitoring.__all__` define the supported
public API. Treat removals or behavioral incompatibilities as deliberate pre-1.0
breaking changes and record them in `CHANGELOG.md`.

Metric export is security- and cost-sensitive. Changes must preserve escaping,
finite-number validation, cardinality limits, bounded sample/history retention, and
handler isolation. Never add automatic telemetry or network export without a visible,
opt-in configuration surface.

## Pull requests

Describe the user problem, the chosen behavior, and exact verification performed.
Avoid generated dashboards, performance claims, or integrations that cannot be tested
from this repository. Report security issues privately as described in `SECURITY.md`.

By contributing, you agree that your contribution is distributed under the repository's
existing license terms. The current license naming mismatch is owner-controlled and
documented in `docs/PRODUCTIZATION.md`.
