# Restricted AI interaction telemetry contract

## Status and boundary

`sanctum.ai-interaction/v1` is the source contract for a restricted,
content-bearing interaction stream. The authenticated gate
records one terminal outcome for each owner-enabled conversational interaction
and its local persistence adapter stores validated and redacted records in a
separate private spool. A separately configured delivery process may upload
only sealed canonical batches to a dedicated S3 content prefix. Live AWS IAM,
bucket, scheduler and Splunk changes remain explicit later owner actions.

This stream is separate from the existing metadata-only operational telemetry
under `ops/` and from manual Observability Cloud traces and metrics. Content
records may never be written through either existing path.

Content telemetry is disabled by default and may be enabled only through the
reviewed `content_telemetry` owner configuration in the private rendered gate
settings. When enabled, collection is
all-or-nothing for every eligible authenticated Sanctum user interaction; no
per-request or silent sampling/exclusion policy exists in this version.

Telemetry is observational, best-effort, non-fatal, and non-authoritative.
Quality annotations, benchmark datasets, and offline replay results are
likewise evidence only. A
failure to prepare or eventually deliver a record must not affect authority,
routing, egress, capability, evaluation, verification, or completion.

## Record and privacy rules

The canonical schema is
`config/schemas/content-telemetry-v1.schema.json`. It permits only:

- event/interaction identity, UTC timestamp, and run/session/trace correlation;
- the explicit `user_query` and nullable `delivered_response` content fields;
- terminal outcome and structured failure stage/category/code;
- model role, model, revision, and provider; and
- optional latency and token counts.

Success, failure, blocked, denied, and unknown terminal outcomes are distinct.
Failure diagnostics are bounded codes; raw exception text is not a field.
Unknown properties are rejected at every object boundary. In particular,
arbitrary headers, cookies, tool bodies, source bodies, file contents, private
keys, and hidden chain-of-thought/reasoning are not record fields.

Quality data is deliberately absent from the interaction record. It is never
added later by rewriting the original query/response event.

Before a valid record can be handed to the local persistence adapter,
`prepareContentTelemetryRecord` redacts recognized authorization credentials,
provider-style tokens, named secret assignments, JWTs, and PEM private keys
from the two explicit content fields. The schema bounds query text to 16,384
characters, delivered response to 32,768 characters, identifiers/codes and
numeric metrics individually, and the final UTF-8 JSON record to 65,536 bytes.
Invalid or oversized records are rejected without returning content values.

Redaction is defense in depth, not permission to add broader input surfaces.
The persistence integration calls the preparation function and does not accept
already-serialized or arbitrary objects as content records.

## Owner configuration hooks

The contract exposes three validated, non-secret policy hooks:

- `enabled`: boolean, default `false`;
- `retention_days`: `null` until the owner chooses a policy, otherwise 1–3650;
- `access_policy`: `owner_only` by default, or
  `owner_authorized_reviewers` after explicit owner configuration.

These hooks define collection policy intent only. They contain no credentials,
endpoints, bucket names, indexes, account bindings, or private infrastructure
values. The local root is derived from the private rendered state directory as
`telemetry/content`; it is not model- or request-selectable. Delivery uses a
distinct owner-only private file with the destination and AWS profile name;
credential values remain solely in the external AWS credential store.

## Durable local spool

The synchronous `gate/content-telemetry/spool.mjs` adapter requires both an
explicitly enabled validated policy and an absolute owner-bound root. Disabled
or invalid configuration creates no directories and writes nothing. A private
deployment should bind the root beneath its external private prefix (for
example, `telemetry/content`), never beneath the source tree or the operational
`ops/` spool.

The root and its `pending`, `failed`, `quarantine`, `staging`, and `uploading` directories
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

Recovery revalidates canonical redacted records. A complete staged or interrupted
upload record is promoted to `pending`; valid `pending` and `failed` files remain recoverable;
partial, malformed, unredacted, oversized, or otherwise invalid files move to
`quarantine` with private file mode enforced. A later process may reclaim the
exclusive writer lock only when its recorded writer PID no longer exists, so a
crash does not strand recoverable staged state. No state in this slice is
uploaded or silently expired. Spool,
permission, validation, lock, and I/O failures return a content-free failure
signal, emit no raw exception/log fallback, and have no authority, routing,
egress, response-delivery, evaluator, verifier, or completion effect.

## Append-only quality annotations

`sanctum.quality-annotation/v1` records quality evidence separately and refers
to the immutable source interaction only by `interaction_id`. One interaction
may have no annotations or any number of private annotation records. Each
append requires an operator-stable `operation_id`; the annotation identity is
the SHA-256 digest of that operation and interaction identity. Exact replay
returns the existing record, while reuse of the identity with changed evidence
raises an explicit conflict. Files are exclusively created beneath an
absolute, owner-only `0700` annotation root at mode `0600`.

The schema supports an optional 1–5 owner rating, bounded evaluator/model and
revision identifiers, benchmark/test-case identity and version, named scores,
pass/fail, a fixed semantic failure category, and structured grounding and
citation signals. Semantic failure categories are enums and can be queried
without interpreting prose. Evaluator prompts, explanations, source or tool
bodies, arbitrary metadata, hidden reasoning, instructions, and authority
claims are not fields. `authority_effect` is fixed to `NONE`.

## Curated benchmark export and offline replay

`exportBenchmarkDataset` creates `sanctum.benchmark-dataset/v1` from an exact
selection of already validated interaction records. Selection is bounded to
100 cases, must name every interaction and versioned test case explicitly,
rejects duplicate or missing interaction identities, and reuses the content
contract's credential redaction. The dataset contains only the selected query,
nullable delivered reference response, and stable identities; it cannot carry
tools, sources, private metadata, reasoning, or authority instructions.

`runOfflineReplay` accepts two to eight explicit model/revision configurations
and matching provider functions supplied by the operator. It does not discover
providers, credentials, or network destinations and grants no egress. Each
provider receives only a frozen benchmark case packet. Results use the
`sanctum.benchmark-replay/v1` format, have a stable replay identity derived from
the operator run ID, dataset version, and ordered configurations, and retain
only a redacted response, bounded latency, and structured failure category.
Provider objects with extra fields are recorded as `INVALID_RESULT`, so a
provider cannot smuggle source text, tool output, evaluator prompts, or hidden
reasoning into result metadata. `compareBenchmarkReplay` compares every result
set with the first configuration using case counts and exact-response matches;
it makes no completion or quality decision.

## Immutable S3 delivery

`gate/content-telemetry/delivery.mjs` is a standalone, owner-scheduled process;
it is not part of request handling and cannot affect a Sanctum response. A run
claims at most the configured number of `pending` and `failed` files. It
revalidates private ownership, permissions, canonical serialization, schema,
redaction and size before any network call. Invalid, partial or malformed
files move to private quarantine and are never uploaded.

Each canonical one-record batch maps deterministically to
`PREFIX/YYYY/MM/DD/EVENT_ID-SHA256.jsonl`. The AWS CLI adapter sends
`PutObject` with `If-None-Match: *`, content type `application/x-ndjson`, and
the batch digest as non-secret object metadata. A successful write removes the
claimed local copy. An HTTP 412/`PreconditionFailed` on the same digest-bound
key reconciles a prior or duplicate successful write without replacing it.
Other ambiguous failures receive exponential backoff only up to the configured
attempt bound, then return the intact batch to `failed` for a later run. A
crash in `uploading` is recovered to `pending` before another run.

The adapter suppresses AWS CLI output and exposes only bounded counts. It does
not log batch content, destination values, profile contents, process
environment, or provider diagnostics. The writer credential needs only
conditional `s3:PutObject` for the content object prefix; it does not need
`GetObject`, `ListBucket`, overwrite, delete, or any permission under `ops/`.

## Authenticated interaction lifecycle

The gate starts an interaction only for an authenticated conversational
request. It retains the user query across disclosure approvals and background
work, accumulates naturally available model latency/token metadata, and writes
the terminal record only when the final gate response is actually returned to
the owner. Repeated result reads do not duplicate the record. Replacement,
cancellation, or shutdown before delivery records a cancellation with no
delivered response.

Host-observed failure mapping uses bounded stage/category/code values for
model/provider failure, routing or source retrieval, authority or input-policy
blocking, verification/evaluation rejection, cancellation, and unknown or
ambiguous failure. Raw exception objects and messages are never copied into
the structured failure object. The existing metadata-only operational emitter
continues to receive no query or response fields.
