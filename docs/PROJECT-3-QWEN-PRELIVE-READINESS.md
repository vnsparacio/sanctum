# Project 3 Qwen offline pre-live readiness package

Date: 2026-09-16. Source implementation for independent review only. Project 3
remains experimental and unaccepted. No private installation, amendment, doctor,
provider inspection, allocation, Qwen inference, microprobe, or live qualification
was performed. Nothing here claims improved Qwen behavior or authorizes spending.

## Starting review target

The canonical checkout and external private prefix are identified in the
[live baseline](V1.1-LIVE-BASELINE.md). Work remained in the existing
`v1.1/project-3-private-lead-workmode` checkout at HEAD
`e168f864eb5ed74d3437102323cdf79804505f06`, eleven commits ahead of its local
tracking reference. No fetch or Git index/history operation occurred. Starting
state: 12 modified tracked files, 15 individually counted untracked files, and
no staged changes. The larger original repair and R1–R4 changes were preserved.

The authoritative [targeted review](PROJECT-3-QWEN-PROTOCOL-TARGETED-REVIEW.md)
concludes `R1–R4 DELTA REVIEW PASSED — PRE-LIVE GATES STILL OPEN — NO LIVE RUN AUTHORIZED`.
Read AGENTS.md, baseline, all four protocol reports, architecture, configuration,
and migration documents. HEAD alone was not used as the source identity.

The complete starting inventory covers 262 source files, including untracked
files. Its SHA-256 is
`fbecb0471e214502a06b8fbcdb19f6b2438d830ab65b92593e098059c9cd4941`.
Starting SOURCE-MANIFEST SHA-256:
`f01e3404b8ab1d54c14c1b7bec2477cf9314349c905d5cec86cfc3c0f82d9e4e`.
Source-only inventories, logs, original manifest and status are retained under
`/tmp/sanctum-prelive-readiness`. No credentials, personal sources, historical
model outputs, private receipts, private runtime files or legacy-tree files were
inspected. Historical installation identities are not newly verified evidence.

## Architecture and attempt semantics

`src/experiment.py` adds experiment and attempt tables to the existing private
`control.sqlite` under the PRIVATE_LEAD state directory. This uses the existing
owner-only directory/database convention and SQLite `BEGIN IMMEDIATE`, not a new
storage service. A record owns one experiment ID, reviewed source-manifest digest,
rendered installation-freeze digest, creation/expiry, absolute deadline, owner
PID/start identity, fixed limits, allocation ownership, request/lease and supervisor
state. The source digest comes from the coherent amendment receipt; the installation
digest binds actual rendered FREEZE bytes. The signed worker verifies that freeze.

The fixed envelope is six inference reservations total: one readiness reservation
with at most 16 output tokens and five proposal reservations with at most 1024
output tokens each. A new experiment cannot replace an unresolved one; old IDs
remain present and cannot be reused. No prompts, task text, repository bytes,
reasoning, output text, exception messages or provider response bodies are stored
in these tables. IDs, fixed codes, bounded counters, times and process identities
are the stored facts. Provider ownership IDs are private resource references.

Immediately at the Mac completion boundary, the guard commits an atomic reservation
and then marks local dispatch initiation before allowing HTTP transmission. The
transaction checks ID, source/install binding, state, expiry, common deadline,
class allowance, total allowance and output-token ceiling. Another process cannot
reuse that reservation. “Dispatched” means local dispatch initiation, not an
acknowledgment from the provider. A crash before actual transmission can therefore
conservatively count as dispatched/uncertain. The tiny reservation-to-transmission
gap is not represented as proof that a request reached the provider.

All reservations start with uncertain completion. Only a fully received response
marks completion known. A completed response with invalid JSON remains counted and
can receive the existing single correction; interrupted transport stops the
experiment. HTTP errors, failed transmission, parser failures, cancellation,
timeout, restart and successful results never refund a reservation. Failed smoke
ends the experiment even when its completed response is known. No readiness
inference occurs inside a polling loop. Non-inference model-list/SSH readiness
checks may poll; their timeout is bounded by the common deadline.

`DiagnosticLifecycle` is separate from ordinary proposal readiness. The signed
`packet.experiment` binding goes through the existing HMAC/nonce contract and real
worker entry point. The backend receives the diagnostic context locally; experiment
metadata never becomes model instructions. Ordinary PRIVATE_LEAD/PRIVATE_80B
lifecycle admission is refused while an experiment owns PRIVATE_LEAD. Without an
experiment, ordinary retry, sampling, token, schema and model behavior remain.

`experiment_control.py` and `diagnostic-experiment.mjs` prepare an installed
owner-operated path. Importing either does not allocate or infer. The executable
path requires a separately supplied owner authorization document plus the explicit
allocation flag. Gate booleans in that document are owner attestations of completed
checks, not automatically discovered proof. These files are preparation, not an
implicit authorization to execute them now.

## Absolute deadline and independent supervision

One absolute Unix deadline is bound into the ledger, signed worker packet,
executor timeout, diagnostic lifecycle, readiness smoke, proposal transport, probe
runner and cleanup state. The experiment lifetime is at most 900 seconds from
creation, which also bounds allocation lifetime conservatively. New inference
requires at least one second before `deadline - 120`; the last 120 seconds are
reserved for cleanup. HTTP waits are capped by remaining time. The worker/control
process also arms an absolute-derived alarm, so an endless trickle of response bytes
cannot extend its deadline indefinitely. The diagnostic probe runner has its
existing 180-second ceiling, additionally capped by that same absolute deadline.
No sequence of relative phase timers can extend the experiment. Diagnostic-only
provider CLI calls are also capped at 20 seconds and remaining time (Keychain
lookup at 10 seconds). Cleanup remains available after expiry with bounded calls;
ordinary provider timeouts are unchanged. The cleanup reserve allows the usual
list/delete/list sequence but cannot guarantee provider response or billing cessation.

`ExperimentSupervisor`, integrated with PRIVATE_LEAD sweep and `watch.py`, runs
outside the caller, gateway and request worker. The existing loaded launchd janitor
can resume sweep after a watcher or Mac restart. Its separate nonblocking lock
serializes supervisor ticks without waiting for a worker's lifecycle lock. It
never allocates. It watches caller/worker identity, absolute deadline, durable
reservation state, allocation identity and cleanup status. PID identity includes a
digest of process start time to avoid signaling a reused PID.

Caller/worker loss, deadline, cancellation or failure changes state to
`CLEANUP_REQUIRED`; it does not erase ownership. The supervisor closes the lease,
signals still-identical workers, escalates from TERM to KILL after a persisted
five-second grace, requests exact managed deletion and lists again. Provider-confirmed
absence and local worker/request/lease reconciliation are both required for
`COMPLETE / CONFIRMED`. Unknown deletion retains the resource identity and active
supervision. A hung lifecycle lock cannot prevent a provider deletion request.

Allocation intent is persisted before the only create call; no capacity retry or
second allocation is permitted. If create is ambiguous and no matching allocation
is visible, a negative list cannot prove no delayed allocation will appear. That
record stays unresolved for reconciliation/owner investigation. A matching resource
can be adopted for deletion, never for a new experiment. Persistent model volumes
are never deleted. Local timeout, local process death, a delete API response, or a
terminal receipt is not a claim about billing cessation. Provider billing must be
reconciled independently under the future authorized procedure.

## Exact compiler and tokenizer preparation

`runtime-readiness.mjs` produces a deterministic synthetic artifact from actual
production schema and request builders. It enumerates exactly these six production
surfaces: ordinary ineligible/eligible, research ineligible/eligible, post-patch
test-only ineligible, and reviewer. Every branch has a host-valid representative.
Both full generation and full authoritative schemas and their identities are
included. No schema is weakened, regex fragment substituted, or acceptance changed.
The separate allEligible coverage superset remains in the existing preflight.

The coordinator and reviewer request construction was extracted into exported pure
builders without changing request fields/text. The backend's pure `proposal_payload`
is shared with token measurement. Preparation includes ordinary initial state,
accumulated observations, active correction, exactly the current 64000-character
boundary, post-patch test-only state and reviewer. These are clearly synthetic
representative states, not qualification fixture examples or token-fit proof for
every possible task.

`verify_exact_runtime.py` requires a reviewed exact environment document. Inventory
records every resolved Python distribution version and RECORD digest, vLLM 0.20.1,
compiler backend module digests, backend selection configuration and per-surface
resolved backend evidence digest, model/revision, tokenizer-file digests, tokenizer
revision, and exact chat-template UTF-8 digest. The local tokenizer snapshot must
match the unchanged model revision. Loading is cache/local-only with remote code
disabled; no weights are loaded and no fallback tokenizer is allowed.

The prepared compiler adapters call the actual installed vLLM backend's
`compile_grammar(JSON, full_schema)` and exercise representative token sequences
through the backend matcher, including EOS. Adapters are supplied for xgrammar
and outlines. An unresolved `auto` choice or any other backend lacks proof and must
stop for a separately reviewed adapter; the tool does not switch the deployment.
The source dialect label does not establish the resolved backend. The adapter API
was checked against the official [vLLM 0.20.1 backend interface](https://raw.githubusercontent.com/vllm-project/vllm/v0.20.1/vllm/v1/structured_output/backend_types.py),
[xgrammar implementation](https://raw.githubusercontent.com/vllm-project/vllm/v0.20.1/vllm/v1/structured_output/backend_xgrammar.py)
and [outlines implementation](https://raw.githubusercontent.com/vllm-project/vllm/v0.20.1/vllm/v1/structured_output/backend_outlines.py).
No model/provider service was contacted for this source API inspection.

The full-schema compiler path is **NOT RUN** here: exact compiler packages,
resolved serving configuration and pinned tokenizer/template were not available in
the authorized environment. Nothing was downloaded or repinned to produce a green
result. AJV and host/source-dialect checks are separate offline evidence. Backend
adapter API preparation is not execution proof; CPU execution still requires a
compatible reviewed environment. Live endpoint compatibility is independently
**NOT RUN** even if a future CPU compiler command passes.

Prepared commands, in a separately authorized compatible environment, using a
private artifact directory and the exact reviewed package:

```sh
node "$SANCTUM_PREFIX/gate/runtime-readiness.mjs" > "$SANCTUM_EVIDENCE/requests.json"
"$SANCTUM_EXACT_PYTHON" -B "$SANCTUM_PREFIX/gate/verify_exact_runtime.py" \
  --artifact "$SANCTUM_EVIDENCE/requests.json" \
  --tokenizer "$SANCTUM_TOKENIZER_SNAPSHOT" \
  --inventory-from-resolved "$SANCTUM_EVIDENCE/resolved-backend.json" \
  > "$SANCTUM_EVIDENCE/candidate-environment.json"
# Independently review/freeze candidate-environment.json before using it as expected.
"$SANCTUM_EXACT_PYTHON" -B "$SANCTUM_PREFIX/gate/verify_exact_runtime.py" \
  --artifact "$SANCTUM_EVIDENCE/requests.json" \
  --tokenizer "$SANCTUM_TOKENIZER_SNAPSHOT" \
  --environment "$SANCTUM_EVIDENCE/reviewed-environment.json" \
  > "$SANCTUM_EVIDENCE/exact-runtime-result.json"
```

The resolved-backend input must identify the unchanged model/revision, the actual
`selection_config` including `backend` and boolean `disable_any_whitespace`, every
surface's resolved backend, and SHA-256 of separately retained non-content runtime
resolution evidence. A source label, guessed default or mocked backend is
insufficient. Preserve `auto` if that is the observed selection configuration;
do not amend backend selection to satisfy this check. Export the complete resolved
distribution/wheel lock from that environment for reproducibility; do not install
“latest” transitive packages on the Mac. The candidate inventory binds the exact
production preparation artifact and must be reviewed rather than auto-promoted.

For each request the measurement command applies the exact pinned chat template
with thinking disabled and the production generation prompt. It reports content-only
system-message and user-message token counts, rendered total input tokens,
template overhead, unchanged 4096-token profile reserve, actual 1024-token proposal
ceiling, unchanged 32768-token model window, and remaining headroom. Negative
headroom fails the check. Content-only counts need not sum to the rendered total.
No tokenizer/template measurement was run here; character counts are never relabeled
as tokens. Context limits and compaction policy remain unchanged.

## Coherent amendment and package

The supported `scripts/upgrade_work_mode.py` overlay now includes all new runtime
modules, the installed diagnostic caller/control, exact-runtime tools, and changed
watcher. Its safety check now examines both PRIVATE_80B and PRIVATE_LEAD lease
stores and rejects unresolved experiments. It records the reviewed source-manifest
digest in the private amendment transaction and installation receipt; HEAD is
retained only as supplementary history. Rendered FREEZE binds installed bytes.

The amendment was inspected, not executed. Its existing Docker build/pull side
effects remain part of a future explicitly authorized installation. The overlay
relies on unchanged base-package modules and pinned runtime dependencies. A permanent
closure test materializes the HEAD base package, overlays current reviewed files,
renders synthetic paths, removes the checkout from module lookup and runs Python
imports, production JS request builders and the unavailable-environment CLI outside
the checkout. Approved interpreter/dependency runtimes remain external by design.

SOURCE-MANIFEST is an explicit new source review freeze for this explained delta
and the previously unrecorded targeted review. It is not an installation freeze,
a way to conceal drift, or independent acceptance. Unrelated existing entries and
separate runtime pins are preserved. Reports from earlier repairs/reviews are unchanged.

## Future installation and microprobe runbook

<!-- RUNBOOK START -->
**NOT AUTHORIZED TO EXECUTE BY THIS WORK PACKAGE**

All paths below are owner-set absolute paths. `SANCTUM_PREFIX` is the external
private candidate, `SANCTUM_EVIDENCE` a new owner-only directory under that prefix,
and `SANCTUM_REPO` the canonical checkout. Use one independently reviewed source
manifest and one coherent stopped-gateway amendment. Each step is a gate; stop on
failure. Exact compiler/token evidence must pass in the separately authorized
compatible environment before allocation authorization. No coding task belongs
inside this microprobe envelope.

1. **01 VERIFY_SOURCE.** Verify the independently reviewed full source inventory,
   new SOURCE-MANIFEST digest and unchanged pins with `scripts.release_operator.verify()`.
   Retain the reviewed manifest digest privately. Do not refresh a hash to suppress drift.
2. **02 VERIFY_BRANCH.** Confirm `v1.1/project-3-private-lead-workmode`, expected HEAD,
   staged/unstaged/untracked inventory and all repair bytes. The dirty tree is part
   of the source identity; no replacement worktree, commit or branch move is needed.
3. **03 GATEWAY_STOPPED.** Confirm the exact candidate gateway process is stopped.
   A separate approved installation window may use `make down PREFIX="$SANCTUM_PREFIX"`.
4. **04 BOTH_RELEASES_SAFE.** Inspect only bounded lifecycle facts for PRIVATE_LEAD
   and PRIVATE_80B. Both must be safely OFFLINE; unresolved allocation intent is a stop.
5. **05 ZERO_OWNERSHIP.** Require zero active requests, leases and managed ownership
   in both stores, plus provider-confirmed absence under separate provider-read
   authorization. Zero local rows alone is insufficient.
6. **06 SUPERVISOR_READY.** Verify the independent prefix launchd janitor's actual
   successful sweep, not just a plist. Confirm the reviewed watcher/supervisor
   integration and wake/restart policy. Leave GPU autostart disabled.
7. **07 AMEND.** With a separately authorized stopped-gateway installation window,
   run exactly one supported reversible amendment:
   `.venv/bin/python -B scripts/upgrade_work_mode.py --prefix "$SANCTUM_PREFIX" --apply`.
   Retain its private rollback transaction. It may build/pull the OCI runner;
   that installation side effect requires the installation authorization.
8. **08 INSTALLED_BYTES.** Verify every overlay byte against `rendered_file(prefix,name)`,
   receipt and FREEZE, and confirm the receipt's source-manifest digest equals the
   independently reviewed digest. Run the isolated package checks on these identities.
9. **09 DOCTOR.** Run `make doctor PREFIX="$SANCTUM_PREFIX"`; require success after
   the coherent amendment. An old runtime's doctor result cannot validate new bytes.
10. **10 AUTHENTICATED_GATEWAY.** Start/verify the exact candidate authenticated gateway
    with `make up PREFIX="$SANCTUM_PREFIX"` as required by the installation window.
    Stop at actual local owner enrollment/permission checkpoints; never disclose secrets.
11. **11 WORK_HELP.** Through the authenticated owner path, invoke `/work` for help/status
    only. Do not start a task, model, real workspace trajectory or inference.
12. **12 SCHEMA_PREFLIGHT.** Run installed non-inference
    `node "$SANCTUM_PREFIX/gate/preflight-work-intent.mjs" --json` and
    `node "$SANCTUM_PREFIX/gate/runtime-readiness.mjs"`. Verify all production
    schema identities, host/AJV checks, and the separately reviewed exact compiler
    and rendered-token results. Any NOT_RUN or failed required gate prevents allocation.
13. **13 NEW_LEDGER.** Confirm no unresolved experiment in PRIVATE_LEAD control.sqlite.
    Prepare fresh binding/receipt paths that do not exist. The runner creates one
    new ID with zero reservations, exactly six total attempts, one readiness slot,
    five proposal slots, 16/1024 token ceilings and one deadline. Inspect the new
    zero-count record with the runner's mandatory pre-allocation check; never
    reuse/reset an old experiment to recover calls.
14. **14 PRICE_AND_CEILING.** Reconfirm capacity, actual hourly quote at most USD 3/hour,
    billing minimums, storage charges, startup/deletion billing and all other provider
    charges. Obtain the owner-approved monetary ceiling including any separately
    itemized charges. USD 0.75 = 900/3600 × USD 3 is arithmetic, not a billing guarantee.
    If the total approved terms cannot be met, stop before allocation.
15. **15 OWNER_AUTHORIZE.** Only a new explicit owner authorization permits one
    allocation, at most 900 seconds and the six-attempt envelope. Prepare a mode-0600
    `sanctum-diagnostic-authorization/v1` document with `ownerAuthorized:true`,
    `allocationLimit:1`, `seconds:900`, `computeCeilingUsd:0.75`, confirmed `hourlyUsd`,
    near-term absolute `expires`, actual `source_id`/`install_id` from installed
    `experiment_control.py identity`, and verified true gates `independentReview`,
    `installedBytes`, `doctor`, `authenticatedWorkHelp`, `schemaPreflight`,
    `exactCompiler`, `tokenMeasurement`, `janitor`, `zeroOwnership`, `pricingAndCharges`.
    This attestation records external checks; writing booleans does not perform them.
    Then and only then use the installed runner:
    `node "$SANCTUM_PREFIX/gate/diagnostic-experiment.mjs" --owner-authorized-one-allocation "$SANCTUM_EVIDENCE/authorization.json" "$SANCTUM_EVIDENCE/binding.json" "$SANCTUM_EVIDENCE/receipt.json"`.
    It creates the ledger, requires a fresh independent supervisor heartbeat, rechecks
    capacity/price, persists one allocation intent, and makes at most one create call.
    No automatic capacity retry or replacement allocation is allowed.
16. **16 SINGLE_SMOKE.** Cache-only server startup and non-inference model-list/SSH
    checks precede at most one globally reserved 16-token readiness smoke. No runtime
    or model preparation/download, warmup, characterization or extra inference is allowed.
17. **17 SMOKE_FAILURE_STOP.** Any failed smoke ends the experiment. Never poll by
    retrying inference. Proceed directly to managed cleanup.
18. **18 FIXED_PROBES.** Run `inspection → postPatch → inability` in that fixed order:
    useful initial inspection, test-only action from a clearly labeled host-seeded
    synthetic patch state, and valid inability/escalation. Synthetic effects do not
    constitute actual Qwen editing/testing or useful task completion.
19. **19 SHARED_BUDGET.** Each probe has the existing one-correction allowance, but
    all share five proposal attempts. Three first decisions plus at most two
    corrections fit. If the third correction would be needed, stop incomplete.
    Readiness plus proposals may never exceed six reserved attempts.
20. **20 STOP_FIRST_FAILURE.** Stop immediately on the first terminal contract,
    semantic, budget, deadline, cancellation, transport or cleanup failure. A first
    correctable invalid decision can use only the existing correction; a second
    invalidity is terminal. No later probe runs after a failed probe.
21. **21 DELETE.** Mark cleanup required and request managed deletion of the exact
    persisted allocation. Caller loss or a hung worker triggers the independent
    supervisor. No second allocation, retry experiment or resumed inference is allowed.
22. **22 CONFIRM_ABSENCE.** Require a successful provider list proving the owned
    allocation absent. A delete response or local timeout is insufficient. Ambiguous
    create/deletion retains ownership and requires continued reconciliation.
23. **23 ZERO_LEASES.** Reconcile verified worker exit, zero active requests and zero
    leases before terminal cleanup. Known responses do not erase uncertain attempts.
24. **24 PRESERVE_STORAGE.** Preserve persistent model storage, configuration and
    evidence. Do not delete the volume or reset the ledger.
25. **25 UNCERTAIN_SUPERVISION.** Keep the watcher and independent janitor active
    if provider absence/local cleanup remains unknown, including beyond the deadline.
    Preserve IDs and evidence for owner reconciliation; report incomplete cleanup.
26. **26 RECEIPT.** Retain the content-minimized experiment receipt: source/install/ID,
    deadline, fixed limits, reservations/dispatched/known/uncertain counts, probe
    dispositions and cleanup state. Compare provider billing separately. Do not
    retain prompts, raw output, reasoning, repository content or provider bodies.

To request early cancellation through the installed control after authorization:
`"$SANCTUM_PYTHON" -B "$SANCTUM_PREFIX/gate/experiment_control.py" stop --binding "$SANCTUM_EVIDENCE/binding.json" --outcome CANCELLED`.
The independent watcher remains responsible for deletion and reconciliation. Status
is available from the same command with `status`; the owner-authorized cleanup
command is `sweep`. A stopped caller does not transfer authority back to a model.
<!-- RUNBOOK END -->

## Validation and limitations

All fixtures are synthetic. The existing dependency venv was inspected first
(Python 3.12.14, Pillow 12.3.0, pypdf 6.18.0, imageio-ffmpeg 0.6.0). The canonical
cache-only dependency bootstrap passed: 383 npm packages with scripts disabled,
three Python requirements checked, no downloads/upgrades or pin changes.
Inspected Makefile, build/test/audit and amendment side effects before execution.
Build regenerated plugin outputs; packaged tests used temporary synthetic state
and the already available cached local OCI runner. No daemon/image build/pull,
private amendment, private doctor or live model/provider operation was performed.

| Check | Final observed result |
| --- | --- |
| `.venv/bin/python -B -m unittest discover -s gate/tests -p 'test_prelive*.py'` | **42 PASS**, zero failures/errors/skips. Includes one package-closure method. |
| `node --test --test-reporter=tap gate/tests/prelive.test.mjs gate/tests/protocol-repair.test.mjs gate/tests/protocol-targeted.test.mjs` | **28 PASS**, zero failures/skips: eight new and twenty related Node tests. |
| `.venv/bin/python -B -m unittest discover -s gate/tests -p 'test_protocol_*.py'` | **15 PASS**, zero failures/errors/skips; also included in the final full run. |
| `npm_config_offline=true npm_config_audit=false UV_OFFLINE=true make deps` | PASS from cache after inspecting the existing venv; `deps.log`. |
| `make build` | PASS, six plugin builds/validations, capability manifest and pinned OpenClaw validation; `build-final.log`. |
| `umask 022` then `make test` | **355 PASS**, zero failures/errors/skips; `full-test-final.log`. Gate Node 109, gate Python 167, reliability Node 31, reliability Python 11, MCP Node 8, release Python 18, six plugin suites 11 (3+1+2+2+1+2). |
| Isolated base plus coherent amendment package | PASS: **46 overlay files**, **56 local JS edges**, **64 local Python edges**, isolated Python imports, identical production JS artifacts, and exact-runtime CLI returning NOT_RUN without an environment. Included in the 42/355 counts. |
| Exact-runtime CLI with no reviewed environment | Expected exit **2**, `status:NOT_RUN`, `EXACT_ENVIRONMENT_IDENTITY_ABSENT`; compiler, tokenizer/template measurement and endpoint all NOT_RUN. `exact-runtime-not-run.json`. No package installation attempted. |
| `make audit` | PASS, **273 source files**, zero issues, including this report. |
| `scripts.release_operator.verify()` | PASS: final recorded source hashes and separate cached runtime pins match. |
| Source invariant comparison | **249 starting files byte-unchanged**; all seven preflight generation/semantic pairs still equal the R1–R4 review; unchanged branch/HEAD and empty index. |
| `git diff --check` plus added-file whitespace scan | PASS. New untracked files are checked separately because Git's ordinary diff excludes them. |

The first complete run passed 354 tests. Final inspection then refined preparation
fixtures to the production PLAN/WORK_REQUIRED/TEST_REQUIRED states and complete
correction/reviewer shapes, and restricted diagnostic provider error persistence
to a fixed code. One new redaction regression justified the final complete run,
which passed 355. No implementation changed after that final run. Final report-only
edits and their explained manifest entry received audit/integrity/whitespace checks;
the full suite was not repeatedly rerun for documentation changes. Focused results
are subsets of the complete total, not additional tests. NOT_RUN environment work
is not reported as a passing compiler check or a skipped unit test.

The source-freeze delta has exactly **12 changed existing entries, 12 additions,
zero removals**. Changed existing entries are `gate/protocol-microprobe.mjs`,
`gate/watch.py`, `gate/worker.py`, `gate/plugin/core.mjs`,
`gate/plugin/work-command.mjs`, `gate/plugin/work-mode.mjs`,
`gate/src/authority.py`, `gate/src/backends.py`, `gate/src/lifecycle.py`,
`gate/src/runpod.py`, `scripts/test.py`, and `scripts/upgrade_work_mode.py`.
The additions are the eleven new implementation/test/report files plus the unchanged
previously unfrozen targeted review. Their exact bytes are bound by SOURCE-MANIFEST;
its own hash and the final report hash are retained in the external final inventory
to avoid a self-referential hash. Earlier reports and all unrelated freeze entries
are unchanged.

The first new Python run passed 35 methods. The first new Node run passed seven
behavioral tests and failed the runbook test because this report had not yet been
written; its attempted name filter did not exclude that test. The first isolated
package run exposed a test-harness `/var` versus `/private/var` path-resolution
mismatch. Resolving the temporary root fixed it; no package dependency was missing.
These intermediate results are not counted as final passes.

No 11-case live qualification, real coding task, unseen task, Qwen action-selection
improvement, installed doctor, exact compiler pass, exact tokenizer count, actual
provider cleanup or billing bound is claimed. Expected compiler/tokenizer execution
and installation are future gated work, not failures concealed with mocks. The
existing evaluator/reviewer policy, one-reviewer REVISE limitation, immutable
inference binding, semantic acceptance, authority/egress, Source-First, APFS/OCI,
workspace/path protection, qualification fixtures, MUTABLE_WORKTREE_V1, other
reasoning tiers and 80B rollback descriptor remain in force.

## Rollback and independent review boundary

No runtime change occurred, so current rollback consists of reviewing/removing only
this package's source delta while preserving the earlier uncommitted repair. Do not
reset the checkout. For a future authorized installation, use the recorded
stopped-gateway `upgrade_work_mode.py --rollback` transaction only after confirmed
zero owned allocations/leases/requests and terminal experiments. It restores prior
files, receipt and FREEZE and removes newly added files recorded as absent. Never
roll back executable cleanup while ownership is uncertain; preserve the ledger,
receipts, janitor and persistent model volumes. No whole-database replacement.

No known offline implementation blocker remains before independent review.
Independent review must assess atomic reservations at the actual completion boundary,
signed identity/deadline propagation, crash and concurrent-create/delete races,
caller/worker signaling, package closure and the extracted request-builder equivalence.
Actual installation, compiler/tokenizer execution and endpoint checks are explicitly
unperformed future gates. Neither this package nor its independent review alone
can authorize inference or spending.

PRE-LIVE READINESS PACKAGE READY FOR INDEPENDENT REVIEW — NO LIVE RUN PERFORMED
