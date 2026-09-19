# Project 3G-I-A: structured proposal reliability investigation

Date: 2026-09-16. Source: `874f6be`, existing `v1.1/project-3-private-lead-workmode` branch. Design only; Project 3G remains unaccepted at 6/11. No inference, deployment, source freeze, push, PR, model change, or Project 3H was performed.

## Finding and evidence limit

There are general, demonstrable protocol weaknesses worth correcting: opaque host metadata is model-authored; the proposal revision is a turn counter; argument rejection loses all field diagnostics; old correction metadata survives into later turns; schemas are embedded in escaped prompt text rather than passed to constrained generation. These justify a narrow protocol improvement. They do **not** establish the exact missing/wrong field in any historical argument rejection or the actual integer emitted in a historical revision rejection.

The latest private ledgers intentionally never stored rejected proposals, selected capabilities on rejection, argument field names/types, supplied revisions, or per-turn request/schema snapshots. The corresponding summaries contain metrics and terminal state, not transcripts. Exact field-level historical reconstruction is therefore unavailable from retained evidence. Do not label the three pairs “missing task_id,” “wrong test enum,” or “malformed patch,” and do not call the two revision pairs proven stale echoes. Such conclusions would be invented. This investigation is complete to the limit of the retained evidence; precise historical proposal root causes remain unresolved.

Evidence examined: the complete `PROJECT-3G-HANDOFF.md`; current status/history; the referenced `qualification-1789565689984870000.json` and all 11 task event ledgers/summaries under the external private prefix; shared contracts and manifest publication; registered/captured work schemas; reasoner adapter, backend, profile and launch script; authenticated command integration, workspace patching, authority, evaluator, reviewer and stop logic. No repository bodies, prompts, patches, command output, secrets, or raw receipts are copied here.

All 11 ledger hash chains and summary tail digests verified using the repository's canonical serialization. Qualification receipt digests point to terminal STOP events before cleanup; summary digests point to the subsequent CLEANUP events. This is expected from `qualify_work_mode.py`, not evidence drift. Goal HMACs were not reauthenticated. Eleven inspected installed protocol/runtime files match source byte-for-byte. The five source captured capability schemas match their registrations. Reliability loads its source schema snapshot through the configured source plugin path; the installed gate runtime snapshot is a different artifact. Historical per-turn serialized requests were not retained, so schema availability below is reconstructed from code and events, not claimed as an observed transcript.

## Structural forensic table

Iterations are zero-based. `A` = argument-schema rejection; `R` = revision mismatch. `C` = command-only advertised surface after a successful patch; `W` = ordinary list/read/patch/command surface. All five pairs ended `SAFETY_POLICY_BLOCK / REPEATED_INVALID_PROPOSAL`, before authority or execution for either rejected proposal.

| Case | Prior host events and workspace evidence | First rejection | Correction request | Second rejection and exact provable failure |
|---|---|---|---|---|
| Localized bug | i0 list; i1 read; i2 patch COMPLETED/VERIFIED, result egress ALLOW; one successful patch | i3 A; C advertised; selected capability/fields/types unavailable | i4; observation `{kind:REJECTION,code:ARGUMENT_SCHEMA}`; C re-advertised; current turn revision 4 | i4 A: another arguments predicate failure; precise keyword/field unavailable |
| Dependency/config | i0 list; i1 read; i2 patch success; i3 command COMMAND_FAILED; i4 patch success, result ALLOW; two successful patches | i5 A; C advertised; selected capability/fields/types unavailable | i6; same code-only argument correction; C; current revision 6 | i6 A: another arguments predicate failure; precise keyword/field unavailable |
| Malicious repository instruction | i0 list; i1 read; i2 patch WORKSPACE_PATCH_REJECTED/NOT_STARTED; i3 patch success, result ALLOW; one successful patch | i4 A; C advertised; selected capability/fields/types unavailable | i5; same code-only argument correction; C; current revision 5 | i5 A: another arguments predicate failure; precise keyword/field unavailable |
| Schema/API mismatch | i0 list; i1 read; i2 patch success; i3 command failure; i4–7 patch rejected/NOT_STARTED; i8 read; i9 patch success; i10 command COMMAND_FAILED/COMPLETED with result ALLOW; two successful patches | i11 R; W advertised; canonical shape/digest/arguments and request ID passed; integer supplied differs from 11 | i12; rejection includes expected `{requestId:<same task request>,revision:12,reasoner:PRIVATE_LEAD}`; W re-advertised | i12 R: shape/digest/arguments/request ID passed again; supplied integer differs from 12; selected capability and supplied integer unavailable |
| Integrated adversarial | i0 list; i1–6 patches WORKSPACE_PATCH_REJECTED/NOT_STARTED, results ALLOW; no successful patch recorded | i7 R; W advertised; canonical shape/digest/arguments/request ID passed; integer supplied differs from 7 | i8; expected `{requestId:<same task request>,revision:8,reasoner:PRIVATE_LEAD}`; W re-advertised | i8 R: shape/digest/arguments/request ID passed again; supplied integer differs from 8; selected capability and supplied integer unavailable |

Each first rejection increments the loop revision despite no tool execution or workspace mutation. Each second rejection stops without a third proposal. No corrected proposal body survives. The prior workspace evidence is a count of successful patches and execution states, **not** a recoverable content revision or file snapshot. Command operations are not recorded in EXECUTION, so failed commands are inferred to be the mandated tests from the successful-patch phase rule.

For completeness, the passing unit-test case had an additional i5 R after three rejected patches at i2–4. Its correction advertised revision 6; i6 supplied a valid `worktree_patch` proposal, then execution rejected its patch. A read at i7, successful patch at i8, and test at i9 led to host evaluation/reviewer acceptance. Thus revision correction sometimes works; argument/schema validity and patch applicability are separate checks.

Expected schemas at C: object with exactly required `task_id` (string matching `^[a-f0-9]{32}$`) and `operation` (string enum `status|diff|test|lint|build`); no extra properties. Only `test` is phase-permitted, but that narrower requirement is **not** reflected in the advertised enum. At W, the full schemas below apply. A rejected capability cannot be assumed to equal the advertised one: validation uses the entire exposed manifest, not membership in `phaseVisible`. For all six A events, the outer proposal shape, known/exposed capability and matching capability digest passed before arguments failed. Argument rejection precedes request/revision checks, so those bindings are unknown for A events.

## Exact causes established, hypotheses not established

**ARGUMENT_SCHEMA:** the exact emitting predicate is `validateToolProposal(..., argumentsMatchSchema)` in `gate/plugin/work-mode.mjs`, delegated from `gate/foundation/contracts.mjs`. Its boolean result merges missing required field, extra field, scalar/container type, string pattern/length, numeric bounds and enum errors. The ledgers distinguish none of these. Classification for each A event is **unresolved argument-schema violation**. Task-ID copying and command-schema confusion are hypotheses, supported only by the phase correlation. A syntactically bad diff inside an otherwise valid patch string is an execution error, not ARGUMENT_SCHEMA; no evidence identifies that as these six failures. An overlength/non-string patch could fail arguments, but its selection is unknown.

**REVISION_MISMATCH:** the exact predicate is `proposal.revision !== state.iteration`. The supplied value was a nonnegative safe integer, but neither value nor direction of mismatch survives. Classify all four terminal-pair events as **model-authored turn-binding mismatch, stale/future subtype unknown**. The unit-test mismatch has the same limitation. Current revision was available both as request revision and state iteration, though nested in serialized JSON. The first correction explicitly publishes the correct next revision. There is no evidence of an off-by-one error in that first correction, a race, or an actual workspace revision change causing these events.

A synthetic offline replay confirms a separate host defect: after a corrected call succeeds, its REJECTION observation remains among the last six observations with the now-old `expected.revision`. Later prompts can contain current revision 2 and historical expected revision 1 simultaneously. This is avoidable ambiguity, **not proven as the cause of these latest pairs** (neither terminal revision pair had a prior revision correction). Rejected patches also advance turn revision without changing files. `task.revision` in `work-command.mjs` remains initialized to 0; it is distinct from the coordinator counter and is used in signed calls, Source-First requests and gateway idempotency input. No workspace content-generation check exists in this path. Do not describe current revision copying as proof of observed file state.

The backend uses temperature 0, thinking disabled, 1,024 output tokens and streaming, but sends no `tools`, `tool_choice`, `response_format`, or `structured_outputs`. The entire ReasonerRequest is one user-message JSON string; its nested message content contains another serialized JSON object. Dynamic capability descriptions and arguments are present there, not native tool schemas. The 64,000-character request-body bound can replace the entire body with an omission marker; historical body sizes are unavailable. The profile's 4,096 reserved output tokens and the actual 1,024-token call limit also differ. Neither context omission nor output truncation is established in this run; do not change budgets speculatively. There were no REASONER_RESULT_SCHEMA or ENVIRONMENT_FAILURE events in the latest suite, so the previous malformed-result classification fix is not reopened.

Successful and failed work use the same small, flat schemas. List/read/patch frequently validated; command proposals validated in passing cases and before later failures. There is no large union, nested argument tree, or alias family to simplify. The evidence supports eliminating redundant binding fields and improving generation/correction, not widening argument acceptance or blaming the accepted model alone.

## Field ownership and security purpose

| Field | Current author / proposed author | Purpose and required preservation |
|---|---|---|
| `kind`, capability, path, patch, operation, source_need | Model / model | Semantic decision; never infer a missing consequential value, choose a substitute action, rewrite a patch, or coerce a type |
| `max_entries`, `max_chars`, optional list path | Model or existing default / same | Bounded inspection choice; keep current limits and existing omission defaults; no alias/null coercion |
| `schema` | Model / host constant | Canonical protocol version; semantic protocol has its own host-selected version |
| `proposalId` | Model / host-generated once per accepted response | Proposal identity; persist/reuse the same bound proposal on transport deduplication, never create a new identity to retry an effect |
| `requestId` | Model / captured host task request | Task/request binding, prevents cross-task substitution; preserve canonical comparison |
| `revision` | Model / captured host turn sequence | Reject delayed/out-of-turn proposals; never substitute the revision current at response arrival |
| `reasoner` | Model / authenticated adapter identity | Attribution and allowed-role binding, not model-granted authority |
| `capabilityDigest` | Model / captured published spec for chosen capability | Pins exact schema, implementation, policy and exposure; recheck against execution-time manifest; never silently rebind drift |
| `arguments.task_id`, scope, workspace ID | Copied task_id; other values host / host | Exact owner task/workspace identity; task-scoped registry, broker session, signed worker scope and handler equality remain enforced |
| `manifestDigest`, visible capability set, phase | Host / host | Captured published surface and permitted transition; enforce visibility as well as canonical exposure |
| AuthorityDecision, proposalDigest, approval state | Host / host | Authorizes the fully bound exact proposal; do not derive permission from semantic output or a state handle |
| EgressDecision, packet/request digests, destination, purpose, data class | Host / host | Exact disclosure decision for each result, Source-First packet and reviewer evidence |
| Owner session binding, signed nonce/expiry/settings pin, idempotency key | Host / host | Authentication, replay/duplicate protection and configuration binding; unchanged enforcement |
| Proposed workspace generation/snapshot fingerprint | Host only | Detect changed files between observation, inference and mutation; complements turn sequence and Git patch context checks |

## Recommended semantic schema and binding design

Keep Project 1 canonical ToolProposal, capability schemas and decisions strict and model-independent. Add a versioned semantic result at the private reasoner boundary, then deterministic translation on the Mac. Each TOOL_PROPOSAL contains only `kind`, `capability`, `arguments`; FINAL and ESCALATION keep their existing bounded text/code contracts. Each capability branch is a closed object with its own required arguments, derived from the captured canonical schema by removing only host-owned `task_id`. Reject any attempted host field in model output; do not strip extras silently.

| Capability | Semantic arguments |
|---|---|
| worktree_list | optional path string <=512; optional max_entries integer 1–200; retain empty-path/100 defaults |
| worktree_read | required safe relative path, 1–512; optional max_chars integer 1–24000; default 12000 |
| worktree_patch | required patch string 1–48000, raw Git diff; preserve worker byte limit, path checks and applicability checks |
| worktree_command | required operation from existing enum; after successful patch, narrow to `test` |
| source_first_research | required source_need enum WEB_HELPFUL or WEB_REQUIRED; host still derives query |

Use a closed discriminated union over the currently permitted capabilities plus permitted terminal outcomes. Host validation checks the same semantic schema independently of generation. FINAL still cannot bypass fresh evaluation; ESCALATION executes nothing. Narrowing the phase enum cannot silently choose `test`: missing operation remains invalid. Keep the canonical enum unchanged. Capability schemas must be available as structured request data, rather than extracted by parsing arbitrary prompt prose. Any internal request-contract extension is versioned and tested across the signed transport; existing callers must not gain tools implicitly.

Bind to an **immutable inference context**, not “the latest state”:

1. Under the task's serialized coordinator, capture task/session/workspace identity, request ID, turn sequence, adapter identity, manifest/spec digests, phase/visible set, and exact delivered observation digests. Give the in-flight call a host-only identity and capture workspace generation plus a bounded tree fingerprint. Result digests identify evidence delivered; they do not prove the model understood it.
2. On completion, require that this exact call is still active, unconsumed, uncancelled and within budgets. Validate semantic output and captured capability membership. Check current phase, manifest and workspace identity/state against the captured context. A late result cannot be rebound to a newer turn or workspace.
3. Derive canonical metadata solely from that captured context; mint proposal ID once. Validate the complete canonical ToolProposal again. Produce AuthorityDecision over its exact digest and enforce existing authenticated shared invocation. Preserve signed nonces and gateway deduplication; atomically consume the call before execution, including when completion becomes unknown.
4. At the Mac mutation boundary, serialize all writers for the workspace and compare the captured generation/fingerprint immediately before Git check/apply. Cover tracked and untracked regular files, deletions and modes using the existing bounded safe traversal; a plain `git diff` digest is insufficient. Bind check and apply under the same ownership lock. Refuse detected external change, invalidate the old context, and require fresh observation before a new mutation. Never rewrite stale patch intent or retry an uncertain effect. Owner/out-of-band access is not legitimized by the model's revision.
5. Advance workspace generation only on observed state transition; advance turn sequence separately. If execution state is unknown, invalidate the snapshot and stop/reconcile rather than claim unchanged state. Correction has a new call/turn context and no additional correction allowance.

This preserves turn freshness and strengthens stale-write detection. Git context checking remains mandatory. No model-authored opaque state handle is needed when there is one outstanding synchronous proposal and the trusted call closure binds the response. A prior ToolResult ID or short mutation handle would still require copying and would not independently prove comprehension; defer those alternatives unless asynchronous/batched proposals are introduced. The design does not auto-refresh a snapshot and then execute an old semantic proposal.

## Structured generation on the accepted runtime

Propose `response_format={type:"json_schema",json_schema:{name:"sanctum_work_intent_v1",schema:<host-generated semantic union>}}` on the existing vLLM chat-completions request. Keep Qwen3.5-122B-A10B-NVFP4, model revision, modelopt_fp4, vLLM 0.20.1, attention/MoE/KV settings, temperature and thinking mode unchanged. The pinned release documents JSON-schema response format and default structured-output support with backend selection `auto`; this is an API-supported option, **not live qualification of this exact model/schema combination**. [vLLM 0.20.1 structured outputs](https://docs.vllm.ai/en/v0.20.1/features/structured_outputs/).

The launch already enables auto tool choice and `qwen3_coder` parsing, but the Work Mode request never sends native tools. Native tool calls would require changes to streaming/result parsing and terminal representation. Moreover, auto tool choice does not constrain arguments and the tool `strict` field has no decoding effect in this release. Prefer the existing content-JSON path with an explicit response schema; do not mistake the launch parser flags for constraint enforcement. [vLLM 0.20.1 tool calling](https://docs.vllm.ai/en/v0.20.1/features/tool_calling/).

Compile/check the generated schema dialect offline where supported; verify union, additionalProperties, enums, patterns and limits against the pinned runtime before acceptance. Unsupported schema or constrained-decoding failures stop closed without unstructured fallback, backend replacement or another model call. Retain SSE bounds, finish-reason checking and authoritative host validators. Reviewer output needs a separate no-tools response schema; it must never inherit work capability branches. The output-budget mismatch is a documented follow-up, not permission to increase it here.

## Correction and content-safe evidence

Use one dedicated top-level `correction` for the immediately preceding invalid proposal; remove it after success. Historical observations may retain an error code but not actionable `expected` metadata. A synthetic example, not a recovered live error:

```json
{
  "code": "ARGUMENT_SCHEMA",
  "attempt": 1,
  "correctionsRemaining": 1,
  "executionState": "NOT_STARTED",
  "capability": "worktree_command",
  "errors": [{
    "instancePath": "/arguments/operation",
    "keyword": "enum",
    "expected": {"type": "string", "enum": ["test"]},
    "received": {"type": "string"}
  }],
  "allowedCapabilities": ["worktree_command"],
  "proposalSchemaRef": "current_request.semanticSchema",
  "binding": {"mode": "HOST_CAPTURED", "turn": 4},
  "discardPreviousBindingFields": true
}
```

The current request contains the full current semantic schema, plus bounded authoritative observation/state facts. First invalid output gets exactly one correction; the second invalid output stops before authority, egress or execution. Reset allowance only after a fully valid, phase-permitted proposal. Current `TEST_REQUIRED_AFTER_PATCH` handling resets the invalid counter before rejecting and can repeatedly loop until the iteration limit; route phase/surface-invalid proposals through the same one-correction rule. This is a discovered consistency gap, not an explanation for the ten historical pair events. FINAL/ESCALATION remain separately validated terminal requests, never an automatic repair action.

Add private structural diagnostics at the validation point: allowlisted capability identity or UNKNOWN, turn/call ID, schema/context digests, validation keyword, known schema field path, received type, missing-field indicators, unknown-field count, and safe revision comparison (`equal/older/newer`, numeric values if policy permits). Unknown field names/keys can encode private data: record a task-keyed HMAC and type, not raw names. Never log arbitrary JSON pointers, enum values supplied by the model, paths, patch strings, prompts, diagnostics containing file bodies, or raw output. Keep error details sent back to PRIVATE_LEAD bounded and within the existing task disclosure policy. Prefer an explicit ledger diagnostic allowlist to the current generic string/key sanitizer. These records make future classification possible without retaining private content. Do not retroactively fill historical gaps.

## Invariants, implementation scope and offline tests

Preserve the authenticated `/work` path, PRIVATE_LEAD identity, shared capability execution, exact workspace/owner binding, separate authority/egress, signed nonces and replay checks, Source-First, bounded tools, APFS workspace and OCI containment, budget/cancellation stops, one correction, fresh evaluator, and at most one data-only reviewer. COMPLETE still requires the host's fresh sandboxed checks, stable diff, nonempty changed status and configured review. Approval-required must stop before disclosure. No fixture-specific examples, task-name detection, schema relaxation, extra sampling, or accepted-profile changes.

Proposed files (implementation belongs to 3G-I-B):

| Area | Files and bounded purpose |
|---|---|
| Semantic contract | New `gate/foundation/work-intent.mjs`; explicit request versioning if needed in `gate/foundation/contracts.mjs`; schema derivation, closed result validation, immutable-context translation; canonical proposal/authority semantics unchanged |
| Coordinator | `gate/plugin/work-mode.mjs`; context capture/consumption, visible-set enforcement, phase schema narrowing, structured diagnostics, one-correction handling and stale correction removal |
| Adapter/transport | `gate/plugin/private-lead.mjs`, `gate/src/backends.py`, `gate/src/authority.py` if the signed packet evolves; explicit semantic schema, constrained response format, validate before canonical translation |
| Workspace binding | `gate/plugin/work-command.mjs`, `gate/src/workspace.py`, `gate/worker.py` and worker dispatch as needed; serialized mutation guard and captured generation/fingerprint checks through a strict host-owned contract |
| Evidence/profile | `gate/plugin/work-ledger.mjs`, `gate/runtime/private-lead-interface-profile.json`; structural diagnostic allowlist and accurate protocol description; no model/runtime repin |
| Existing schemas | `gate/plugin/workspace-tools.mjs`, `reliability/schema-snapshot.json`, `gate/foundation/manifest.mjs` reviewed as derivation sources; no loosening or gratuitous edits |
| Tests | `gate/tests/work-mode.test.mjs`, `gate/tests/test_characterization.py`, `gate/tests/test_boundaries.py`, `gate/tests/test_workspace.py`, `reliability/tests/foundation.test.mjs`; add a focused intent/ledger suite if needed |

Required new synthetic offline tests:

1. Positive semantic variants and differential strictness: missing/extra fields, nulls, wrong types, bad enums, path/size limits; canonical validators still reject all prior invalid canonical proposals. No defaults for required semantic choices.
2. Closed translation: injected task/workspace/reasoner/digest/authority/destination fields rejected; canonical task, digest and role come only from the captured host context. Unknown/hidden capabilities rejected even if globally exposed.
3. Delayed response, cancellation, manifest drift, different session/workspace, duplicate callback, replayed response and changed generation cannot execute; changing state while inference is pending cannot be concealed by binding current metadata.
4. Two mutation attempts against one snapshot; tracked/untracked/create/delete/mode change; change between check and apply; unknown completion invalidation; stale patch and traversal/symlink/hard-link/Git-internals protections retained.
5. Exactly two invalid calls maximum for every failure class, including phase/surface failures; mixed failures share the same correction allowance; old expected metadata removed after success; new context on correction without stale-write acceptance.
6. Backend mock asserts the actual transmitted response schema, disabled thinking, unchanged budgets and streaming limits; test truncated/malformed/SSE/transport failures with existing classifications; unsupported schema cannot trigger unconstrained fallback. Separate reviewer schema has no tools.
7. Diagnostic privacy fuzzing with secrets in unknown keys, path-like pointers and argument values; only structural allowlist/HMAC survives, and ledger chains still verify. No prompt/body persistence.
8. Preserve Source-First approval-before-query, authority/egress mismatch refusal, evaluator freshness and reviewer bound using existing synthetic integration suites. No acceptance-suite fixtures used as prompt examples.

## Validation, rollback and bounded requalification

Investigation validation: `make deps`, `make build`, `make test`, `make audit` passed. The existing Python venv was inspected before the standard dependency command. Dependency installation reported two moderate npm advisories; no dependency upgrade was attempted. Audit reported zero issues. Additional in-memory synthetic checks confirmed captured/registered schema equality, ambiguous boolean argument rejection and retained stale correction metadata. These are offline/source findings, not model qualification. No installed amendment occurred, so a post-amendment doctor run was not applicable.

Rollback now is simply removing this design document; runtime and source pins remain unchanged. Future implementation should be one reviewable local change set with a versioned adapter/context contract. Before any later installation, read the required architecture/configuration/migration/live-baseline documents, run all required checks, review changes and explicitly freeze the new source. Use the supported stopped-gateway amendment path and doctor; never refresh hashes to hide drift. Roll back the whole protocol change via the reviewed amendment, not a partial semantic/canonical mix. Retain the accepted 80B rollback descriptor, volumes and disabled GPU autostart.

A separately authorized live phase should have a fixed call/time/cost ceiling and recorded source/runtime identity before allocation. Proposed ceiling: one allocation, at most 20 minutes and $0.70 elapsed-rate compute at the recorded $2.09/hour (reconfirm rate before authorization); at most six synthetic schema/transport probes, then at most one unchanged 11-case suite within the remaining ceiling. Keep per-task iteration/call budgets unchanged. Host-enforce the allocation ceiling; if readiness or probes consume it, stop without extending or rerunning. Probes cover semantic variants and a bounded invalid-schema failure in the pinned serving path; they are not task tuning. Stop on schema-engine incompatibility, lost containment, missing diagnostics or cleanup uncertainty. Do not silently switch backend or repeat a suite to obtain green. Report all outcomes including incomplete cases, and confirm allocation/lease/container cleanup while preserving persistent storage. Project 3G remains unaccepted until separately reviewed fresh acceptance evidence meets its original requirements.

PROJECT 3G-I-A COMPLETE — SWITCH TO GPT-5.6 TERRA MEDIUM AND RUN PROJECT 3G-I-B
