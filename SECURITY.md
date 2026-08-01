# Security policy

## Supported versions

The unreleased `0.3.x` line is the only version currently receiving security fixes.
There is no production service operated by this repository.

## Reporting a vulnerability

Use the repository's **Security** tab to submit a private GitHub security advisory.
Do not include secrets, personal data, or exploit details in a public issue. If private
advisories are unavailable, email support@samsarix.com. If email is unavailable, open
a public issue containing only a request for a private maintainer contact channel.

## Trust model and invariants

`samsarix-analytics` is embedded in the caller's Python process. Metric definitions and
alert rules are trusted developer configuration; observed numeric values and label
values may come from untrusted application activity.

The package must:

- validate metric and label names before rendering;
- escape help text and label values in Prometheus output;
- reject non-finite values and counter decrements;
- bound metric definitions, series cardinality, retained samples, label length, and
  alert rules, handlers, and history;
- isolate alert callback failures;
- perform no implicit network, file, credential, or environment access;
- bind the opt-in standalone metrics server to loopback by default;
- compare optional bearer credentials without data-dependent string comparison;
- normalize HTTP instrumentation to a fixed method/status-class label space and never
  capture raw paths, queries, headers, bodies, or client addresses;
- isolate instrumentation recording failures from the wrapped application;
- reject oversized, malformed, duplicate-keyed, non-finite, or internally inconsistent
  checkpoint data before it becomes live metric state;
- write checkpoints through private, flushed, same-directory temporary files followed
  by atomic replacement;
- avoid logging metric label values or other application data by default.

Applications remain responsible for authorizing access to exported snapshots and HTTP
endpoints and for avoiding secrets, personal data, and high-cardinality identifiers in
labels. The standalone server is intended for loopback or trusted private networks; use
a TLS-capable application server or reverse proxy when metrics cross a trust boundary.
Checkpoint files can contain the same application labels and values as exported
metrics. Keep them out of web roots and source control, restrict filesystem access, and
choose a smaller `CheckpointPolicy` when accepting state from outside the process's
trust boundary.

General product questions belong at contact@samsarix.com; security and support requests
belong at support@samsarix.com.
