# Releasing Samsarix Analytics

Releases are deliberate supply-chain events, not a side effect of merging to `main`.
The repository builds and tests every supported Python version in CI; publishing starts
only when a GitHub Release is published for a tag that exactly matches the package
version.

## One-time PyPI setup

The `samsarix-analytics` PyPI project did not exist when checked on August 10, 2026.
The protected GitHub `pypi` environment and `PYPI_PUBLISH_ENABLED=false` gate were
configured on August 10, 2026. Before the first publication, an authorized Samsarix
LLC owner must:

1. retain the project chain-of-title record described in `LICENSING.md`;
2. create a pending PyPI Trusted Publisher for owner `Deathcharge`, repository
   `samsarix-analytics`, workflow `release.yml`, and environment `pypi`;
3. set the repository variable `PYPI_PUBLISH_ENABLED` to `true` only after PyPI accepts
   that publisher configuration.

No long-lived PyPI token belongs in GitHub, a developer machine, or a repository file.
Until the variable is enabled, releases still receive checked distributions and GitHub
provenance attestations, while the PyPI job is visibly skipped.

## Release checklist

1. Update `CHANGELOG.md`, replacing `Unreleased` with the release date.
2. Update the version in `pyproject.toml`, `samsarix_analytics/__init__.py`, and
   `CITATION.cff` when preparing a new version.
3. Run the complete local checks from `CONTRIBUTING.md`, including:

   ```bash
   python scripts/verify_release.py
   python -m pip install --require-hashes -r requirements-release.txt
   python -m build --no-isolation
   python -m twine check dist/*
   python -m scripts.verify_distributions
   ```

   Then prove the wheel works without help from the source checkout (POSIX shell):

   ```bash
   checkout="$(pwd)"
   python -m venv /tmp/samsarix-analytics-smoke
   /tmp/samsarix-analytics-smoke/bin/python -m pip install --no-deps dist/*.whl
   cd /tmp
   /tmp/samsarix-analytics-smoke/bin/python -I \
     "$checkout/scripts/smoke_installed.py" --version 0.3.0
   ```

4. Merge the release-preparation pull request and require green CI on its exact head.
5. Publish a GitHub Release from the verified `main` commit with tag `v<version>`.
6. Confirm the Release workflow built one wheel and one source distribution, attached
   both to the release, and produced provenance attestations.
7. If PyPI publishing is enabled, confirm both files appear under the expected project
   and version with verified project URLs.

`requirements-release.txt` is the reviewed Linux/Python 3.14 release lock generated
from `requirements-release.in`; regenerate it with the command recorded in its header
and review every dependency and hash change. Builds also derive `SOURCE_DATE_EPOCH`
from the release commit. The workflow rejects a tag that differs from the synchronized
repository version and refuses to replace an existing GitHub asset. Existing GitHub and
PyPI filenames are treated as immutable, so retry a failed upload only after determining
whether any distribution was already accepted.

## Verification and rollback

Download release assets and verify their GitHub provenance with:

```bash
gh attestation verify samsarix_analytics-<version>-py3-none-any.whl \
  --repo Deathcharge/samsarix-analytics
```

PyPI releases cannot be replaced. If a release is defective, yank the affected PyPI
version, mark the GitHub Release accordingly, document the reason, and publish a new
patch version. Never move or recreate an already-published release tag.
