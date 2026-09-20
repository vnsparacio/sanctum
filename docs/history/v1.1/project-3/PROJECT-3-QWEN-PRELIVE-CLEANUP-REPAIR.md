# Project 3 pre-live cleanup repair and 80B default retirement

Source repair following the [independent targeted review](PROJECT-3-QWEN-PRELIVE-TARGETED-REVIEW.md). The owner requested planning and repair of both cleanup findings, then asked to cut 80B if it was causing problems. This package uses the narrower retirement described during implementation: disable new 80B requests in the source default while retaining ownership reconciliation and rollback code. It does not remove resources, caches, persistent volumes or historical evidence.

Project 3 remains unaccepted. The earlier independent review's blocked disposition is preserved as historical evidence. These new bytes require independent review; passing implementation tests does not authorize installation, inference or spending.

## Plan and scope

1. Serialize every ordinary sweep's lease pruning with diagnostic admission in both release stores; close the experiment-create/check/use race while keeping provider work outside database transactions.
2. Distinguish confirmed process exit/replacement from unknown identity. Preserve leases and unresolved cleanup on lookup failure, and recover after exit becomes verifiable.
3. Add production-path counterexamples, lifecycle/crash tests, and disabled-80B routing/authority tests; repeat existing controls, package closure, build, tests, audit and integrity checks.
4. Record an explicit source freeze for the explained changes. Preserve the dirty branch and all private runtime state.

Work remains on `v1.1/project-3-private-lead-workmode`, HEAD `e168f864eb5ed74d3437102323cdf79804505f06`. Starting inventory: 277 source files, SOURCE-MANIFEST SHA-256 `f31f9697638c6f68babe15c1d677ae72995d00fe2b68e29be2d07b9aaf3d13f3`. The larger uncommitted repair and empty index are preserved. Inventories, authenticated pre-edit runtime copies, the narrow delta and synthetic command logs are retained in `/tmp/sanctum-prelive-cleanup-repair-20260917`.

No private prefix, legacy tree, credential, personal source, model output or provider response was inspected. No stage, commit, stash, reset, clean, branch switch, merge, push or PR occurred. No private installation, gateway operation, doctor, model call, allocation, microprobe or live qualification occurred.

## R1a: ordinary cleanup preserves unresolved experiment ownership

Both releases now use the common experiment-aware sweep. Its initial ownership check occurs before attempting the nonblocking lifecycle lock, so an existing experiment's independent supervisor can still run while a worker holds that lock. Manual stop persists its stop marker, but marking ordinary lease rows closing is guarded by admission.

The sweep rechecks ownership after taking the lifecycle lock. Ordinary expiry pruning, closing-row deletion and runtime-limit lease cleanup all occur under that same PRIVATE_LEAD admission transaction. PRIVATE_LEAD reuses its connection; PRIVATE_80B takes its store second. An experiment appearing between the initial check and lock acquisition therefore prevents pruning. The old separate lead override is removed in favor of this common path.

If an experiment owns the stores, the 80B sweep preserves its rows and returns. The lead sweep delegates to the diagnostic supervisor using lead configuration, after releasing database/lifecycle locks. Only that owner reconciles the diagnostic allocation. No provider operation, readiness wait or model transmission occurs under admission. Ordinary expiry, idle grace, explicit close and runtime limits remain available without an unresolved experiment, including cleanup when new 80B use is disabled.

The original independent counterexample now preserves its expired active ordinary row through 80B sweep. Provider absence is still confirmed, but the record remains `CLEANUP_REQUIRED / LOCAL_PENDING`. A subsequent sweep completes only after explicit synthetic owner reconciliation removes the foreign row.

## R1b: process evidence has three outcomes

`alive()` now returns True only for an identical observed PID/start identity, False only for verified identity replacement or confirmed process absence, and None for unknown evidence. The existing bounded `ps` identity reader still returns no identity on errors/timeouts. In that case a signal-zero process probe sends no signal: ESRCH establishes absence; a present process, permission failure or other error leaves identity unknown. Missing/invalid recorded identity also remains unknown.

Supervisor signaling requires an explicit True. Terminal cleanup requires explicit False for every recorded control, proposal, allocation and uncertain-attempt worker. Live or unknown workers preserve leases and produce local-pending cleanup. Unknown allocation-worker identity cannot clear an in-flight allocation flag. Provider deletion remains possible while local identity is uncertain; provider absence alone does not permit terminal local cleanup.

An active diagnostic lease with no recorded worker is also preserved. A normal inactive row with cleared worker identity remains reconcilable. Proposal finalization now clears worker identity and deactivates its lease in one ledger transaction, preventing a crash from producing an active row whose worker identity has already been erased. A rollback regression interrupts this final transaction and verifies that both active lease and recorded worker remain together.

The original independent live-child counterexample now retains the lease with `LOCAL_PENDING`; it neither signals the unknown worker nor confirms cleanup. Permanent tests cover both no-allocation and provider-confirmed-absence paths, subsequent successful identity lookup while the child is still alive, actual child exit, and a fresh supervisor instance completing reconciliation afterward.

## 80B: disabled for new use, cleanup retained

Source `gpu.enabled` is now false, alongside the existing disabled GPU autostart setting. The gate excludes 80B, grants no automatic private-80B session permission, and refuses `/gate include 80b` and `/gate private80 allow` while installation configuration disables it. Help and new-session text explain its availability. Routing applies the existing excluded-tier policy; any resulting hosted answer still needs its own exact disclosure approval. PRIVATE_LEAD Work Mode is unchanged by this routing decision.

Signed inference authorization, worker dispatch, lease acquisition, explicit readiness and resume refuse disabled 80B before new lease creation or provider/model operations. Status, close, stop, sweep, resource identity checks and persistent storage remain available. The two-store zero-ownership requirement remains necessary even when 80B is unused.

Existing explicit configurations without the new key keep their historical enabled behavior; the new source default and its rendered amendment set false. This is an intentional compatibility choice, not a claim that the currently installed candidate was amended. Synthetic rollback tests opt in with `gpu.enabled=True` so retained behavior and cross-release safety still receive coverage. Model/revision descriptors and bootstrap pins remain unchanged.

## Validation

All new tests use temporary synthetic stores/providers and harmless local child processes. The initial eleven-method cleanup regression run against pre-edit implementation produced 15 failed assertions across subcases, zero errors; it reproduced both findings and the stale sweep race. The first repair passed those eleven methods. Final coverage adds missing-worker identity, atomic finalization and disabled-80B behavior for fifteen new Python methods, plus one signed-authority and one gate-routing regression.

The two earlier cleanup fixtures that seeded active diagnostic leases now supply explicit synthetic worker identities to their existing verified-exit fake. This makes their successful-cleanup premise valid; a new separate test requires active rows without identities to remain pending. Their foreign-row preservation assertions remain intact.

The existing dependency venv was inspected before cache-only bootstrap: Python 3.12.14, Pillow 12.3.0, pypdf 6.18.0, imageio-ffmpeg 0.6.0. No compiler/runtime/model package was downloaded or upgraded.

| Command | Final observed result |
| --- | --- |
| `npm_config_offline=true npm_config_audit=false UV_OFFLINE=true make deps` | PASS after venv inspection; 383 cached npm packages and three pinned Python requirements checked. |
| `make build` | PASS, six plugin builds/validations and capability/runtime-pin checks. |
| `.venv/bin/python -B -m unittest discover -s gate/tests -p 'test_prelive*.py'` | **69 PASS**, zero failures/errors/skips, including all fifteen new cleanup/default tests. |
| `node --test --test-reporter=tap gate/tests/core.test.mjs` | **27 PASS**, zero failures/skips, including the disabled-80B routing/approval case. |
| `node --test --test-reporter=tap gate/tests/prelive.test.mjs gate/tests/protocol-repair.test.mjs gate/tests/protocol-targeted.test.mjs` | **28 PASS**, zero failures/skips. |
| `.venv/bin/python -B -m unittest discover -s gate/tests -p 'test_protocol_*.py'` | **15 PASS**, zero failures/errors/skips. |
| `umask 022` then `make test` | **384 PASS**, zero failures/errors/skips: gate Node 110, gate Python 195, reliability Node 31, reliability Python 11, MCP Node 8, release Python 18, plugin suites 11 (3+1+2+2+1+2). |
| `.venv/bin/python -B /tmp/sanctum-prelive-targeted-review-20260917/cleanup-counterexamples.py` | Both unchanged independent cleanup counterexamples now **PASS**. Both preserve one unresolved row and report `CLEANUP_REQUIRED / LOCAL_PENDING`. |
| `.venv/bin/python -B /tmp/sanctum-prelive-independent-review-20260917/counterexamples.py Counterexamples.test_cleanup_does_not_report_confirmed_with_ordinary_rejected_lease` | Original admission/leftover-row counterexample **PASS**, with confirmed synthetic absence and zero surviving leases. |
| `.venv/bin/python -B /tmp/sanctum-prelive-independent-review-20260917/ledger-controls.py` | **6 PASS**, including restart, final-slot races, class/total budgets, stale identity/deadline/tokens and cancellation. |
| `.venv/bin/python -B /tmp/sanctum-prelive-targeted-review-20260917/compiler-controls.py` | **4 PASS**, 50 fresh upstream wrappers across twelve full-schema checks; orchestration evidence only. |
| Isolated package closure (included in Python counts) | **46 overlay files, 56 JS and 65 Python import edges**; isolated production builders identical and unavailable exact-runtime CLI remains NOT_RUN. |
| `make audit` | PASS, 279 files, zero issues; repeated after final report update. |
| `.venv/bin/python -B -c 'from scripts.release_operator import verify; verify(); print("Source manifest and runtime pins match")'` | PASS after explicit source freeze; repeated after final report update. |
| `git diff --check` plus untracked-file trailing-whitespace scan | PASS. |

Focused test counts are subsets of the packaged total; reused independent tests are separate. The first full run reached release tests before the new source freeze had been written: ten setup tests correctly errored on stale `gate/SETTINGS.json` source identity. That partial run is retained in `full-test.log`, not counted as a pass. The second complete run, after the intentional source freeze, passed all 384 tests (`full-test-final.log`). No implementation changed afterward. Final report-only edits and their manifest entry received audit/integrity/inventory/whitespace checks.

The supported checks used synthetic state and the existing cached local OCI test environment. They did not start a daemon, build/pull a container image, amend an owner runtime or invoke a model. Compiler controls use synthetic adapters around upstream wrapper methods; exact compiler packages, tokenizer/template execution, token headroom and live endpoint compatibility remain NOT_RUN.

## Source freeze and packaging

The six changed runtime/configuration files are `gate/SETTINGS.json`, `gate/plugin/core.mjs`, `gate/src/authority.py`, `gate/src/experiment_lifecycle.py`, `gate/src/lifecycle.py` and `gate/worker.py`. All six already belong to the unchanged coherent 46-file amendment overlay. No installation procedure or new runtime dependency is introduced.

SOURCE-MANIFEST is intentionally updated only for these six files, four modified test files, the new cleanup regression, this report and the unchanged previously unfrozen independent targeted review. Other existing entries remain intact. Exact final source inventories and manifest/report digests are retained in the external synthetic evidence directory to avoid self-referential hashes. This source freeze is not an installed receipt/FREEZE, independent acceptance or a hidden drift refresh.

Independent review of the new cleanup and 80B-default bytes is next. Installed-byte verification, private doctor/authenticated gateway, exact compiler/backend/tokenizer/template verification, rendered tokens, live ownership/janitor/provider checks and pricing remain unperformed gates. The paid-compute authorization boundary remains unchanged.
