# Project 3G-I-F-B host-owned completion eligibility handoff

Date: 2026-09-16. Branch: `v1.1/project-3-private-lead-workmode`. Baseline: `af89e1f`. This step is offline only. Project 3G remains unaccepted pending one separately authorized bounded live qualification. No private amendment, deployment, GPU allocation, model call, push, PR, merge or Project 3H work occurred.

## Result

Work Mode now exposes `FINAL` only when the Mac-owned mutable-worktree policy says a completion claim is structurally eligible for fresh evaluation. The policy is fixed by production integration as `MUTABLE_WORKTREE_V1`; it cannot come from task prose, repository content, model output, reviewer text or a model-selected field.

The pure predicate uses normalized host facts with fixed precedence:

```text
active planning decision
AND no host stop
AND execution state known
AND current task/workspace/turn-bound inspection evidence valid
AND diff bytes > 0
AND status bytes > 0
AND no post-patch test obligation
```

Its reason codes are `HOST_STOP_ACTIVE`, `EXECUTION_UNCERTAIN`, `WORKSPACE_EVIDENCE_UNAVAILABLE`, `POST_PATCH_TEST_REQUIRED`, `NO_COMPLETABLE_DIFF`, `NO_WORKTREE_CHANGES`, and `ELIGIBLE_FOR_FRESH_EVALUATION`. Invalid or failed workspace inspection stops `ENVIRONMENT_FAILURE / WORKSPACE_STATE_UNAVAILABLE`; it is never interpreted as an empty worktree.

This is a host state-machine validity correction, not prompt tuning. No list/read/patch count, fixture condition, prior test pass or model-authored mutation prerequisite was added. The production contract still does not support clean-worktree success and does not force pointless mutation.

## Semantic surface and freshness

`workIntentSchema`, `workIntentRequest` and `validateWorkIntent` require explicit terminal visibility. Omitting it fails closed. Ineligible task surfaces contain valid tools plus `ESCALATION`, with no `FINAL` branch in either the authoritative union or projected vLLM schema. Eligible task surfaces additionally contain `FINAL`. The post-patch surface remains test-only plus `ESCALATION`.

A manually supplied hidden `FINAL` is rejected as `TERMINAL_NOT_VISIBLE` before evaluator, reviewer, canonical translation, authority or execution. It shares the existing one-correction counter with all other covered invalid semantic results. Mixed invalid classes consume the same allowance; a second consecutive invalid result retains `SAFETY_POLICY_BLOCK / REPEATED_INVALID_PROPOSAL`. A fully valid result clears correction state. An eligible `FINAL` whose evaluator fails is an acceptance failure, not an invalid proposal, and receives no correction retry.

`FINAL` and `ESCALATION` now use the immutable inference context. Before dispatch, the coordinator checks cancellation and budgets, exact scope/workspace/request/turn/manifest/generation binding, one-use state, captured terminal visibility and a fresh normalized workspace snapshot matching the captured digest. It never reinterprets an old result under newer eligibility. A valid escalation executes no tool, grants no permission and maps to the content-minimized host result `BLOCKED / MODEL_ESCALATION`; arbitrary model reason text is not persisted as the stop reason.

System text lists only choices in the generated surface. Structured request state carries the host policy, eligibility boolean/reason, terminal kinds, decision state, post-patch obligation, generation and snapshot digest. Schema and host validation remain independent.

## Execution facts, evaluator and reviewer

Patch/test facts now update immediately after a known execution and before result-egress branching. A successful patch creates the test obligation and advances coordinator generation even when its result is withheld. An explicit successful or failed test clears the existing obligation and updates test state even when result details are withheld. A successful explicit test still runs the fresh evaluator and bounded reviewer without another model call. A failed test does not permanently hide `FINAL`; current workspace facts and a fresh evaluator remain authoritative. `COMPLETION_UNKNOWN` records unresolved state and stops before result egress.

The installed evaluator predicate is unchanged: fresh before diff, configured sandbox checks, fresh after diff and status, all checks successful, non-empty status, stable before/after diff and non-empty diff. Both eligible `FINAL` and the successful explicit-test path still invoke it fresh. Cancellation and host budgets are rechecked before evaluation, after evaluation, after review and before `COMPLETE`.

Reviewer behavior remains unchanged: only after evaluator pass, bounded diff/check facts, separate exact egress, no tools or authority, and at most one invocation. `ACCEPT`, `REJECT` and `REVISE` retain their prior meaning. `REVISE` invalidates candidate/evaluator state, returns to planning, recomputes eligibility and retains `reviewUsed`; no second review was added.

Source-First is unchanged. Research remains visible where configured; its proposal still receives host binding, canonical validation and Mac authority before local query derivation/minimization. `QUERY_APPROVAL_REQUIRED` still becomes host `NEEDS_APPROVAL / SOURCE_QUERY_APPROVAL_REQUIRED` without a model-authored approval terminal.

## Content-minimized evidence

The ledger now accepts a strictly allowlisted `SEMANTIC_SURFACE` event before each task-loop call, including correction calls, and a paired result-stage event. It records only phase/decision enums, policy and eligibility codes, schema/snapshot digests, visible host capability and terminal names, booleans, counters, test/evaluator/reviewer states, selected result kind and validation code. Tests prove unknown fields are excluded, private-looking escalation text and task prose do not enter the ledger, and the hash chain still verifies.

## Production preflight and future probe surfaces

The offline preflight validates every distinct production surface and records both digests:

| Surface | Branches | Generation digest | Authoritative digest |
|---|---:|---|---|
| All eligible | 7 | `b9a3cb4c2710199bbd838f3f503bf82d31c0c21cf2cbb71a2d869fa57827ff2a` | `183e7113a06cd1454dd6a6096653d5800e9d735ddf6d607500a0d06596fa7858` |
| Ordinary ineligible | 5 | `703a39854d8cd5280869881234d06dfe3de584e4db4d97da00e4652786c4422f` | `fc17add66f479ad1dc7b09896703c04643f31fd533dcae31f5179f902ece508b` |
| Ordinary eligible | 6 | `06649c94b07ec2cfc509c93b0473a76dc08128dac89e34a45b4f8267372c92f9` | `7d985ad0889b1954210f88ca3ac2d873144af9c782101bbc59bbfa06adfade3f` |
| Research ineligible | 5 | `0fd0061f1db71be77ab9987c31b6e086ad2dc1d151c5d8c93a9f0d3995dbb201` | `d325b8b13f195b54a50596acddf3e3a6caa188e5f08b5d7252c24d36ea79291b` |
| Research eligible | 6 | `f20ec775b10fd743e8d3977e4ab5067f90cc516a7dd85df0f3d53b7c0a8b0549` | `1a5b4cacd52eaddf54fa177dc021e7a16682b0ace805f45f9bfdd18e06f2e94a` |
| Test-only ineligible | 2 | `cc49f8cd2b3d0cde6bb74f5824794d5e31953a190dfb70734730a0b872851d50` | `483dcd8cd9bc33d8810677d7e960461da492e460a801545b6936593cb3a9ad5c` |
| Reviewer | 1 | `38fbf1c7c40b5ca81c55f478cf953f1af538a72b6586a2cc259fd5d9e90d9a29` | `38fbf1c7c40b5ca81c55f478cf953f1af538a72b6586a2cc259fd5d9e90d9a29` |

The ordinary/research eligible digests are unchanged because they reproduce the former full terminal unions. Ineligible and test-only digests are new. Known generation-only regex omissions remain the reviewed path look-around and escalation prefix-context cases; authoritative validation retains both patterns. The reviewer remains a separate one-branch `FINAL` schema with no task tools or escalation.

`probe_work_intent.py` now accepts an explicit surface from `ordinaryIneligible`, `ordinaryEligible`, `researchIneligible`, `researchEligible`, `testOnlyIneligible`, or `reviewer` and obtains that exact schema from installed production preflight. It still has no toy schema, fallback or retry. No live probe was run in this step. Qualification preflight now binds all six task/reviewer surfaces instead of one ordinary digest; fixture goals and expected outcomes are unchanged.

## Offline verification and packaging

The focused Work Mode suite contains 36 tests and covers the accepted synthetic matrix: clean/non-empty evidence, diff/status absence, inspection failure, post-patch gating, egress-independent accounting, unknown completion, failed tests, stale test/evaluator state, schema and validator visibility, correction sharing, snapshot/generation/cancellation/budget freshness, automatic evaluation, reviewer bounds, Source-First approval, malicious data, explicit inability, telemetry privacy/hash chaining, preflight surfaces and exact backend schema transport. Existing structured-intent, authority, egress, Source-First and sandbox tests remain intact.

The final packaged suite passed 259 tests: gate 81 JavaScript and 100 Python, reliability 31 JavaScript and 11 Python, MCP integration 8 JavaScript, root 17 Python, and six plugin packages with 11 tests. `make deps` reused the inspected Python 3.12 venv and retained the existing two moderate npm advisories without repinning. Canonical build passed. Audit scanned 243 files with zero issues.

The stopped-gateway amendment was checked against every changed runtime artifact. It packages all seven: `foundation/work-intent.mjs`, `plugin/work-mode.mjs`, `plugin/work-command.mjs`, `plugin/work-ledger.mjs`, `preflight-work-intent.mjs`, `probe_work_intent.py`, and `qualify_work_mode.py`. Their reviewed bytes match `SOURCE-MANIFEST.json`; the update is an explicit source freeze for this intentional implementation, not a drift refresh. Tests and both F-A/F-B documents are also bound by the source manifest.

No private amendment occurred, so candidate doctor was not run: the installed candidate correctly remains on the prior reviewed source, and running doctor against a deliberately newer uninstalled source freeze would not qualify this implementation. A future installation must use the stopped-gateway reversible amendment and then run doctor.

## Rollback and next boundary

Source rollback is one revert of the single local F-B commit; do not partially revert schema visibility, coordinator validation, ledger telemetry or production preflight. There is no private-runtime rollback for this offline step. If later authorized, install the exact committed source through `upgrade_work_mode.py`, preserve the accepted model/runtime, 80B rollback descriptor, disabled GPU autostart and persistent storage, run doctor, then perform only one bounded live qualification. Project 3G remains unaccepted until that evidence is reviewed.
