# Project 3D: PRIVATE_LEAD capability integration and Work Mode handoff

> Phase 11 audit note: this is source scaffolding, not an accepted or deployed
> Work Mode. See `PROJECT-3-PHASE-11-AUDIT.md`.

## Scope and result

Project 3D adds source scaffolding for the staged, data-only `PRIVATE_LEAD` proposal path and a Mac-owned Work Mode coordinator. The accepted Project 3C profile remains unchanged: compact prompt, host-selected capability view capped at four, direct single-action proposals, host task state, one schema correction, and no model-authored plans.

The implementation does not promote `PRIVATE_LEAD` into normal Gate routing, change the accepted 80B release, enable GPU autostart, or make a production/candidate ownership switch.

## Capability and egress boundary

`gate/plugin/private-lead.mjs` turns a bounded reasoner request into one signed `private_lead_propose` operation. `gate/src/authority.py`, `gate/worker.py`, `gate/src/lifecycle.py`, and `gate/src/backends.py` bind it to the staged loopback lifecycle and exact `PRIVATE_LEAD` role. The model receives neither tools, authority, approvals, credentials, generic invocation access, nor a shell.

`gate/plugin/work-mode.mjs` validates every proposal against the published Project 1 capability manifest before it can call the existing native capability layer supplied by the host. It then creates a separate action decision and a separate exact `REMOTE_RESULT_RETURN` egress decision. Only deterministic public utilities are presently eligible for a default return to the private loopback; Gmail, Messages, Calendar, File Steward, browser, MCP, mutations, and other personal/broker results are withheld by default even when their local action is permitted. Source-First stays a host coordinator; direct web capability proposals are not a disclosure bypass.

The reusable shared layer retains the approved semantic capability vocabulary: exact utilities; Source-First evidence; browser reads; Gmail, Messages and Calendar reads where the manifest is actually exposed; File Steward; MarkItDown/curated MCP; scoped Markdown creation; bounded steward mutation; and existing approval-gated browser mutation. Missing captured schemas remain unavailable.

## Work Mode and command boundary

The coordinator owns phase, task state, iteration/model/time budgets, proposal correction count, terminal result, and reviewer sequencing. It supports `COMPLETE`, `BLOCKED`, `NEEDS_APPROVAL`, `BUDGET_EXHAUSTED`, `ITERATION_LIMIT`, `SAFETY_POLICY_BLOCK`, and `ENVIRONMENT_FAILURE`. A final claim cannot complete after a failed test state, and completion uncertainty does not replay an action.

`gate/plugin/command-broker.mjs` accepts only a fixed host catalog, never model command text. It uses `spawn` without a shell, a scrubbed environment, a bounded output/timeout, and requires macOS `sandbox-exec` with network denied, only the approved worktree readable/writable, and an owner-created temporary directory. Missing sandbox support, an unknown operation, a requested network path, or an invalid workspace fails closed. Git worktrees and reversible staging remain owner-selected deployment inputs; no canonical checkout, home path, Docker socket, Keychain, ambient credentials, cloud/production endpoint, or raw filesystem path is exposed.

One reviewer is sequential and separate-context only. It may require a revision or reject; it cannot execute, approve, or change budgets.

## Validation and remaining live qualification

The source suite contains synthetic coverage for the full graded fixture vocabulary: local bug, failing test, multi-file change, schema mismatch, refactor, dependency/configuration, ambiguity, approval, malicious repository text, and impossible/unsafe tasks. It also covers invalid/repeated proposals, schema drift, action approval, result withholding, completion uncertainty, workspace/command rejection, bounded surface selection, and reviewer revision/rejection.

The source-only suite is not a substitute for a bounded live Work Mode qualification against the accepted Qwen deployment. Before that run, apply the reviewed `scripts/upgrade_private_lead.py` amendment with the candidate gateway stopped, run doctor, select an owner-approved isolated worktree, and keep the run content-free/synthetic. Record GPU-active time, model latency, cost, tool correctness, egress outcomes, reviewer benefit, and provider-confirmed cleanup in the private prefix. Do not promote PRIVATE_LEAD or begin any later project if this live gate fails.

## Rollback

The staged private-lead amendment retains a private rollback transaction and restores only the altered installed files, freeze and receipt. It leaves the accepted 80B descriptor, private state, credentials, sessions, volumes, receipts, and caches intact. Source rollback is an ordered revert of this stage’s commits.
