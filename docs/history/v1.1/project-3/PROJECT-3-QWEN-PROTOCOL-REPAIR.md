# Project 3 Qwen protocol repair — offline review candidate

Date: 2026-09-16. Project 3 remains experimental and unaccepted.

## Scope and identities

Work continued on `v1.1/project-3-private-lead-workmode`, from clean source HEAD
`e168f864eb5ed74d3437102323cdf79804505f06`, eleven local commits ahead of its
tracking branch. The canonical source, remote and private-prefix locations are
recorded in [the baseline](../V1.1-LIVE-BASELINE.md). No branch change, commit, push,
PR, installation, gateway start, provider action or model call was performed.

`ffe539f3d097ff2e652acc842438590a3ba117ea` is the **historically reported installed
source**, not a newly verified running identity. Private runtime files, receipts,
credentials and personal sources were not read. The legacy tree was untouched.
The supplied diagnosis and implementation prompt were authorized for offline
execution after their review. Older handoff instructions remain historical.

The checkpoint, quantization, vLLM version, thinking flag, sampling, 1024-token
proposal output limit, task budgets, authoritative schemas and 11-case fixtures
are unchanged. Native tools and a two-stage interface were not implemented.

## Boundary map and first rejecting predicates

| Boundary | Actual production entry | Input/output and rejection |
| --- | --- | --- |
| State and surface | `plugin/work-mode.mjs`, `foundation/decision-surface.mjs` | Captured workspace facts determine terminal visibility under MUTABLE_WORKTREE_V1. Manifest exposure/order and existing four-capability selection determine tools. Builder returns ordered views, authoritative schema, generation request and identities. |
| Task rendering | `createWorkMode.run` | Owner task, legal choices, state, latest bounded observations and active correction are serialized into the existing request. More than 64000 characters now stops as MODEL_CONTEXT_LIMIT instead of replacing the entire task with an omission marker. |
| Generic request | `foundation/contracts.mjs:createReasonerAdapter` | Exact sanctum-capability/v1 request fields, bounded messages and request size; no change to acceptance. |
| Signed transport | `plugin/core.mjs:createExecutor` → `worker.py` → `src/authority.py:authorize` | HMAC envelope, expiry, settings digest, signed purpose and one-use nonce checked before dispatch. |
| Lifecycle | `worker.execute` → `PrivateLeadLifecycle.propose` | Existing lease/readiness/cleanup. Untouched. Offline fixture substitutes lifecycle and endpoint bytes only. |
| Backend request | `src/backends.py:PrivateLeadBackend.propose` | Exact Work Intent version/dialect/shape and generation schema digest checked. Same schema transmitted in response_format; model profile unchanged. |
| SSE assembly | `src/protocol_stream.py:completion_stream` | Bounded UTF-8 SSE lines, one choice, content deltas only, explicit stop and DONE required. Tool/function calls, refusal, extra choices, unfinished streams and malformed events stop at STREAM before effects. Reasoning content is ignored, not retained. |
| JSON parse | `protocol_stream.parse_result` | strict_json rejects syntax, duplicate keys and nonfinite numbers. Fixed JSON_PARSE diagnostic; malformed proposal gets the existing shared correction allowance. |
| Backend result | `protocol_stream.parse_result` | Object with recognized FINAL, ESCALATION or TOOL_PROPOSAL kind. Recognition alone is not semantic acceptance. |
| Adapter/generic result | `private-lead.mjs` → `contracts.mjs:validateReasonerResult` | Exact top-level keys. ESCALATION reason must satisfy `^[A-Z][A-Z0-9_:-]{0,79}$`. FINAL text must be nonempty, at most 32768 JS code units and contain no NUL. Semantic proposal must have capability identifier and object arguments. No defaulting, trimming or terminal conversion. |
| Work Intent | `work-intent.mjs:validateWorkIntent` | Captured terminal/capability visibility, forbidden host fields, required and unknown arguments, types, enums, regex and numeric/string limits. Full semantic constraints retained. |
| Freshness and binding | `inferenceContextCurrent`, fresh workspace capture, `bindWorkIntent` | One-use captured context checked; terminal/mutation freshness checked. Host constructs opaque canonical bindings. |
| Canonical validation | `contracts.mjs:validateToolProposal` + `argumentsMatchSchema` | Canonical Project 1 shape, manifest identity and arguments checked before authority. |
| Authority/effect/egress/completion | Existing coordinator and Work Mode integration | Existing separate authority/egress, one-effect execution, evaluator and bounded reviewer. Unchanged. |

There are two routes into the existing `reasoner_result_shape` catch:
(1) PRIVATE_LEAD adapter maps worker `private_lead_result_schema`, and
(2) generic reasoner validation throws REASONER_RESULT_SHAPE in lowercase.
The coordinator maps both to REASONER_RESULT_SCHEMA. It previously discarded
which structural predicate failed. New diagnostics are attached before that
collapse. A later Work Intent rejection has its own semantic code.

Reviewer requests use the shared builder with no capabilities and FINAL only.
FINAL.text then undergoes the existing separate verdict/findings JSON validation
in `work-command.mjs`; this review policy is not strengthened by this repair.
The one-reviewer REVISE limitation and diff/status fingerprint limitations remain.

## Reproduced defects and bounded repairs

1. **Schema identity:** ordinary/research preflight used registration order while
   coordinator used manifest order. Regression captured the actual coordinator
   request and failed equality. Both now use decisionSurface; Python probes consume
   that same preflight artifact. Ordering remains production manifest order, not a
   benchmark-tuned order. `allEligible` remains a five-capability coverage superset,
   not a claim that ordinary production exposes all five simultaneously.
2. **Streaming acceptance:** synthetic production streams lacking DONE, or containing
   native tool calls beside valid JSON, were accepted. Both now fail before results
   can reach host execution. Multiple choices/refusals are also rejected.
3. **Parser observability:** malformed JSON escaped as JSONDecodeError; generic
   validation lost its field/predicate. Fixed typed facts now reach adapter,
   coordinator, correction and the private ledger. Invalid JSON shares one correction;
   incomplete/uncertain transport remains an environment stop, without another call.
4. **Task delivery:** six large but individually bounded observations could erase
   the entire task request through an omission marker. The regression previously
   reached the next model invocation without its goal. It now stops at the existing
   context boundary before inference. No prompt strategy or budget increase.

These are synthetic reproductions, not recovered historical outputs. The failing
field in the original 22 responses remains unknown. Why Qwen chose ESCALATION is
also unresolved. This repair makes no claim that useful action selection improved.

## Differential contract matrix

G = generation JSON Schema (AJV); S = authoritative semantic JSON Schema (AJV);
R = generic reasoner validator; W = Work Intent validator. These are **host tests**,
not the vLLM grammar compiler or token-level decoding.

| Synthetic case | G | S | R | W | Explanation |
| --- | --- | --- | --- | --- | --- |
| Valid ESCALATION, lengths 1 and 80 | pass | pass | pass | pass | Exact current host contract. |
| Empty/lowercase/space/newline/non-ASCII/NUL reason or length 81 | pass | fail | fail | fail | Whole reason pattern omitted by generation projection; preserved, documented gap. |
| Missing/wrong-type reason, extra top-level property | fail | fail | fail | fail | Structural rejection. |
| Valid FINAL / empty FINAL / overlength ASCII FINAL | agree | agree | agree | agree | Visibility separately enforced. |
| FINAL containing NUL | pass | pass | fail | pass | Existing stricter generic text contract; unchanged. |
| FINAL with 20000 astral Unicode characters | pass | pass | fail | fail | JSON Schema counts Unicode characters; host uses JS UTF-16 code units; unchanged. |
| Valid example of every tool | pass | pass | pass | pass | Then canonical binding and Project 1 validation pass. |
| Read path violating omitted regex | pass | fail | pass | fail | Generic validator checks proposal structure, semantic validator checks arguments. |
| Hidden FINAL/capability or injected host bindings | context-dependent | fail | may pass shape | fail | No authority/effect is reached. |
| Separate reviewer FINAL containing verdict/findings | pass | pass | pass | pass | Existing reviewer parser remains additional validation. |

Remaining disagreements are identified, not silently repaired by weakening host
acceptance. Restoring generation regex constraints requires evidence from the
exact compiler. No enum or arbitrary reason normalization was added.

## Shared surface identities

Ordered capability arrays are tested against captured production requests.
The following digests describe source artifacts, not a newly installed runtime.

| Surface | Generation SHA-256 | Semantic SHA-256 |
| --- | --- | --- |
| allEligible | `1b9500698d4cbc3d06b6ed5b5edd899a1db8ca1ae738189bc342ade3a192abde` | `d5f49f9065d87f48ee6dc5f484c4fcbece53b8e054751a4b1764888f2ae26e1f` |
| ordinaryIneligible | `765dbcdf0942bb330a66dfd34cbfc1271a290caf9ed2f0d39eac63f8f73d2787` | `16f87595681c155cae7c1a9f0690eaa675b471034caef90cae8a5e8d068c5249` |
| ordinaryEligible | `a8c1fabb092975639ba0cf9b86090a64ecc7ae75537ce10c4543a4e0aa19f125` | `e78c1de040c84c63d676d96f35bb59c494becd47088fb70cc7255e236b6d9ad2` |
| researchIneligible | `f709f64220b6018158d01f86b0485ed8a913422333bdb1a74258b6a7159743fc` | `ae2d5e326de4b996b07b82e3cc898559ea431e27e748db5e210243818b24ca25` |
| researchEligible | `58c0d6ba79cc6f1b4d0dced4676cdd812c9b10d82b6b95d1b297b1cd8fec9f16` | `995e81aa91b8152100ed696ed1b11dab6ade8f3b88131caec68f185b092ba911` |
| testOnlyIneligible | `cc49f8cd2b3d0cde6bb74f5824794d5e31953a190dfb70734730a0b872851d50` | `483dcd8cd9bc33d8810677d7e960461da492e460a801545b6936593cb3a9ad5c` |
| reviewer | `38fbf1c7c40b5ca81c55f478cf953f1af538a72b6586a2cc259fd5d9e90d9a29` | `38fbf1c7c40b5ca81c55f478cf953f1af538a72b6586a2cc259fd5d9e90d9a29` |

## Structural diagnostic contract

`sanctum-protocol-diagnostic/v1` contains fixed stage and validator version,
recognized result kind, allowlisted field, failed keyword, received type, bounded
string length, pattern-match boolean, missing-field flag, unknown-field count,
stream/finish status, parse status and normalization status. Unobserved facts use
UNKNOWN or null. Counts/lengths saturate at 65537. Failed pattern checks report false;
other predicates do not pretend that the pattern was evaluated.

The host adds actual generation and semantic identities to PROTOCOL_DIAGNOSTIC
ledger events. Diagnostic keys and string values are re-allowlisted at the adapter
and ledger boundaries; arbitrary fields, enum values and error strings disappear.
Schema paths, patches, raw reasons, prompts and source contents are never diagnostics.
No new raw-content hashes or transformation fingerprints were needed: outputs are
not normalized. Existing captured-state identity mechanisms remain unchanged.

Tests inject synthetic secrets in values, keys, stage/enum names and error strings,
verify that they do not survive, and verify every ledger hash-chain link. Worker
parser failures and generic/semantic failures share the existing one-correction
counter. Second invalid output stops; valid output clears stale correction state.

## Decoder and rendered request evidence

The checked-in launch script pins vLLM 0.20.1, Qwen revision
`98915d837c4e7c87ac8296d02e89de19b3207e6d`, qwen3 reasoning parser and qwen3_coder
tool parser. It does not explicitly select a structured-output backend. The source
dialect label is not evidence of which backend actually served historical requests.
The preparation script pins vLLM, not a complete resolved transitive compiler lock.

The source projection tests an isolated field pattern and removes every pattern
starting with `^`. That implementation fact is confirmed. Whether the anchored
reason pattern compiles correctly *inside the full schema* is **NOT RUN**: vLLM,
outlines and outlines_core are absent from the existing repository environment;
no compatible compiler installation was found in the local uv cache. No packages
were upgraded/downloaded for this check. Current GPU backend identity, resolved
compiler versions and pinned installed template bytes were **NOT OBSERVED**.

Tests intercept actual streaming HTTP request construction, compare every transmitted
schema and its order, and decode the nested request/message JSON to confirm goal,
observation and correction survive. Nesting is present but no data loss is reproduced
within the bounds. The profile reserves 4096 output tokens while proposals transmit
1024. This is conservative input headroom, not permission to expand outputs. Both
remain unchanged. Exact tokenizer/rendered-chat token counts are **NOT RUN** without
the pinned tokenizer/template. Byte/character bounds and output limit are tested;
these do not establish that every permitted input fits the actual model token window.

## Validation and source freeze

Existing `.venv` was inspected before dependency bootstrap: Python 3.12, Pillow
12.3.0, pypdf 6.18.0, imageio-ffmpeg 0.6.0. It had no pip module; `uv pip list`
confirmed the installed pins. `npm_config_offline=true UV_OFFLINE=true make deps`
passed from cache with the existing environment. No lockfile/runtime-pin change.

Initial regression run: Node 1 pass / 2 failures; Python 1 pass / 2 failures /
1 error. These exposed surface order, missing diagnostics, absent DONE acceptance,
ignored tool calls, and the raw JSON parse exception. The context-specific test was
added and reproduced separately before the context guard change.

Verification commands:

- `npm_config_offline=true UV_OFFLINE=true make deps`: PASS, cached pinned dependencies.
- `make build`: PASS, six plugins and captured manifest/runtime-pin validation.
- `node --test gate/tests/protocol-repair.test.mjs`: PASS, 10 tests including signed-worker microprobes.
- `.venv/bin/python -B -m unittest discover -s gate/tests -p test_protocol_repair.py`: PASS, 10 tests including packaging closure.
- `make test`: PASS, 290 tests: 91 gate Node, 120 gate Python, 31 reliability Node, 11 reliability Python, 8 MCP, 18 release/setup and 11 plugin tests; zero failures/skips.
- `make audit`: PASS, 255 files scanned, zero issues.
- `git diff --check`: PASS.
- `scripts.release_operator.verify()` against source and existing cached runtime pins: PASS.
- Exact GPU grammar/compiler, pinned tokenizer, actual decoder/template identity,
  live inference, installed amendment/doctor, actual APFS/OCI task and full live
  qualification: NOT RUN for the scope/availability reasons above.

The first complete offline run passed all 289 tests. Worker-boundary diagnostic
re-allowlisting subsequently added one regression; the final complete run passed all
290 tests. No failed intermediate regression was relabeled as a successful run.

This change explicitly creates a **source review freeze** in SOURCE-MANIFEST.json
for only the explained modified/new artifacts. Unchanged entries are checked against
their prior values; runtime pins remain separately unchanged. This is not an install
freeze, acceptance or independent review. No doctor against the old private install
is used to validate these new source bytes.

## Packaging and rollback

`scripts/upgrade_work_mode.py` includes the new decision-surface and diagnostic
modules, Python stream helper and microprobe module along with all changed existing
runtime files. Packaging-closure regression checks their relative JS imports.
The normal amendment must still verify source/installed receipts, stopped gateway,
empty managed ownership and independent janitor, then back up/copy the coherent unit.
It may build/pull the runner image: it was inspected and **not invoked** here.

Rollback remains the existing stopped-gateway amendment transaction, restoring all
previous files and removing newly introduced files recorded as absent. Private
receipts and persistent volumes remain intact. No live amendment or rollback was run.

Changed implementation: contracts, decision-surface, protocol-diagnostics,
private-lead adapter, coordinator, reviewer surface integration, ledger, preflight,
backend stream path, worker error forwarding, microprobe runner, amendment packaging.
Changed verification: protocol Node/Python tests, signed-worker fixture, one obsolete
registration-order assertion, default test command list and this report.

## Future microprobe plan — NOT AUTHORIZED TO RUN

The executable decision runner is `gate/protocol-microprobe.mjs:runProtocolMicroprobes`.
It accepts a supplied reasoner and manifest; it does not load credentials, allocate,
start a gateway or expose a live CLI. It has a 180-second diagnostic deadline, at
most two reasoner calls per probe and six calls total, and stops on the first failed
semantic choice or contract. Synthetic actions/evaluator facts never count as real
agentic task completion. A host seed adds one coordinator turn but **zero model calls**.

Run its offline signed-path regression from source:

```sh
node --test --test-name-pattern='signed worker microprobes|microprobe runner' gate/tests/protocol-repair.test.mjs
```

This exercises production createExecutor HMAC signing, Python authorize/nonce checks,
worker dispatch, actual streaming backend, PRIVATE_LEAD adapter, coordinator,
semantic validation, canonical binding and authority. Lifecycle, endpoint bytes,
workspace facts and effects are synthetic. The fixture cannot provision a provider.

Proposed paid decisions, in this fixed order:

1. Read `index.js` for an unambiguous initial inspection. A valid but irrelevant
   action or escalation fails semantic grading.
2. Select `worktree_command` with operation `test` after a **host-seeded synthetic**
   patch. This is not a Qwen-created edit or actual successful test.
3. Accept a valid inability report for a missing instrument capability through
   terminal visibility/freshness and MODEL_ESCALATION; repeated-invalid blocking fails.

Before spending: independent source review, supported coherent installation, exact
installed source/schema identities, gateway doctor/health/authenticated Work Mode
readiness without inference, validated janitor and zero existing managed ownership.
Reconfirm current provider rate and obtain separate authorization for **one allocation,
900 seconds total allocation lifetime, at most USD 0.75 compute at no more than
USD 3/hour**, plus any separately itemized provider billing minimums/storage charges.
If the quote cannot meet that ceiling, do not allocate. Preserve existing volumes.
No second allocation or full 11-case suite.

**Readiness inference is a concrete remaining live-harness gate:** existing lifecycle
readiness calls health_check(smoke=True) and can repeat it inside its readiness loop.
The decision runner's six-call counter does not count those calls. Therefore it must
not be connected to the live lifecycle as-is and represented as a six-call experiment.
A separately reviewed installed caller must enforce a global **six inference attempts
including readiness**: reserve at most one 16-token readiness smoke, leaving at most
five proposal attempts (1024 output tokens each). Three first attempts plus at most
two corrections fit; if another correction would exceed the global cap, stop and
record incomplete. An unsuccessful smoke stops the allocation rather than polling
more inference. Read-only model-list/HTTP/gateway checks consume no model calls.
No uncounted characterization, preflight, warmup or benchmark model calls are allowed.
This caller/budget integration is deliberately not smuggled into an offline protocol
repair or a modified serving profile; it is required before any live authorization.

The outer allocation supervisor must bound cold readiness and cleanup within the
900 seconds (proposed 600 seconds readiness, 180 seconds probes, 120 seconds cleanup),
stop on contract/readiness/deadline/cost/cancellation failure, and retain independent
janitor supervision until provider deletion and no leases/active requests are proven.
Unconfirmed deletion remains a failure and preserves ownership records/supervision.
Record every attempt, including failures and unused budget; no sample-until-green loop.

After successful probes, the next separately authorized experiment is one unseen,
small read → actual patch → explicit test trajectory with real host evaluator/reviewer.
Protocol probes do not satisfy that milestone or the unchanged 11/11 acceptance bar.

## Status

OFFLINE REPAIR READY FOR INDEPENDENT REVIEW — NO LIVE RUN PERFORMED

This status is limited to the source repair. Exact compiler verification and the
readiness-inclusive inference-budget integration remain prerequisites to a future
live diagnostic. It does not authorize deployment, spending, promotion or a PR.
