# Project 1A — shared capability foundation design

## Status and scope

Project 1A is inspection and design only. It begins at merge commit `252e5ac`, the latest accepted `v1.1-dev` after Project 0 PR #1, on branch `v1.1/project-1-foundation`. Stable `main` and tag `v1.0.0` remain at `83a1edf`. The source tree was clean; the existing dependency environment was inspected; the baseline build and publication audit passed before the branch was created.

The design preserves the governing invariant: **reasoning is replaceable; authority stays on the Mac**. It adopts the useful PersonalAI/Dax/hybrid/PydanticAI ideas—one capability registry, small typed envelopes, explicit decisions, and replaceable adapters—without importing a framework or moving policy into a model.

No runtime behavior, private deployment, provider pin, credential, account binding, existing source hash, legacy tree, or live service is changed by Project 1A. Only this new design artifact is added to the reviewed source manifest.

## Current post-Project-0 architecture

1. `gate/webui/guard.py`, `gate/webui/pipe.py`, and `gate/webui/bridge.mjs` restrict WebUI inputs and carry an authenticated owner request to the loopback OpenClaw gateway. Implicit WebUI tools, uploads, skills, project context, memory, and feature flags are denied on the gate path.
2. `gate/plugin/core.mjs` owns process-local gate sessions, retained risk state, tier exclusions, request revisions, background jobs, exact disclosure prompts, and one-use approval consumption. A changed request, session, exclusion, expiry, cancellation, or reuse invalidates a pending ticket.
3. `gate/plugin/local-agent.mjs` sends only the latest local request to an authenticated, model-pinned, loopback OpenClaw agent session. OpenClaw retains the local tool loop and its existing permissions; a bare MLX call is deliberately not substituted.
4. Signed non-local operations cross to `gate/worker.py`. `gate/src/authority.py` checks the HMAC envelope, exact operation shape, settings digest, session scope, expiry, approval kind, privacy floor, and a durable one-use nonce in SQLite. Model output cannot construct trusted Mac facts.
5. `gate/src/schema.py`, `dispatch.py`, and `risk_policy.py` validate the Gemini audit and compose fail-closed risk/routing state. `backends.py` pins provider/model identity, forbids fallback and tool calls, bounds context/output and reserves budget. `lifecycle.py` and `runpod.py` separately own private-80B leases, allocation intent, reconciliation, readiness, tunneling, and confirmed deletion; the independent janitor can clean up but cannot allocate or infer.
6. Local capabilities are OpenClaw tools. Gmail, Messages, Calendar, Markdown, and File Steward wrappers call fixed Unix-socket brokers. Browser Guard restricts the isolated profile and applies native allow-once approval to interaction. Web search/fetch are optional pinned OpenClaw providers. MCP is an isolated, three-tool, no-network container profile with path containment and a per-call Hugging Face disclosure approval.
7. `reliability/index.mjs` is the nearest existing shared capability layer. It validates proposals against captured schemas, performs at most one allowlisted safe repair before execution, never retries an action, normalizes bounded results, retains untrusted/provenance markers, supplies exact local utilities, performs a narrow exact-answer check, and writes content-minimized failure telemetry.
8. `scripts/release_operator.py` derives the isolated runtime configuration; `scripts/configure.py` applies narrow stopped-gateway amendments with a write-ahead rollback record. Source, rendered runtime, OpenClaw artifacts, and provider/runtime versions have distinct integrity pins.

The retained `router/` is historical deterministic privacy/escalation contract evidence plus a mock/dry-run escalation helper. It is not the production gate transport and will not be promoted into an authorization service.

## What already exists and what is missing

| Concern | Existing strength | Genuine Project 1 gap |
| --- | --- | --- |
| Capability identity and schemas | Stable tool names; TypeBox/JSON schemas; generated plugin tool lists; captured OpenClaw schemas | Registration, configured exposure, schema capture, repair policy, approval policy, provenance, output bounds, and rollback are separate inventories |
| Tool proposals | OpenClaw supplies a named call plus arguments; reliability validates before execution | No explicit model-independent proposal envelope binds reasoner, run/revision, capability-spec digest, and arguments while excluding authority fields |
| Authority | Gate exact tickets; HMAC worker requests; durable nonces; native Browser/File/MCP allow-once approval; broker-level least privilege | Outcomes are represented differently across boundaries and are not traceable as `ALLOW`, `ALLOW_ONCE`, `ASK`, or `DENY` |
| Egress | Gate tickets bind packet, destination, purpose, expiry, scope, and one use; MCP Hugging Face calls ask per call; hosted providers are pinned and budgeted | No shared destination/purpose/data-class decision. Optional web queries and future return of local results to another reasoner need the same boundary |
| Argument repair | One bounded, allowlisted repair; no repair of consequential tools, identifiers, paths, recipients, accounts, or authority | Repair declarations are duplicated in `registry.mjs` and `repair-registry.json`, and are not attached to the capability that actually runs |
| Results and provenance | `modelResult` creates bounded envelopes; most non-utility output is untrusted; source fixtures distinguish metadata from content | Result typing does not explicitly preserve `NOT_STARTED`, `COMPLETED`, or `COMPLETION_UNKNOWN`, sensitivity, authority/egress references, verifier outcome, and rollback receipt |
| Verification | Exact calculator, unit, date, and weekday facts are checked; a contradiction gets one fixed fallback and no more tools | Current public statuses are `verified`, `contradiction`, and `not_applicable`, not the required three-state contract; schema/path/postcondition checks are enforcement code rather than named verifier results |
| Source grounding | Tool descriptions, untrusted wrappers, normalized metadata names, and synthetic source-grounding fixtures are good and specific | Grounding requirements are prose/fixtures rather than capability-attached rule identifiers and evidence requirements |
| Reasoners | Local agent, hosted remote, private 80B, and local multimodal transports validate identities and bounded output | They do not implement one stable adapter contract. Local is an OpenClaw agent, while other adapters are final-answer-only Python methods |
| Audit | Reliability logs no prompts/arguments/results/IDs; gate network accounting and lifecycle state are bounded; shadow logs are metadata-only | Schemas and correlation semantics are fragmented. There is no single content-minimized event contract for proposal → decisions → execution → verification |
| Rollback | File Steward transactions/undo, configure rollback, installer rollback, GPU reconciliation, and preserved volumes are strong | Rollback support is not declared on the capability/result contract, so a reasoner cannot safely distinguish reversible, create-only, and irreversible/none |

Two observed mismatches demonstrate the need for derivation rather than another list: `messages_contact_history` and `calendar_search` are registered by their plugins but absent from both configured exposure and `reliability/schema-snapshot.json`. Project 1A does not silently enable, remove, or repair either mismatch.

The schema snapshot also includes disabled or non-exposed core capabilities such as memory tools. A schema snapshot is therefore useful compatibility evidence, but it is not a capability manifest or an authorization policy.

## Proposed shared flow

```text
ReasonerAdapter
  -> validated ToolProposal (never authority)
  -> runtime-derived CapabilitySpec
  -> AuthorityDecision
  -> EgressDecision (independent, when data may leave)
  -> existing OpenClaw hook / gate ticket / broker
  -> ToolResultEnvelope
  -> deterministic verifier: VERIFIED | REJECTED | UNKNOWN
  -> content-minimized AuditEvent
  -> normalized evidence back to the reasoner
```

Every transition is Mac-owned and schema-validated. A model may propose a capability and arguments; it may not populate, upgrade, or reinterpret either decision. Repository, retrieved, tool, and model content remain data.

## Shared contracts

The implementation should use versioned JSON-compatible contracts, validated in JavaScript with the already pinned Ajv/TypeBox stack and in Python with strict constructors/validators. Pydantic-like discipline is useful; a new Pydantic dependency is not justified.

### `CapabilitySpec`

Required fields:

- contract version, stable capability name, description, and canonical argument schema;
- implementation identity: OpenClaw source/plugin plus broker/provider boundary;
- effect: `READ`, `MUTATION`, or `CONTROL`, with network egress represented separately;
- input/output data classes and provenance/trust semantics;
- authority policy and allowed approval resolutions;
- remote-result eligibility by destination class, defaulting to none;
- maximum input, item, text, and whole-result bounds;
- allowed repair-rule identifiers;
- source-grounding rule identifiers and required evidence shape;
- supported verifier identifiers and whether verification is required or opportunistic;
- rollback mode: `NONE`, `CREATE_ONLY`, `UNDO_CAPABILITY`, or `LIFECYCLE_RECONCILIATION`, including the exact undo capability when one exists;
- runtime state: registered, configured, exposed to this run, and schema/policy digest.

`effect=MUTATION` does not imply approval, and `effect=READ` does not imply egress permission. Those are independent policy inputs.

### `ToolProposal`

The strict proposal contains a generated proposal ID, request/run identity, request revision, proposing reasoner ID, capability name, capability-spec digest, and arguments. It contains no approval, credential, destination grant, trusted provenance classification, filesystem root, account binding, or execution status. Extra fields are rejected.

The host revalidates the arguments against the capability's current schema after the one permitted repair. A schema/spec digest mismatch is `DENY`; it is never repaired or treated as authority to update the manifest.

### `AuthorityDecision`

The decision contains the outcome, capability, request/proposal digest, trusted scope, effect, safe reason codes, decision source, expiry when applicable, and an opaque approval reference held outside model-visible content.

- `ALLOW`: current Mac policy permits this exact local operation without an interactive approval.
- `ALLOW_ONCE`: an exact owner approval or purpose-bound ticket has been resolved and can be consumed once.
- `ASK`: execution is paused pending an exact owner decision.
- `DENY`: execution is prohibited or the necessary trusted context is absent.

Only the authenticated gate, native approval runtime, or another reviewed Mac authority adapter can issue a decision. Existing gate and native approval cryptography/consumption remain the enforcement mechanisms; the new contract records and composes their result rather than replacing them.

### `EgressDecision`

Egress is evaluated after authority and before any remote call. Its fields are:

- outcome using the same four semantics;
- request/proposal and capability-spec digests;
- exact data classes and provenance classes allowed to leave;
- exact destination class, service/provider, and model or endpoint identity;
- purpose such as `RISK_CLASSIFICATION`, `ANSWER_GENERATION`, `PUBLIC_SEARCH`, `PUBLIC_FETCH`, or `REMOTE_RESULT_RETURN`;
- trusted session/scope/revision binding, maximum bytes/items, expiry, and one-use status;
- content digest of the exact disclosure packet and safe reason codes;
- opaque approval reference, never the approval secret/token itself.

An approval for one destination, model, purpose, query, packet, or revision cannot authorize another. An action decision cannot authorize disclosure, and an egress decision cannot authorize a tool action. Missing destination, purpose, provenance, or exact packet binding is `DENY`.

The current gate maps cleanly to `ASK` followed by `ALLOW_ONCE`; its private-80B prompt-only session grant maps to narrowly scoped `ALLOW` only for the already enforced prompt-only packet. Hugging Face maps to per-call `ASK`/`ALLOW_ONCE`. Project 2 can add web-query privacy policy without changing the contract, and Project 3 can request `REMOTE_RESULT_RETURN` without inheriting tool authority.

### `ToolResultEnvelope`

The result contains capability/spec/proposal identity, safe status, execution state (`NOT_STARTED`, `COMPLETED`, or `COMPLETION_UNKNOWN`), bounded data or safe error, source and provenance, data sensitivity, untrusted flag, truncation, repair receipt, authority and egress decision references, verifier outcome, and an optional rollback receipt/reference.

Provider/broker exception text, credentials, private paths, approval tokens, and arbitrary debug fields are never copied into the envelope. `COMPLETION_UNKNOWN` on a mutation forbids automatic replay. Existing media blocks remain outside model-facing JSON, as they are today.

### `AuditEvent`

The event contains only schema version, timestamp, HMAC/hash correlation IDs, capability and phase, decision/result/verifier enums, safe reason codes, repair-rule IDs, data/destination classes, duration bucket, and whether rollback is available. It excludes prompts, arguments, outputs, personal identifiers, paths, email/message bodies, file contents, provider bodies, credentials, approval tokens, and opaque receipts.

Existing network accounting, lifecycle state, File Steward transactions, and configuration receipts keep their own purpose-built stores. The shared event is a trace spine, not a database migration or a copy of those records.

## Runtime-derived capability manifest

The manifest must be a projection of executable reality, not a manually edited master JSON file.

1. Sanctum-owned tool modules define each tool once through a small capability builder. The builder returns the OpenClaw `ToolDefinition` and the non-schema policy metadata together. The same `parameters` object used for registration becomes the manifest schema.
2. Browser, MCP, and gate policies export their classified action/destination metadata from the same policy functions that enforce them.
3. Core and optional third-party tools that Sanctum does not register use narrow reviewed adapters. Their runtime schema capture remains pinned compatibility evidence; the adapter adds only Sanctum policy metadata. A missing or changed schema fails closed and reports drift—it never refreshes itself.
4. Runtime configuration contributes whether the capability is enabled and allowlisted. Registration, configured enablement, run exposure, and enforcement availability remain separate booleans.
5. Build/test materializes a deterministic review artifact from those definitions and compares its digest with the runtime projection. Production may persist only the digest and content-free drift event; it must not write private bindings into source.

This replaces the duplicated repair inventory with one executable source. Human-readable repair documentation can be generated from it. It does not let plugin manifests, descriptions, model schemas, or repository text grant authority.

## Deterministic verifier contract

All verifiers return exactly:

- `VERIFIED`: deterministic evidence satisfies the named claim/contract;
- `REJECTED`: deterministic evidence contradicts or violates it;
- `UNKNOWN`: unsupported, missing, ambiguous, truncated, stale, or not applicable.

`UNKNOWN` is never success. It may mean verification was not required for ordinary prose; it must not be displayed or audited as verified.

Project 1B should first wrap, not broaden, the existing exact verifier:

- calculator and unit numeric facts;
- `date_math` date, weekday, and day-difference facts;
- JSON/schema validation of proposals, decisions, and envelopes.

Path containment and tool postconditions remain enforcement at their current brokers. They should become named verifier results only where the broker already returns sufficient deterministic evidence—for example a File Steward transaction/undo receipt or create-only Markdown receipt. No filesystem reread, speculative plugin family, model confidence, semantic prose checking, or general hallucination detector is proposed.

For the current one-tool exact-answer case, a match is `VERIFIED`, a parseable contradiction is `REJECTED`, and an answer outside the deliberately narrow grammar is `UNKNOWN`. `REJECTED` retains the current fixed local fallback and no-more-tools rule.

## Reasoner adapter boundary

`ReasonerAdapter` exposes stable identity/capability metadata plus `prepare`, `invoke`, and `normalize` operations over versioned `ReasonerRequest` and `ReasonerResult` contracts. Adapters may own endpoint/model identity, provider protocol, system instructions, context/output budgets, sampling, and tool-call syntax quirks. They may not own capability schemas, authority, egress, execution, provenance, normalization, verification, audit, or rollback.

`ReasonerResult` is a strict union of final answer, advisory escalation, or tool proposal. A proposal returns to the Mac coordinator; it never executes inside an adapter. Project 1 does not enable new proposal support on reasoning-only backends.

Compatibility mappings:

- `LOCAL_4B`: wraps the existing authenticated OpenClaw agent session. Its current OpenClaw tool loop remains in place while all calls continue through the shared hooks.
- `PRIVATE_80B`: wraps the existing lifecycle/backend and remains final-answer-only in Project 1. Tool parity is Project 3.
- hosted 235B, multimodal, and frontier: wrap the existing `Remote`/multimodal paths and remain reasoning-only with no fallback.
- future local reasoners: supply identity/protocol/context behavior, then use the same manifest and Mac coordinator.

The gate's risk routing remains separate from the reasoner adapter. An adapter cannot select itself, weaken high-stakes handling, authorize egress, or start infrastructure.

## Proposed implementation map for Project 1B

Add a small `foundation/` package containing versioned schemas, strict constructors/validators, the capability builder/registry, decision composition, egress policy, verifier protocol, and audit-event sanitizer. Keep it dependency-light and importable by reliability tests.

Change only where the contract provides a concrete benefit:

- `reliability/index.mjs`, `runtime.mjs`, `output.mjs`, `verification.mjs`, `telemetry.mjs`, `registry.mjs`, and `schemas.mjs`: consume the shared contracts; preserve one repair/no replay; emit tri-state verification and content-minimized events.
- `plugins/*/src/index.ts`: colocate schemas and policy metadata with each registered tool. Preserve names, schemas, brokers, and execution behavior.
- `plugins/browser-guard/src/index.ts` and `mcp-integration/guard/policy.js`: return explicit decisions while retaining native approval enforcement and existing allowlists.
- `gate/plugin/core.mjs` and `local-agent.mjs`: validate reasoner requests/results and map existing disclosure tickets to explicit decisions without changing ticket scope or local tool behavior.
- `gate/src/authority.py`, `backends.py`, and `worker.py`: add strict Python-side contract/adapters around current enforcement. Preserve HMAC, nonces, settings binding, provider identity, budgets, and lifecycle.
- `scripts/build.py`, `scripts/test.py`, `scripts/release_operator.py`, and `scripts/configure.py`: derive/review the manifest, verify runtime projection, and preserve current integration enablement. Do not silently resolve the two observed exposure mismatches.
- `docs/architecture.md`, `capabilities.md`, `privacy.md`, and `testing.md`: describe the accepted implementation after it passes; add a separate Project 1 acceptance record.
- `SOURCE-MANIFEST.json`: update only after reviewing intentional Project 1 source changes. Do not alter unrelated runtime pins.

The host brokers, media preparation, lifecycle, Runpod adapter, WebUI boundary, provider versions, and legacy router should not be refactored merely to fit the new names.

## Compatibility and migration strategy

1. Add and test contracts/manifest derivation with no runtime enforcement change.
2. Compare the derived projection against current registered/configured schemas and document mismatches. Unknown, duplicate, or changed capabilities fail closed in the test/enforcement stage; no automatic capture or hash refresh occurs.
3. Move reliability normalization/repair/verification behind the contracts while retaining byte/output caps and exact existing tool behavior.
4. Adapt existing native approval and gate disclosure results; do not replace their storage, signatures, nonce consumption, or UI.
5. Add reasoner wrappers last and prove request/response equivalence for every current tier. Do not enable private-80B tools or new routing.

No private state migration is needed. Existing sessions, approvals, nonces, File Steward transactions, GPU ownership, provider accounting, and configuration receipts retain their formats. Deployment into the private prefix is a later reviewed, stopped-gateway operation with a new source freeze and doctor; Project 1A performs none.

## Test strategy

Project 1B acceptance should add synthetic, credential-free tests for:

- manifest derivation from the same schemas used to register tools;
- registered/configured/exposed distinctions, including the two current mismatches;
- duplicate names, unknown tools, stale schemas, unknown repair/verifier/rollback IDs, and digest changes failing closed;
- proposal rejection of authority, egress, account, root, approval, and extra fields;
- all four authority outcomes and separation from all four egress outcomes;
- destination, purpose, scope, revision, expiry, content-digest, and one-use egress binding plus replay/cross-destination refusal;
- unchanged native Browser/File/MCP approvals and gate HMAC/nonce replay protection;
- unchanged one-repair/no-action-retry behavior and `COMPLETION_UNKNOWN` replay refusal;
- normalized result bounds, provenance/sensitivity propagation, truncation, and safe errors;
- verifier truth tables using only `VERIFIED`, `REJECTED`, and `UNKNOWN`, including current fallback behavior;
- audit allowlisted keys and absence of prompts, arguments, output, identifiers, paths, bodies, secrets, and approval material;
- reasoner adapter identity, context, tool-free remote behavior, no fallback, and equivalence with current local/private/hosted paths;
- File Steward/Markdown rollback declarations matching actual broker receipts;
- build-time and installed-runtime manifest projection agreement.

Run `make deps`, `make build`, `make test`, and `make audit`. For any later private-prefix setup or supported amendment, keep the gateway stopped and run `make doctor PREFIX=/absolute/private/prefix`. Live provider, UI, personal-source, macOS permission, and GPU checks remain separately authorized evidence, never implied by unit tests.

## Rollback strategy

Project 1A rollback is deletion of this design commit/branch only; it has no runtime state to undo.

Project 1B must remain source-revertible: keep current capability names and external broker protocols, avoid private-state schema migrations, and land the foundation as an additive compatibility layer before retiring duplicated internal representations. If equivalence or manifest projection fails, stop and retain the previous accepted source/runtime freeze. Do not refresh hashes, clear approval/nonces, rewrite transactions, kill uncertain compute, delete volumes, or modify the legacy tree to force rollback.

## Explicitly unchanged or deferred

- No automatic Source-First retrieval or `WEB_HELPFUL` / `WEB_REQUIRED` policy.
- No private-80B tool parity, Work Mode, autonomous coding, or multi-agent execution.
- No production vLLM Semantic Router, RouteLLM, SkyPilot, ToolHive, LiteLLM, or LangGraph migration.
- No vector store, embeddings, personal-document RAG, memory redesign, or local 235B deployment.
- No new email/message/calendar mutation, generic shell, deletion, arbitrary filesystem/network scope, provider fallback, standing broad disclosure, or model-granted permission.
- No provider/model/dependency repin, authorization-cryptography replacement, lifecycle redesign, production cutover, or legacy-tree edit.

PROJECT 1A DESIGN COMPLETE — SWITCH TO GPT-5.6 TERRA MEDIUM AND RUN PROJECT 1B
