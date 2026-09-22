# Restricted AI interaction telemetry contract

## Status and boundary

`sanctum.ai-interaction/v1` is the source contract for a future restricted,
content-bearing interaction and evaluation stream. This slice defines and
tests the record boundary only. It does not collect, persist, spool, upload, or
export records and makes no S3 or Splunk change.

This stream is separate from the existing metadata-only operational telemetry
under `ops/` and from manual Observability Cloud traces and metrics. Content
records may never be written through either existing path.

Content telemetry is disabled by default. A future integration may enable it
only through explicit owner configuration. When enabled, collection is
all-or-nothing for every eligible authenticated Sanctum user interaction; no
per-request or silent sampling/exclusion policy exists in this version.

Telemetry is observational, best-effort, non-fatal, and non-authoritative. A
failure to prepare or eventually deliver a record must not affect authority,
routing, egress, capability, evaluation, verification, or completion.

## Record and privacy rules

The canonical schema is
`config/schemas/content-telemetry-v1.schema.json`. It permits only:

- event/interaction identity, UTC timestamp, and run/session/trace correlation;
- the explicit `user_query` and nullable `delivered_response` content fields;
- terminal outcome and structured failure stage/category/code;
- model role, model, revision, and provider;
- optional latency and token counts; and
- optional owner rating, evaluator result, benchmark, and test-case identity.

Success, failure, blocked, denied, and unknown terminal outcomes are distinct.
Failure diagnostics are bounded codes; raw exception text is not a field.
Unknown properties are rejected at every object boundary. In particular,
arbitrary headers, cookies, tool bodies, source bodies, file contents, private
keys, and hidden chain-of-thought/reasoning are not record fields.

Before a valid record can be handed to any future persistence adapter,
`prepareContentTelemetryRecord` redacts recognized authorization credentials,
provider-style tokens, named secret assignments, JWTs, and PEM private keys
from the two explicit content fields. The schema bounds query text to 16,384
characters, delivered response to 32,768 characters, identifiers/codes and
numeric metrics individually, and the final UTF-8 JSON record to 65,536 bytes.
Invalid or oversized records are rejected without returning content values.

Redaction is defense in depth, not permission to add broader input surfaces.
A future persistence integration must call the preparation function and must
not accept already-serialized or arbitrary objects as content records.

## Future owner configuration hooks

The contract reserves three validated, non-secret policy hooks:

- `enabled`: boolean, default `false`;
- `retention_days`: `null` until the owner chooses a policy, otherwise 1–3650;
- `access_policy`: `owner_only` by default, or
  `owner_authorized_reviewers` after explicit owner configuration.

These hooks define policy intent only. They contain no credentials, endpoints,
bucket names, indexes, account bindings, or private infrastructure values.
Adding persistence or export requires a separate reviewed change with private
runtime binding, access enforcement, deletion behavior, and live validation.
