# Project 3G-I-D structured-output dialect remediation handoff

Date: 2026-09-16. Branch: `v1.1/project-3-private-lead-workmode`. This step is offline only. No private runtime amendment, GPU allocation, model call, live suite, push, PR or Project 3H work occurred. Project 3G remains unaccepted pending one separately authorized bounded live qualification.

## Three explicit validation layers

The implementation now keeps three separate layers:

1. `projectVllmGenerationSchema` creates a model-facing shape constraint for the pinned `vllm-0.20.1-outlines` dialect. This layer improves generation reliability and grants no authority.
2. `validateWorkIntent` applies the unchanged authoritative Mac semantic rules to the returned object. It still checks safe relative paths, length, NUL, enums, exact fields, visible capabilities and terminal values before binding.
3. `bindWorkIntent` adds immutable host-owned fields, after which the existing Project 1 `validateToolProposal` validation remains mandatory before `AuthorityDecision`.

The canonical `worktree_read` path pattern remains exactly:

```text
^(?!/)(?!.*(?:^|/)\.\.(?:/|$))(?!.*\u0000).+$
```

It was not weakened or changed to accommodate the decoder. Traversal, symlink, hard-link, Git-internals, mount and workspace containment also remain enforced later by the existing host capability path.

## Pinned-dialect projection

`gate/foundation/vllm-structured-output.mjs` is the single deterministic projection and compatibility boundary. It preserves the current supported constructs: object/string/integer types, properties, required fields, closed `additionalProperties`, `oneOf`, constants, enums, string and numeric bounds, and array item/bound constraints. Unknown schema keywords fail preflight rather than being silently discarded.

Only a `pattern` diagnosed as incompatible with the pinned backend is omitted from the generation schema. The explicit incompatible categories are look-around, backreferences, Unicode word boundaries and a prefix-context anchor. The current production surfaces produce exactly two omission classes:

- `worktree_read.arguments.path`: `REGEX_LOOKAROUND`;
- `ESCALATION.reason`: `REGEX_PREFIX_CONTEXT`.

Both patterns remain present in the authoritative semantic schema and remain mandatory in host validation. Differential tests show that a generation-valid absolute path, parent traversal, embedded parent traversal or NUL is rejected by the host before canonical binding, authority or execution. Oversize paths are rejected by both retained generation bounds and host validation. Valid relative paths still pass. Invalid lowercase escalation reasons are likewise rejected by the host even though their anchored pattern is absent from generation.

For the ordinary four-capability surface, the authoritative semantic digest remains `7d985ad0889b1954210f88ca3ac2d873144af9c782101bbc59bbfa06adfade3f`; its projected generation digest is `06649c94b07ec2cfc509c93b0473a76dc08128dac89e34a45b4f8267372c92f9`. Identical surfaces reproduce identical schemas and digests. Ordinary, research and test-only visibility produce different digests as required.

## Exact production-schema preflight and probe

`gate/preflight-work-intent.mjs` builds the manifest from the real registered Work Mode tools and checks every schema that the installed coordinator can send: all configured capabilities, ordinary coding, research, post-patch test-only and reviewer terminal-only. It records capability names, schema version, pinned dialect, projected digest, authoritative digest, branch count and each intentional omission. Known incompatible patterns or an unrecognized construct fail closed.

`manage.py resume --release PRIVATE_LEAD` now runs this installed offline preflight before clearing manual stop, so a known incompatible production schema cannot proceed toward allocation. `qualify_work_mode.py --preflight-only` exposes the same content-minimized identity before a run, and the full qualification refuses before fixture setup if preflight fails. Future qualification receipts bind the exact preflight version, dialect and digests.

`probe_work_intent.py` is the only staged live transport probe for this remediation. When separately authorized, it obtains the exact ordinary production request from the installed preflight, verifies its digest identity and submits that schema without fallback or retry. It reports only schema identities, result kind and bounded telemetry. A toy terminal schema is no longer used as evidence for production compatibility.

## Failure classification and fail-closed behavior

The backend verifies the transmitted generation-schema digest. HTTP 400 or 422 at the structured-decoding request stage becomes the bounded worker reason `structured_decoding_http_<status>`. The adapter maps only those codes to `structured_decoding_unavailable`; Work Mode records stage, safe HTTP status, backend category, schema version and schema digest, then stops `ENVIRONMENT_FAILURE / STRUCTURED_DECODING_UNAVAILABLE` with zero successful model calls.

Other transport failures remain `PRIVATE_LEAD_UNAVAILABLE`, and malformed returned objects retain the existing one-correction behavior. No raw provider body, prompt, schema body or model output is persisted. There is no unconstrained JSON, natural-language, native-tool, backend, model or retry fallback.

## Offline verification and packaging

Focused tests cover deterministic projection, current-schema compatibility, unchanged host path validation, absolute/traversal/NUL/length cases, safe paths, terminal branches, all capability branches, visibility-sensitive digests, exact backend schema transmission, production preflight, unsupported-construct refusal, distinct structured-decoding classification, no retry/fallback, mandatory host validation, mandatory canonical validation, and zero authority/execution after semantic rejection.

`make deps` completed with the pinned dependency sets and reported the same two moderate npm advisories; no dependency was repinned. The full packaged suite passed 246 tests: gate 68 JavaScript and 100 Python, reliability 31 JavaScript and 11 Python, MCP integration 8 JavaScript, root 17 Python, and six plugin packages with 11 tests. Canonical build passed, and audit scanned 240 files with zero issues. The unchanged installed candidate passed doctor for source, runtime-pin and configuration integrity. PRIVATE_LEAD and PRIVATE_80B remained offline and manually stopped with zero active requests, zero leases and no pod; no Work Mode container was running.

The Work Mode amendment explicitly packages `foundation/vllm-structured-output.mjs`, `preflight-work-intent.mjs`, `probe_work_intent.py`, the changed qualification tool and all modified runtime files. Source-manifest hashes cover every new and changed source artifact. Full dependency, test, build, audit and candidate doctor results are recorded in the commit that contains this handoff.

Source rollback is one revert of the Project 3G-I-D commit. No private rollback is needed because this step did not amend the candidate. A future installation must use the stopped-gateway reversible Work Mode amendment and preserve the existing 80B rollback descriptor and private state.
