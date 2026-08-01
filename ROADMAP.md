# Samsarix Analytics roadmap

This roadmap separates four gates: merge, release, publication, and flagship adoption. Passing one does not imply the next.

## Product boundary

Portfolio role: **reusable library or sdk**. Keep this as a small, independently versioned package. Samsarix Unified should consume it only through a public API adapter; private monorepo imports and copied implementations are out of scope.

Current disposition: Merge the productization branch after exact-head verification and rollback-ref creation; release and adoption remain separate decisions.

## Stabilize the productized default

- Keep the default branch buildable from a clean checkout and preserve exact-head CI evidence.
- Keep Samsarix LLC branding, package identity, license metadata, and compatibility aliases internally consistent.
- Preserve the pre-productization default under a rollback ref before merging; do not delete legacy history.
- Review priority: Review draft PR #2 and licensing authority, run CI, then integrate into one low-risk portfolio process before publication.

## Release candidate

- Build and install the wheel in a clean environment.
- Prove one real consumer and a versioned compatibility fixture.
- Publish only after package-name ownership, licensing, provenance, and rollback are recorded.

Current hardening backlog:

- Prometheus WSGI/ASGI and loopback endpoint helpers are implemented for `0.3.0`.
- Explicit bounded registry checkpoints are implemented for restartable local jobs.
- No multiprocess aggregation, alert-manager checkpoint, or OpenTelemetry adapter.
- A reproducible core benchmark exists; a real external application consumer and
  multi-hour soak evidence are still missing.
- Percentiles use a bounded recent window and can be misunderstood as global quantiles.
- Publishing, API compatibility policy, and Samsarix LLC chain-of-title confirmation remain owner/legal gates.

## Competitive `0.3.0` slice

- [x] Document the product wedge against current Prometheus and OpenTelemetry guidance.
- [x] Add exact-path WSGI and ASGI Prometheus applications.
- [x] Add an explicitly managed, loopback-by-default standalone server.
- [x] Add privacy-conscious WSGI/ASGI request lifecycle instrumentation.
- [x] Add deterministic, atomic, bounded registry checkpoints and CLI inspection.
- [x] Add scrapeable and restartable-worker examples.
- [x] Add reproducible recording, rendering, checkpoint, and retention benchmarks.
- [ ] Prove the release slice from a clean built wheel and the remote CI matrix.

## Samsarix adoption

- Define a public API, event, schema, artifact, or deployment contract before connecting to Samsarix Unified.
- Add a consumer-owned contract fixture covering authentication, privacy, limits, errors, and version compatibility.
- Make one implementation canonical; remove or freeze duplicate behavior only after parity and rollback are proven.
- Record an owner, support level, compatibility window, and measurable adoption signal.

## Completion evidence

A milestone is complete only when its exact commit, commands and results, artifact digest, consumer or deployment, and rollback path are recorded in a pull request or release record. README claims must not exceed that evidence.
