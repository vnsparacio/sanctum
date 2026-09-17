# Project 3G-I-F-C bounded live qualification handoff

Date: 2026-09-16. Branch: `v1.1/project-3-private-lead-workmode`. Installed source commit: `976378c35065fa98514461f24706466788b78c0c`. Project 3G remains **not accepted**. The exact changed-surface probes passed, but the unchanged 11-case suite did not begin because its first installed `/work start` command reached a stopped candidate gateway and the harness returned `installed_command_failed`. The instruction forbidding a second suite was honored.

## Installation and offline gates

The candidate gateway was stopped before the supported reversible Work Mode amendment. Amendment `work-mode-1789588663994299000` records source commit `976378c35065fa98514461f24706466788b78c0c`. Every packaged file matched the reviewed rendered source, including the seven changed runtime artifacts from the F-B handoff. The installed candidate contains `MUTABLE_WORKTREE_V1`, the `SEMANTIC_SURFACE` ledger event, the six-surface probe tooling and the unchanged qualification fixtures.

Candidate doctor passed source, runtime-pin and configuration integrity after installation. The exact installed production preflight passed for all six task and reviewer surfaces:

| Surface | Branches | Projected generation digest | Authoritative digest |
|---|---:|---|---|
| Ordinary ineligible | 5 | `703a39854d8cd5280869881234d06dfe3de584e4db4d97da00e4652786c4422f` | `fc17add66f479ad1dc7b09896703c04643f31fd533dcae31f5179f902ece508b` |
| Ordinary eligible | 6 | `06649c94b07ec2cfc509c93b0473a76dc08128dac89e34a45b4f8267372c92f9` | `7d985ad0889b1954210f88ca3ac2d873144af9c782101bbc59bbfa06adfade3f` |
| Research ineligible | 5 | `0fd0061f1db71be77ab9987c31b6e086ad2dc1d151c5d8c93a9f0d3995dbb201` | `d325b8b13f195b54a50596acddf3e3a6caa188e5f08b5d7252c24d36ea79291b` |
| Research eligible | 6 | `f20ec775b10fd743e8d3977e4ab5067f90cc516a7dd85df0f3d53b7c0a8b0549` | `1a5b4cacd52eaddf54fa177dc021e7a16682b0ace805f45f9bfdd18e06f2e94a` |
| Test-only ineligible | 2 | `cc49f8cd2b3d0cde6bb74f5824794d5e31953a190dfb70734730a0b872851d50` | `483dcd8cd9bc33d8810677d7e960461da492e460a801545b6936593cb3a9ad5c` |
| Reviewer | 1 | `38fbf1c7c40b5ca81c55f478cf953f1af538a72b6586a2cc259fd5d9e90d9a29` | `38fbf1c7c40b5ca81c55f478cf953f1af538a72b6586a2cc259fd5d9e90d9a29` |

Before allocation, the working tree and 242-entry source manifest were clean at the expected commit. All 259 packaged tests passed, canonical build passed, and audit scanned 243 files with zero issues. Both GPU releases were offline and manually stopped with zero active requests and leases, no provider-managed pod existed, the independent janitor was loaded, GPU autostart was disabled, the accepted 80B rollback descriptor matched source and installed state, and no Work Mode container was running. Provider preflight reported accepted secure capacity at `$2.09/hour`.

## Exact live surface probes

One allocation was accepted after bounded capacity wait. PRIVATE_LEAD reached accepted readiness on the pinned `nvidia/Qwen3.5-122B-A10B-NVFP4` revision and unchanged vLLM `0.20.1` runtime. Readiness took 316.718 seconds from allocation.

The four installed exact-schema probes all passed without retry or fallback:

| Surface | Result kind | Prompt / completion tokens | Model seconds | Schema result |
|---|---|---:|---:|---|
| Ordinary ineligible | ESCALATION | 801 / 16 | 2.915 | accepted; FINAL absent |
| Test-only ineligible | ESCALATION | 542 / 16 | 0.438 | accepted; test-only command plus ESCALATION |
| Ordinary eligible | FINAL | 832 / 10 | 1.016 | accepted; FINAL and ESCALATION present |
| Research ineligible | ESCALATION | 802 / 16 | 0.463 | accepted; FINAL absent |

The model choices in these synthetic probes are not task-success evidence. The content-minimized probe record is `probes-1789589664.jsonl` under the external private prefix. No structured-decoding rejection, `ARGUMENT_SCHEMA`, or `REVISION_MISMATCH` occurred in the four probes.

## Suite failure and classification

After the probes passed, the unchanged installed qualification command was invoked exactly once. Its first bridge request failed before `/work start` could create a task because the candidate gateway remained stopped after the required amendment. The harness returned `REFUSED: installed_command_failed`. No qualification case started, no suite task ID or task ledger was created, no suite model call occurred, and no official 11-case qualification receipt was emitted.

This is failure class `HARNESS`, type **B: harness defect**. It is not a completion-policy, terminal-visibility, model-semantic, evaluator, reviewer, Source-First, authority, egress or sandbox result because none of those task-loop stages ran. The operator should have restarted the stopped candidate gateway and verified `/work` before invoking the suite. The instruction said not to run another suite after a failure, so the gateway was not started and the suite was not invoked again.

Consequently there is no 11/11 table, no live task-loop `SEMANTIC_SURFACE` progression, no live post-patch accounting, no live evaluator/reviewer path, no live impossible/unsafe outcome, and no live Source-First approval outcome from this attempt. The probes establish transport compatibility for the changed schemas only. Project 3G acceptance criteria were not met.

## Timing, cost and private evidence

The single allocation `86v61s3bn6wrv6` existed for 375.949 seconds. At `$2.09/hour`, elapsed-rate allocation cost was approximately `$0.21826`. Readiness consumed 316.718 seconds. The four probes made four model calls totaling 4.833 model seconds, 2,977 prompt tokens and 58 completion tokens; their elapsed-rate inference estimate is approximately `$0.00281`. The suite made zero model calls.

The content-minimized private attempt receipt is `qualification-attempt-1789589758198752000.json` under the external private prefix, with SHA-256 `d4d11364d5a989e3a76c36ed6b51544ecfde797cc4ece01f2722261e2344cbf8`. It records the harness classification, zero started cases, probe count, allocation timing/cost and cleanup facts without task prose, repository content, prompts, patches, command output or secrets.

## Cleanup and rollback

Cleanup completed immediately after the harness refusal. Provider absence was confirmed at `1789589709.6811829`; `PRIVATE_LEAD` is `OFFLINE`, manually stopped, with zero active requests, zero leases, no pod identifier and no uncertain allocation. `PRIVATE_80B` is also offline and manually stopped with zero active requests and leases. Provider listing reports zero managed pods, Docker reports no Work Mode container, and no new Work Mode task exists. Persistent model storage was preserved and GPU autostart remains disabled. Final candidate doctor again passes source, runtime-pin and configuration integrity, with the candidate gateway stopped.

The accepted PRIVATE_80B rollback descriptor remains unchanged at digest `4186d96c97f8e306950190c26b298f526d0259b3859cb58b193206182e14ba95`, status `accepted-rollback`, revision `ac9dc5b939ba948ab378b8638cfcce4ac4d5642b`. No rollback weights were downloaded. Candidate source rollback remains the complete reversible amendment `work-mode-1789588663994299000`; do not partially roll back schema visibility, coordinator validation or telemetry.

Project 3G remains unaccepted. Do not run another paid suite, push, open a PR, merge, promote PRIVATE_LEAD, remove the rollback path or begin Project 3H without a new owner decision.
