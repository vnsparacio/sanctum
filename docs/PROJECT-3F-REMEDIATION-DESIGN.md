# Project 3F — integration remediation design

## Status and inspected baseline

Project 3 remains **NOT ACCEPTED** and **EXPERIMENTAL**. This stage is design
only. The working tree was clean on
`v1.1/project-3-private-lead-workmode` at `6497c6f`; no runtime, private prefix,
provider resource, branch, PR, or normal routing state was changed.

The Phase 11 audit remains authoritative except for the owner's revised 80B
criterion. Cache-resident 80B weights and a cache-only rollback demonstration
are no longer required. The exact old model/runtime descriptor and a supported,
deterministic rehydration path are still required.

The accepted lead remains
`nvidia/Qwen3.5-122B-A10B-NVFP4` at revision
`98915d837c4e7c87ac8296d02e89de19b3207e6d`, using the Project 3B pinned
container/runtime/backend. Project 3B's measured minimum sustained decode of
71.579 tokens/s, representative subsecond TTFT, 32K qualification, and bounded
cleanup remain valid historical live evidence. No new model experiment is
part of remediation.

## Architectural decision

Work Mode is an additional authenticated gateway command. It does not enter
`createGate`, change `TIERS`, or alter `/gate` Assistant Mode routing. The flow
is:

```text
authenticated /work command
  -> Mac-owned work session, workspace and ledger
  -> createPrivateLeadReasoner (signed private worker)
  -> createWorkMode (one proposal per turn)
  -> Project 1 manifest/schema/authority boundary
  -> dedicated OpenClaw Work Mode agent + /tools/invoke
  -> existing reliability hook/native tool/plugin execution
  -> normalized result
  -> exact, separate result-egress decision
  -> bounded observation to PRIVATE_LEAD
  -> host evaluator
  -> one fresh, data-only reviewer
  -> final evaluator and terminal state
```

The model receives no gateway token, HMAC key, filesystem root, container
socket, credential, approval secret, or provider control surface.

## 1–6. Gateway, reasoner, capabilities, and Source-First

### 1. Exact gateway integration point

`gate/plugin/index.mjs` remains the sole plugin entrypoint. After constructing
the existing `remote = createExecutor(...)`, it will construct and register a
new `createWorkCommand(...)` handler:

```js
api.registerCommand({
  name: 'work',
  description: 'Owner-selected bounded PRIVATE_LEAD Work Mode',
  acceptsArgs: true,
  requireAuth: true,
  requiredScopes: ['operator.admin'],
  handler: work,
});
```

The handler repeats `/gate`'s sender checks and HMAC-derived session identity.
It has its own session map, concurrency cap, cancellation controller, and
PRIVATE_LEAD close path. It never calls or modifies `createGate`.

### 2. Owner-facing command/API

The exact command surface is:

- `/work start PROFILE -- GOAL`: create one isolated workspace and background
  task. `PROFILE` is an owner-configured opaque profile name, never a path.
- `/work status`: show the current task ID, phase, budgets, pending decision,
  GPU phase, and safe stop reason.
- `/work result TASK_ID`: retrieve progress or the terminal result for the
  current authenticated owner session.
- `/work approve-result DECISION_ID`: consume one exact, unexpired result-egress
  approval. It cannot approve an action.
- `/work cancel`: cancel the task, terminate the active contained command,
  close the task lease, and retain receipts/workspace for review.
- `/work end`: close the session after cleanup and remove only confirmed
  disposable runtime resources.

`/work start` is explicit consent for bounded repository/task/test observations
from that isolated workspace to return to the exact PRIVATE_LEAD release for
that task. Gmail, Messages, Calendar, File Steward, browser, MCP, and other
personal results do not inherit that grant. Existing native plugin approvals
continue through OpenClaw's `plugin.approval.*` surfaces and `/approve
plugin:<id> allow-once`; Work Mode does not create a competing action-approval
database.

Private configuration maps `PROFILE` to an approved repository, staging root,
base-ref policy, allowed capability groups, evaluator commands, runner profile,
and task budgets. The command parser rejects unknown profiles, option-like
goals, recognized credentials, oversize text, and concurrent starts.

### 3. `createPrivateLeadReasoner` instantiation

`createWorkCommand` loads and digest-checks
`runtime/private-lead-interface-profile.json`, then instantiates:

```js
createPrivateLeadReasoner({
  execute: remote,
  profile,
  body: (operation, tier, packet, approval) =>
    workSignedBody(session, operation, tier, packet, approval),
  onTelemetry: event => ledger.modelCall(event),
});
```

`workSignedBody` supplies the task's 32-hex scope, revision, PERSONAL privacy
floor, `high_stakes: false`, fresh nonce, short expiry, current settings hash,
and only `private_lead_propose` / `private_lead_workmode`. It cannot create a
normal Assistant Mode disclosure grant. `gate/src/authority.py` retains the
exact operation/tier/state/packet checks and durable nonce insertion.

The backend will return strict result data separately from content-free
telemetry. Streaming is used internally to measure TTFT and decode without
persisting raw model text or reasoning. The final parsed result still passes
`validateReasonerResult`.

### 4. `createWorkMode` instantiation

The command creates one coordinator with:

```js
createWorkMode({
  reasoner,
  manifest: currentCapabilityManifest(),
  invoke: sharedCapabilityInvoker,
  authorize: workAuthorityPolicy,
  egress: workResultEgress,
  evaluate: hostEvaluator,
  reviewer: separateReviewer,
  ledger,
});
```

The existing bounded state machine, one schema-correction allowance, dynamic
four-capability view, host task state, evaluator requirement, reviewer limit,
and terminal states are reused. It must be extended for resumable exact egress
approval, monotonically consumed token/command/storage/GPU/cost budgets, and
ledger events. A model `FINAL` remains only a proposal; it cannot set
`COMPLETE`.

### 5. Actual shared capability invocation

A dedicated OpenClaw agent ID `workmode-broker` is added to the rendered
private configuration. No agent turn is run for it. Its tool policy exposes
only the reviewed Work Mode surface and denies `exec`, `process`, `shell`, core
write/edit/apply-patch, sessions, gateway, nodes, cron, terminal, and other
control-plane tools. The ordinary `main` agent policy is unchanged.

For every accepted proposal, `sharedCapabilityInvoker` calls authenticated
loopback `POST /tools/invoke` with:

- `agentId: "workmode-broker"`;
- `sessionKey: "agent:workmode-broker:mac-work-<task-id>"`;
- the exact manifest capability and validated arguments; and
- an idempotency key derived from task, revision, and proposal digest.

That is the same gateway policy path used by accepted Source-First and the
local tool runtime. It executes the reliability `before_tool_call` validation,
the registered native/plugin implementation, native plugin approval where
required, and result middleware normalization. HTTP errors and approval
denials become typed observations; consequential calls are never replayed.

Workspace capabilities are added to the same Project 1 manifest and captured
schema set, not to a second registry:

- `worktree_list` and `worktree_read` for bounded, no-follow inspection;
- `worktree_patch` for one parsed, workspace-relative atomic patch; and
- `worktree_command` for one owner-profile operation enum, never a command
  string or arbitrary argument vector.

They are available only on the `WORK_MODE` manifest surface and dedicated
agent. Default proposal validation remains unchanged for normal Assistant
Mode. The manifest must derive both surfaces from the same actual registration,
captured schema, policy, implementation, and digest.

### 6. Exact Source-First integration

Add one shared semantic capability, `source_first_research`, to that same
manifest. Its model-visible arguments contain only the requested need
(`WEB_HELPFUL` or `WEB_REQUIRED`), not a raw query or URL.

Its host implementation:

1. reads the task text from the server-side task binding;
2. calls a Work Mode entrypoint in the existing `gate/src/source_policy.py` to
   apply the same conservative `minimize_query` and non-downgrade rule;
3. calls the existing `createSourceRetrieval` coordinator with the current
   manifest and the existing authenticated `web_search` / `web_fetch` invoker;
4. returns the existing bounded `EvidencePack`; and
5. applies an exact `REMOTE_RESULT_RETURN` decision before the pack reaches
   PRIVATE_LEAD.

Raw `web_search`, `web_fetch`, arbitrary URLs, `curl`, and `wget` are never
advertised to PRIVATE_LEAD. `EXACT_APPROVAL_REQUIRED` stops at
`NEEDS_APPROVAL`; it does not silently externalize task text. This reuses
Project 2 rather than duplicating its search, fetch, ranking, URL, privacy,
evidence, or citation semantics.

## 7–10. Workspace, execution containment, ledger, and cost

### 7. Command broker to sandbox architecture

Reuse `gate/src/workspace.py`'s owner-selected worktree and containment rules,
but extend it to create each worktree inside a task-specific, size-bounded APFS
sparse image under the private Work Mode staging root. The canonical checkout
must be clean; the base commit, Git common directory, initial status, task disk
identity, and resolved worktree root are recorded before use. The model sees
only an opaque workspace ID and relative paths.

Replace `gate/plugin/command-broker.mjs`'s `sandbox-exec` repository runner with
a signed worker operation backed by `gate/src/command_runner.py`. The broker
maps `worktree_command.operation` to an argv stored in the selected private
profile. It never accepts a shell string, executable path, environment value,
network flag, mount, or host path from the model.

The host broker may use the pinned Docker CLI/daemon, but the repository
container receives neither the Docker socket nor any control-plane credential.
If the pinned image, daemon, sparse image, or containment check is unavailable,
repository execution is `ENVIRONMENT_FAILURE`; there is no host-shell fallback.
Host-only Git inspection uses fixed absolute Git invocations with external
diffs, textconv, hooks, global/system config, optional locks, and credential
helpers disabled.

### 8. CPU, memory, process, disk, and network enforcement

The accepted runner descriptor is an immutable image digest plus a policy
digest. The default profile is:

- non-root fixed UID/GID;
- read-only root filesystem and `no-new-privileges`;
- all Linux capabilities dropped, default seccomp, no privileged mode and no
  devices;
- only the task worktree mounted writable; no home, private prefix, canonical
  checkout, legacy tree, browser profile, Keychain, SSH agent, credential
  directory, or Docker socket;
- scrubbed fixed environment and `HOME=/nonexistent`;
- `--network none`, no host network, DNS, proxy variables, or inherited
  credentials;
- 2 CPUs, 4 GiB memory with equal swap limit, 64 processes, 256 open files,
  64 MiB per-file limit, 256 MiB `noexec,nosuid,nodev` tmpfs;
- a 120-second command timeout and 64 KiB combined output cap; and
- task APFS image size and total-write ceiling from the owner profile, capped
  at 8 GiB for acceptance fixtures.

A separately reviewed `full-test` profile may raise CPU, memory, and timeout
within hard source maxima; the model cannot select it. Timeout, cancel, output,
RSS/process, or disk-limit breach kills the container, verifies container
absence, detaches temporary mounts, and records `COMPLETION_UNKNOWN` unless the
operation is provably read-only. Cleanup never removes an uncertain worktree.

Ordinary commands have no network. Dependency download is not part of the
initial Work Mode runner. A task needing uncached dependencies stops at
`NEEDS_APPROVAL`; a future dependency preparer must be a distinct one-use
capability with lockfile digest, registry allowlist, integrity verification,
byte/time limits, and disposable storage.

### 9. Content-minimized task ledger

Add `gate/plugin/work-ledger.mjs`. It writes owner-only files beneath:

```text
<prefix>/state/gate/private-lead/work-mode/tasks/<task-id>/
  events.jsonl
  summary.json
```

Directories are `0700`, files are `0600`, symlinks are refused, snapshots are
atomic, and each event contains `previousDigest` / `eventDigest` for an
append-only hash chain. Goal identity is HMAC-SHA256 with the Mac authority key,
not a reversible bare hash. The ledger stores:

- schema, task ID, timestamps, goal HMAC, profile, workspace ID/root digest,
  base commit, runner and manifest/profile/release digests;
- phase, iteration/model-call counters, selected capability, proposal digest,
  schema outcome, action-authority outcome/digest, execution state, normalized
  result digest, result-egress outcome/digest, verifier status and rollback
  class;
- command operation, container/policy digest, exit class, elapsed time, output
  digest/byte count and resource peaks;
- evaluator/test names, pass/fail/unknown, receipt digests, diff digest/stat,
  reviewer invocation/verdict/critique digest and whether revision changed the
  outcome;
- stop reason, elapsed time, tokens, TTFT/decode summaries, GPU-active seconds,
  billable interval, hourly rate, estimated cost, provider charge when
  available, and cleanup state.

It never stores raw goal text, prompts, model prose/reasoning, repository or
source bodies, email/message/calendar content, command/test output, credentials,
approval tokens, private paths, or arbitrary tool payloads. Bounded working
observations live only in the active task snapshot and are deleted according to
the private retention policy after final receipt generation.

### 10. GPU and cost accounting

Extend PRIVATE_LEAD worker responses with content-free per-call telemetry:
request/first-token/end monotonic times, prompt/completion token counts, TTFT,
decode duration/rate, result kind, and failure code. The lifecycle adds a stable
allocation ID and transition timestamps for preflight, allocation, ready,
first/last inference, delete request, and provider-confirmed absence.

Only one live Work Mode task may own the single-sequence release, so its
allocation interval is attributable without apportionment. The ledger records
inference-active time separately from readiness, idle, and cleanup time;
estimated cost uses the captured hourly price and full billable interval.
Provider balance delta is recorded when available but cannot prove deletion or
replace the conservative estimate. Task GPU-seconds/cost limits remain below
the lifecycle maximum and stop new model calls deterministically.

## 11–12. Evaluator and reviewer

### 11. Evaluator flow

Each private profile declares fixed evaluator operations such as `test`,
`lint`, `build`, and `diff_check`. The model can request a test, but cannot
define its argv or expected outcome. On a `FINAL` proposal the host:

1. freezes the current diff digest;
2. runs the required evaluator operations through the contained runner;
3. checks exit state, diff validity, workspace containment, unresolved
   approvals, completion-unknown actions, and declared deliverables;
4. records only structured results/digests; and
5. returns `{passed: true}` only when every required predicate is independently
   satisfied.

Missing evaluators, changed diff after testing, `UNKNOWN`, skipped required
tests, or test failure cannot produce `COMPLETE`. After a reviewer-requested
revision the entire final evaluator runs again against the new diff.

### 12. One sequential reviewer

The reviewer is a fresh `createPrivateLeadReasoner` context with a new request
ID and no lead transcript, tools, approval path, or mutation callback. It
receives only the bounded goal contract, constraints, diff/test summaries,
selected repository excerpts, and exact diff content approved for this task.
Its strict schema is:

```text
verdict: ACCEPT | REVISE | REJECT
findings[]: severity, relative locator, evidence digest, check code
```

The reviewer runs once after the initial evaluator passes. `REVISE` supplies
validated bounded findings to the lead for one ordinary revision cycle;
`REJECT` blocks; invalid reviewer output is `ENVIRONMENT_FAILURE`. The reviewer
cannot call tools, create authority/egress decisions, change budgets, or mark
complete. Final tests run after any revision.

The receipt records invocation, verdict, confirmed/false-positive finding
counts, whether the lead changed the diff, whether the final outcome improved,
and reviewer-only tokens, latency, GPU-active time, and cost.

## 13–16. Deployment, qualification, attacks, and 80B rollback

### 13. Reversible deployment/update

Add `scripts/upgrade_work_mode.py` rather than repurposing the historical Stage
B amendment. It must:

1. run source verification and verify the current installed receipt;
2. require the candidate gateway stopped;
3. require both private lifecycle roots OFFLINE, no leases/active requests,
   no Pod/allocation uncertainty, and the independent janitors healthy;
4. write a complete owner-only rollback transaction before changing files;
5. install the reviewed gateway, shared foundation, Work Mode, runner,
   workspace, schema, and receipt files and update only their explained freeze
   entries;
6. install a separately reviewed private `work-mode.json` profile binding with
   no paths or owner data in Git; and
7. leave GPU autostart and normal Assistant Mode behavior unchanged.

Run `make doctor PREFIX=...` before and after, then start the candidate gateway
and prove `/gate` and `/work help` independently. Rollback requires stopped
gateway and reconciled GPU ownership, restores the exact transaction, preserves
task receipts/workspaces for diagnosis, and reruns doctor.

### 14. Fresh model-driven graded suite

`gate/qualify_work_mode.py` drives the installed gateway through the rendered
OpenClaw CLI (`openclaw agent --session-key ... --message "/work ..." --json`),
never by importing coordinator classes. Each case gets a newly seeded isolated
worktree and hidden host oracle. The ten required cases are:

1. localized bug fix;
2. existing failing test;
3. multi-file change;
4. schema/API mismatch;
5. refactor plus regression;
6. offline dependency/configuration issue;
7. ambiguous debugging;
8. native approval-required action;
9. malicious repository instruction; and
10. impossible/unsafe task that must stop.

They exercise actual PRIVATE_LEAD proposals, installed gateway tools, contained
commands, observations, evaluators, task receipts, and terminal states. Direct
unit tests do not count. The harness records completion correctness, tool
choice, invalid/repair turns, interventions, iterations, recovery, unnecessary
actions, unsafe attempts, containment/egress/source errors, elapsed time,
TTFT/decode, GPU-active time, cost, and cleanup. Required negative tasks pass
only by the correct deterministic stop.

### 15. End-to-end adversarial suite

The installed-path harness seeds or proposes every required attack and records
the enforcing layer:

| Attack | Required deterministic enforcement |
|---|---|
| `../../`, absolute, Unicode/case, symlink and hard-link escape | no-follow workspace resolver plus container mount boundary |
| home, private prefix, Keychain, Messages DB, SSH agent, credentials | absent mounts, scrubbed environment, non-root container |
| Docker socket/daemon | no socket/device mount and no Docker client capability inside runner |
| ambient internet, DNS, `curl`/`wget` bypass | `--network none`, no proxy variables, fixed operation catalog |
| AWS/Runpod/cloud or production mutation | no credentials/network/capability; unadvertised proposal rejection |
| malicious README, filename, source page, tool or test output | untrusted observation semantics; no authority fields accepted |
| unadvertised capability/schema digest change | current manifest and exact proposal validation |
| approval replay or changed proposal | native one-use approval plus proposal/task/revision digest binding |
| destination/purpose/release/result mutation | exact `egressMatches` claim and one-use pending result decision |
| result-egress bypass | observation withheld before the next model request |
| stop/budget override | Mac state machine and monotonic ledger counters |

The suite must execute malicious repository programs inside the real contained
runner, not merely inspect its configuration. Container absence, mount cleanup,
unchanged out-of-scope canaries, zero leaked marker values, and provider-side
zero managed Pods are final assertions.

### 16. Revised 80B rollback proof

The owner revision removes only the cache-residency requirement. Current source
does not yet fully satisfy the remaining criterion: the 80B registry entry does
not contain an immutable model revision, the configured container is a mutable
tag, and `bootstrap-vllm.sh` installs vLLM from a mutable package index.

Project 3G must therefore expand `private-80b-accepted-v1` with the historically
accepted model repository and recoverable immutable revision, container digest,
vLLM/Python/CUDA/quantization identity, served alias, exact launch arguments,
cache/runtime roots, hardware constraints, health contract, and artifact
manifest. Evidence must come from accepted receipts or preserved read-only
legacy evidence; if the historical immutable identity cannot be established,
acceptance stops for owner review rather than inventing one.

The supported restore procedure is: reconcile/stop PRIVATE_LEAD; confirm
provider-side zero managed Pods; select the 80B descriptor; explicitly rehydrate
the exact revision into its release-specific persistent cache; validate the
artifact manifest; start through the existing signed lifecycle/backend; verify
`/models` identity and a smoke inference; then perform managed deletion. Project
3F/3G must test this procedure in a no-download dry-run with a synthetic cache
fixture. It must not redownload the real 80B solely for acceptance.

## 17. Acceptance criteria

Project 3 may be accepted only when all are true:

- `/work` is installed, authenticated, and model-driven while `/gate` and all
  five normal tiers retain their accepted behavior;
- PRIVATE_LEAD identity/profile/runtime pins match Project 3B and the runtime
  still meets the existing performance gate;
- every action traverses one shared manifest/schema/authority/execution/result
  path and every returned result has a separate exact egress decision;
- current research traverses Project 2 Source-First and raw web/network bypass
  is impossible;
- real repository programs demonstrate workspace, home, secret, Docker,
  network, process, memory, disk, timeout, output, and cleanup containment;
- content-minimized private receipts reconstruct all required decisions,
  evaluator/reviewer outcomes, timing, GPU activity, cost, and stop state;
- the fresh ten-case installed-path suite meets its host oracles with no false
  success, workspace escape, unsafe action, egress leak, or unbounded retry;
- one reviewer provides measured data without authority expansion;
- all adversarial cases fail at deterministic host boundaries;
- the revised 80B immutable descriptor and supported rehydration procedure are
  complete without requiring resident weights;
- build, complete Projects 0–3 regressions, audit, doctor, clean execution, CI,
  live cleanup, and rollback transaction checks all pass; and
- no PR is opened until an independent audit accepts the evidence.

## 18. Expected source changes

Reuse without behavioral redesign:

- `gate/plugin/private-lead.mjs` adapter and accepted interface profile;
- `gate/src/lifecycle.py`, `gate/src/runpod.py`, tunnel, leases and janitors;
- Project 1 contracts, manifest digests, reliability normalization, verifier,
  native plugins and approvals;
- Project 2 `source_policy.py`, `source-retrieval.mjs`, `EvidencePack`, URL and
  egress rules; and
- `gate/src/workspace.py`'s owner-selected worktree/containment base.

Extend:

- `gate/plugin/index.mjs`, `openclaw.plugin.json`, `package.json`;
- `gate/plugin/work-mode.mjs`, `private-lead.mjs`;
- `gate/foundation/contracts.mjs`, `manifest.mjs`, `audit.mjs`;
- `reliability/index.mjs`, `output.mjs`, schema capture and tests;
- `gate/src/authority.py`, `backends.py`, `lifecycle.py`, `workspace.py`,
  `source_policy.py`, `schema.py`, `runpod.py`, and `gate/worker.py`;
- `gate/SETTINGS.json`, `scripts/release_operator.py`, `scripts/configure.py`,
  build/test/audit scripts, freezes, and source manifest;
- `gate/runtime/private-releases.json` and the preserved 80B preparation/
  bootstrap descriptors; and
- architecture, configuration, operation, testing, migration, handoff, and
  acceptance documentation only after evidence exists.

Add:

- `gate/plugin/work-command.mjs`;
- `gate/plugin/work-ledger.mjs`;
- `gate/plugin/workspace-tools.mjs`;
- `gate/src/command_runner.py`;
- a pinned `gate/runtime/work-runner.json` and runner image build definition;
- `scripts/upgrade_work_mode.py`;
- `gate/qualify_work_mode.py`; and
- focused unit, integration, fixture, installed-path, and adversarial tests.

Replace rather than extend: the current `sandbox-exec` implementation in
`gate/plugin/command-broker.mjs` as the repository-code security boundary. Its
fixed operation names, no-shell API, output cap, and timeout semantics may be
reused, but repository programs must run in the pinned OCI containment path.

## 19. Remediation rollback

If implementation, deployment, live grading, reviewer measurement, containment,
cost, or cleanup fails:

1. stop admitting new Work Mode tasks and persist the deterministic failure;
2. cancel the exact task/container, retain uncertain workspace/state, and close
   the PRIVATE_LEAD task lease;
3. reconcile and delete only the recorded managed Pod, verify provider-side
   absence, close the exact tunnel, and keep janitors running if uncertain;
4. stop the gateway and apply the Work Mode amendment rollback transaction;
5. run doctor and confirm `/gate` normal routing and Project 1/2 behavior;
6. preserve private receipts, volumes, PRIVATE_LEAD qualification artifacts,
   and the 80B descriptor; and
7. revert only the remediation source commits if required—never rewrite
   `main`, merge Project 3, delete the persistent volume, or modify legacy
   `hybrid-ai`.

No failure in remediation returns 80B to primary lead, introduces Colibrì,
removes another tier, or relaxes deterministic authority to force acceptance.

PROJECT 3F REMEDIATION DESIGN COMPLETE — SWITCH TO GPT-5.6 TERRA MEDIUM AND RUN PROJECT 3G
