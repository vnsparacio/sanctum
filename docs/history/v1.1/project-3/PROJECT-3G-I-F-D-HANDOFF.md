# Project 3G-I-F-D qualification harness remediation handoff

Date: 2026-09-16. Branch: `v1.1/project-3-private-lead-workmode`. Baseline: `8770218`. This step is offline only. Project 3G remains unaccepted pending a separately authorized final live qualification. No private amendment, gateway start, GPU allocation, model call, paid inference, push, PR, merge or Project 3H work occurred.

## Result

Gateway readiness is now an explicit fail-closed qualification precondition. The installed qualification harness will not run schema preflight, seed fixtures, create a Work Mode task or reach PRIVATE_LEAD until the owner-visible candidate gateway path is current, healthy, authenticated and serving the installed `/work` command.

The harness uses the existing supported `scripts/release_operator.py up` workflow for the exact candidate prefix. It does not start MLX, WebUI, PRIVATE_LEAD, PRIVATE_80B or any unrelated service. A stopped candidate is explicitly started by this workflow. A running candidate is accepted only when its process record matches the current installed identity and its loopback socket is healthy; a stale process is refused rather than adopted, replaced or retried.

## Exact readiness sequence

Before any fixture mutation, the harness now performs this sequence once:

1. Resolve the reviewed source and configured Python only from the installed candidate receipt and settings.
2. Invoke the supported candidate gateway `up` operation for the exact prefix.
3. Invoke candidate doctor and require source integrity, runtime pins and installed configuration integrity to pass.
4. Require `gateway_running=true`, `gateway_identity=match` and `gateway_health=pass`.
5. Send one bounded `/work help` command through the installed authenticated bridge with `operator.admin` scope.
6. Require the exact owner-visible Work Mode help response, proving authenticated connectivity and `/work` registration without starting a task.
7. Run the six-surface installed schema preflight.
8. Only after all checks pass, seed the unchanged qualification fixtures and permit graded task creation.

`--preflight-only` follows the same gateway restart, identity, health, authenticated bridge and `/work` checks before reporting schema identities. This supports the required future live order: amendment, gateway restart/readiness, offline schema preflight, PRIVATE_LEAD allocation, exact live schema probes, then one unchanged suite. The full suite repeats readiness immediately before fixture seeding and task creation.

## Installed gateway identity

The supported operator writes a versioned `sanctum-gateway-process/v1` record when it starts the candidate. The record binds the exact resolved Node executable and OpenClaw entrypoint, entrypoint hash, gateway port, installed receipt hash, installed gate freeze hash, installed OpenClaw configuration hash and reviewed source-manifest hash. Process ownership still requires the recorded PID and command identity. Candidate doctor reports current, stale or stopped identity separately from process health.

An already-running process with missing or changed identity fields is `stale` and cannot be silently adopted. The ordinary shutdown path can still identify and terminate its owned recorded process, so stronger admission checks do not weaken cleanup.

## Failure semantics and diagnostics

Readiness uses a fixed code allowlist: `GATEWAY_OPERATOR_UNAVAILABLE`, `GATEWAY_RESTART_FAILED`, `GATEWAY_DOCTOR_FAILED`, `GATEWAY_IDENTITY_MISMATCH`, `GATEWAY_UNHEALTHY`, `GATEWAY_BRIDGE_FAILED`, and `WORK_COMMAND_UNAVAILABLE`.

Any failure stops as `GATEWAY_READINESS:<code>` before fixtures or tasks. It is not classified as a PRIVATE_LEAD, semantic-schema, completion-policy, evaluator, authority, egress, Source-First or sandbox failure. There is no alternate command path and no readiness retry loop. The harness writes a private mode-0600 receipt containing only schema, blocked status, `HARNESS` classification, fixed reason/code and timestamp; it never persists bridge output, command output, paths, credentials, task text or arbitrary exception text.

## Regression coverage

Ten focused qualification tests cover stopped-gateway restart failure before fixtures, explicit supported restart, unhealthy gateway refusal, stale/wrong identity refusal, missing `/work`, authenticated bridge failure, successful readiness, readiness/schema/fixture ordering, content-minimized failure receipts, unchanged graded fixtures/expected outcomes and unchanged exact-schema probe surfaces/requests. A release-operator test covers exact process-record matching and stale-record rejection.

The fixture contract digest remains `e67ed7a5798f3fdae524ba5f570021f6a7b7874d54cb725b1feffeaa308aa831`; all ten ordinary cases, the integrated adversarial case, prompts, files and expected outcomes are unchanged. `probe_work_intent.py`, lifecycle/provider cleanup, Work Mode state-machine, model/profile, completion eligibility, semantic schemas, evaluator/reviewer, Source-First, authority, egress and sandbox code are unchanged.

The full packaged suite passes 270 tests: gate 81 JavaScript and 110 Python, reliability 31 JavaScript and 11 Python, MCP integration 8 JavaScript, root 18 Python, and six plugin packages with 11 tests. Canonical build passes. Audit scans 246 files with zero issues.

## Candidate state, packaging and rollback

The private candidate was not amended in this step. Candidate doctor passes source, runtime-pin and installed configuration integrity and reports the gateway stopped. PRIVATE_LEAD and PRIVATE_80B remain offline and manually stopped with zero active requests, zero leases and no pod identifier. No paid compute was allocated.

The existing stopped-gateway Work Mode amendment already packages `gate/qualify_work_mode.py`; a future authorized amendment will install this harness correction. `scripts/release_operator.py` remains the source-owned supported gateway manager referenced by the installed receipt and is bound by `SOURCE-MANIFEST.json`. Future qualification must install the exact committed source before exercising the new readiness path.

Source rollback is one revert of the F-D commit. No private-runtime rollback is required because the candidate was not changed. Preserve amendment `work-mode-1789588663994299000`, the accepted PRIVATE_80B rollback descriptor, disabled GPU autostart, persistent model storage and all prior qualification evidence.
