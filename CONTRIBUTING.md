# Contributing to Samsarix Analytics

Thanks for improving the project. Keep changes focused on the embedded metrics and
threshold-alerting product described in the README; hosted services, dashboards,
databases, authentication, and private cross-repository integrations require an evidence-backed
product decision before implementation.

## Setup

```bash
git clone https://github.com/Deathcharge/samsarix-analytics.git
cd samsarix-analytics
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
python -m mypy samsarix_analytics benchmarks scripts
python scripts/verify_release.py
python -m pytest --cov=samsarix_analytics --cov-report=term-missing
python -m pip install --require-hashes -r requirements-release.txt
python -m build --no-isolation
python -m twine check dist/*
python -m scripts.verify_distributions
```

New behavior needs tests for the successful path and the important validation,
capacity, or failure path. Public functions and classes need type annotations and
concise docstrings. Keep the runtime dependency-free unless a dependency creates a
clear, documented benefit that cannot be achieved safely in the standard library.

## Compatibility and public API

`samsarix_analytics.__all__` and `samsarix_analytics.monitoring.__all__` define the supported
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

By contributing, you represent that you have the right to submit the work and agree
that your contribution is distributed under MPL-2.0. Preserve SPDX, copyright,
license, and attribution notices. Do not add third-party code unless its provenance and
license compatibility are documented in the pull request.

The source-code license does not grant rights to Samsarix names or logos. See
`LICENSING.md`, `NOTICE`, and `TRADEMARKS.md` for the complete project policy.

Maintainers preparing a tag must follow `docs/RELEASING.md`. Do not upload a locally
built distribution or add a long-lived package-index token to repository secrets.
