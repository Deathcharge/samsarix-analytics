# Security policy

## Supported versions

The unreleased `0.2.x` line is the only version currently receiving security fixes.
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
- avoid logging metric label values or other application data by default.

Applications remain responsible for authorizing access to exported snapshots and for
avoiding secrets, personal data, and high-cardinality identifiers in labels.

General product questions belong at contact@samsarix.com; security and support requests
belong at support@samsarix.com.
