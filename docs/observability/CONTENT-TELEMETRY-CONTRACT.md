# Restricted AI interaction telemetry contract

## Status and boundary

`sanctum.ai-interaction/v1` is the source contract for a restricted,
content-bearing interaction and evaluation stream. Its local persistence
adapter stores validated and redacted records in a separate private spool. It
does not collect interactions at a call site, upload records, or make an S3 or
Splunk change.

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
Adding collection or export requires a separate reviewed change with private
runtime binding, access enforcement, deletion behavior, and live validation.

## Durable local spool

The synchronous `gate/content-telemetry/spool.mjs` adapter requires both an
explicitly enabled validated policy and an absolute owner-bound root. Disabled
or invalid configuration creates no directories and writes nothing. A private
deployment should bind the root beneath its external private prefix (for
example, `telemetry/content`), never beneath the source tree or the operational
`ops/` spool.

The root and its `pending`, `failed`, `quarantine`, and `staging` directories
must be owner-owned mode `0700`; record and lock files are created exclusively
at mode `0600` without following a final-component symlink. Existing unsafe
permissions, ownership, file types, or symlinks cause a best-effort failure and
are never repaired by broadening access.

Each append prepares the object through the contract, writes one bounded JSONL
record to a uniquely named staging file, flushes it, and atomically renames it
into `pending`. Thus each pending file is a sealed one-record rotation unit for
later immutable delivery. The default spool limits are 1,000 files and 64 MiB;
configured limits are bounded and reject a new append instead of deleting any
pending, failed, quarantined, or staged state.

Recovery revalidates canonical redacted records. A complete staged record is
promoted to `pending`; valid `pending` and `failed` files remain recoverable;
partial, malformed, unredacted, oversized, or otherwise invalid files move to
`quarantine` with private file mode enforced. A later process may reclaim the
exclusive writer lock only when its recorded writer PID no longer exists, so a
crash does not strand recoverable staged state. No state in this slice is
uploaded or silently expired. Spool,
permission, validation, lock, and I/O failures return a content-free failure
signal, emit no raw exception/log fallback, and have no authority, routing,
egress, response-delivery, evaluator, verifier, or completion effect.
