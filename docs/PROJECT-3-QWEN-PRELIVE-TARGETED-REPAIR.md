# Project 3 Qwen pre-live readiness — R1/R2 targeted repair

Date: 2026-09-16. Source repair only; Project 3 remains unaccepted. This supplements the unchanged [independent pre-live review](PROJECT-3-QWEN-PRELIVE-REVIEW.md). Its blocked disposition remains historical evidence, not an acceptance of the new bytes.

## Plan and scope

The owner requested that both findings be planned and fixed without another permission step. Work remained on `v1.1/project-3-private-lead-workmode`, HEAD `e168f864eb5ed74d3437102323cdf79804505f06`, preserving the larger uncommitted repair and empty index. The starting source inventory contains 274 files, including the independent review. Starting SOURCE-MANIFEST SHA-256: `be567a4f22f0bdfcbe4ccbc1dd9fd5a2242f2410f9665351ad3561869ea5ced2`.

The implementation plan was to serialize ordinary lease admission with experiment ownership, require zero leases in both release stores before terminal cleanup, use a fresh backend grammar for each representative, and verify these changes with offline regressions and the supported suite. No private installation, gateway operation, provider action, inference, coding task, qualification run or Git index/history operation is part of this repair.

Synthetic inventories, copies of the five starting runtime files, test logs and the final delta are retained in `/tmp/sanctum-prelive-targeted-repair-20260917`.

## R1: admission and terminal lease reconciliation

Ordinary PRIVATE_LEAD and PRIVATE_80B `acquire()` now take the PRIVATE_LEAD experiment ledger's SQLite transaction before touching either lease store. An unresolved experiment refuses admission before inserting or incrementing a lease. The same transaction serializes experiment creation and terminal reconciliation. The lock order is PRIVATE_LEAD followed by PRIVATE_80B; it is never held over provider calls, readiness or model transmission.

Experiment creation rejects existing PRIVATE_LEAD leases. The installed `experiment_control.py create` path additionally supplies the ordinary release store, so PRIVATE_80B leases also prevent creation. Active, inactive and expired rows all count until their owner reconciles them. The low-level ledger's optional `ordinary_root` supports isolated ledger tests; production creation supplies it explicitly, covered by an actual control-command regression. Concurrent ordinary acquisition and production-equivalent creation cannot both win: either the ordinary lease exists and creation refuses, or experiment ownership exists and acquisition refuses.

After provider-confirmed absence and verified diagnostic worker exit, the supervisor may remove only the diagnostic lease bound to that experiment. It checks both stores while holding the admission transaction. Any other row retains `CLEANUP_REQUIRED / LOCAL_PENDING`; no terminal cleanup claim is made. Unknown ordinary leases are preserved regardless of activity, expiry or matching scope in the other release. This is deliberately conservative: old unresolved lease rows need owner reconciliation rather than automatic deletion without worker identity evidence. After that reconciliation, a later sweep can confirm zero leases and complete.

Without an unresolved experiment, ordinary lease counts and idle retention remain unchanged. The admission lock does initialize the shared diagnostic metadata store when needed, including on the ordinary 80B path. Existing lifecycle retry/model policy is unchanged.

## R2: independent grammar state for branch reachability

`verify_exact_runtime.py` now obtains a fresh grammar from the selected backend's `compile_grammar()` for each representative of each full generation/semantic schema. It does not reuse/reset a wrapper that has consumed EOS. The pinned backend may reuse immutable compiled context internally; per-request matcher state is separate.

No backend selection, vLLM/compiler version, schema, representative, model, tokenizer, template or token limit was changed. Invalid representatives and compilation failures still fail the aggregate result, and each backend is destroyed after its surface checks. Exact runtime identities and NOT_RUN gates remain unchanged.

The verifier regression exercises its actual control flow and request builder with synthetic external package/tokenizer adapters. Its fake grammar models the pinned xgrammar wrapper's termination flag surviving reset, then verifies all successive branches and EOS through fresh grammar instances. This is orchestration regression evidence, **not exact compiler, tokenizer or token-headroom proof**. No compiler package was installed and no real environment pass is claimed.

## Regression evidence

The new `gate/tests/test_prelive_targeted.py` is discovered by the existing packaged Python test command; no suite-registration edit is needed. Its 12 methods cover:

- Both ordinary releases and infer/propose admission during active and cleanup-required experiments, with zero new lease rows.
- Rejection of existing active/inactive/expired leases at creation and the installed control command's other-release check.
- Provider-confirmed absence with leftover leases in either store; preserved rows, pending cleanup, then completion after explicit synthetic reconciliation.
- No-allocation cleanup, matching scopes in different stores, and a still-live diagnostic worker.
- Ordinary idle-lease behavior with no experiment.
- Separate processes racing ordinary acquisition against creation for both releases and both launch orders.
- Full verifier orchestration with successive branches/EOS, an invalid branch, and compiler exceptions with backend destruction.

The first pre-edit regression run exposed a test-fixture problem: the old ordinary finally path could retire the fixture experiment between subcases, allowing a later subcase to enter ordinary readiness. That synthetic run was terminated, and the admission test was isolated from supervisor sweep (which has its own tests). Child streams were also closed explicitly. No private service or real provider was involved.

The corrected initial 11-method suite was rerun in an isolated copy of the gate package with all five runtime files restored from their captured pre-edit bytes. It failed as expected (16 failed assertions and 11 errors across subcases, including the then-absent `ordinary_root` API and residual fixture rows after failed assertions). These are not reported as 27 independent product bugs. The same 11 methods passed against the repair. A twelfth regression subsequently verified the actual installed control path's second-store check. Final test results are recorded below.

## Verification and explicit source freeze

The existing dependency environment was inspected before cache-only bootstrap: Python 3.12.14, Pillow 12.3.0, pypdf 6.18.0 and imageio-ffmpeg 0.6.0. No runtime pin, lockfile or model/profile change is intended.

| Check | Result |
| --- | --- |
| `npm_config_offline=true npm_config_audit=false UV_OFFLINE=true make deps` | PASS from cache after inspecting the existing venv. |
| `.venv/bin/python -B -m unittest discover -s gate/tests -p 'test_prelive*.py'` | 54 PASS, zero failures/errors/skips; includes all 12 repair regressions and isolated package closure. |
| Isolated package closure | PASS: 46 overlay files, 56 JS import edges, 65 Python import edges; production artifacts identical outside the source module path. |
| `make build` | PASS: six plugin builds/validations, manifest and cached OpenClaw pins. |
| `node --test --test-reporter=tap gate/tests/prelive.test.mjs gate/tests/protocol-repair.test.mjs gate/tests/protocol-targeted.test.mjs` | 28 PASS, zero failures/skips. |
| `.venv/bin/python -B -m unittest discover -s gate/tests -p 'test_protocol_*.py'` | 15 PASS, zero failures/errors/skips. |
| `umask 022` then `make test` | **367 PASS**, zero failures/errors/skips. Gate Node 109, gate Python 179, reliability Node 31, reliability Python 11, MCP Node 8, release Python 18, plugin suites 11 (3+1+2+2+1+2). |
| `.venv/bin/python -B /tmp/sanctum-prelive-independent-review-20260917/counterexamples.py Counterexamples.test_cleanup_does_not_report_confirmed_with_ordinary_rejected_lease` | Original R1 counterexample now PASS: one synthetic delete, confirmed absence, zero leases, zero active requests. |
| `.venv/bin/python -B /tmp/sanctum-prelive-independent-review-20260917/ledger-controls.py` | Original six independent ledger controls PASS, including crash/restart, concurrent final slot, readiness/proposal race and cancellation. |
| `make audit` | PASS: 276 source files, zero issues; repeated after final report update. |
| `.venv/bin/python -B -c 'from scripts.release_operator import verify; verify(); print("Source manifest and runtime pins match")'` | PASS; repeated against the final explicit source review freeze. |
| `git diff --check` plus added-file whitespace scan | PASS. |
| Starting inventory and pin comparison | Exactly five runtime files plus SOURCE-MANIFEST changed; all other 268 starting files unchanged. Two files added: the regression module and this report. Index/branch/HEAD unchanged; runtime, model, settings and dependency pins unchanged. |

SOURCE-MANIFEST is intentionally updated as a new **source review freeze** for exactly five explained runtime changes (`src/experiment.py`, `src/lifecycle.py`, `src/experiment_lifecycle.py`, `experiment_control.py`, `verify_exact_runtime.py`, all under `gate/`), the new regression file, this report and the unchanged independent review. Other recorded entries are preserved. This is not an installed freeze, independent acceptance or permission for paid compute.

The full suite ran once. Focused counts are subsets of the 367; the seven reused independent checks are separate. No implementation changed after the full run. Final documentation/freezing changes received audit, integrity, inventory and whitespace verification. The supported suite used temporary synthetic state and its existing cached local OCI environment; it did not amend the owner candidate or start a model/provider workload.

Every changed runtime file is already in the existing 46-file coherent amendment overlay. No new runtime dependency or manual-copy installation procedure is introduced. A future installation must use the supported stopped-gateway reversible amendment after independent source review and the remaining gates. No amendment or doctor against the old installation was performed here.

## Remaining gates

Independent review of these repair bytes remains required. Installed byte verification, doctor/authenticated gateway checks, actual exact compiler/backend/tokenizer/template execution and rendered-token measurement remain unperformed. Provider pricing, ownership and janitor state have not been inspected. Spending still requires the separate explicit owner authorization specified in the original mission; this repair does not authorize allocation or microprobes.

R1/R2 PRE-LIVE TARGETED REPAIR READY FOR INDEPENDENT REVIEW — NO INSTALLATION OR LIVE RUN PERFORMED
