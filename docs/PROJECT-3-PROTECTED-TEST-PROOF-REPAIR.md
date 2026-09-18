# Project 3 protected-test proof-channel repair

Date: 2026-09-17. Status: **OFFLINE VALIDATED — READY FOR FRESH INDEPENDENT REVIEW**. No installation, model invocation, GPU allocation, live coding task or qualification run occurred.

## Reproduced blocker and cause

The blocked independent review preserved an exact contained counterexample. The immutable `oracle.test.js` asserts that the imported value equals 17. Candidate-controlled `value.js` instead contains value 99, writes a correctly serialized `node:test` `test:pass` event naming `/workspace/oracle.test.js` and `independent oracle`, then calls `process.exit(0)` before the original module registers or runs its assertion.

Before this repair, `node:test.run({isolation:'process'})` used the child process's stdout as its event transport. `protected-test-driver.cjs` trusted matching events from that stream, so the candidate-produced event incremented the driver's execution count. The driver then emitted ordinary unauthenticated JSON. The Mac host reported `integrity: PASS`, `executed: true`, `passed: true`, `code: OK` even though the protected assertion never ran.

The defect was confined to the execution-proof channel. Protected original bytes, snapshot integrity, candidate fingerprinting and downstream completion predicates were already present and remain unchanged.

## Trusted-proof design

The protected driver now runs the exact host-selected original entry points with Node's `isolation: 'none'`. Test lifecycle events therefore arrive through the driver's in-memory `TestsStream`; candidate stdout, stderr, TAP, JSON and serialized Node events are not decoded into that stream. The read-only preload is loaded in the driver before repository imports and continues to freeze the assertion and test interfaces.

Before the container starts, the Mac command runner generates a fresh 256-bit key with `os.urandom`. The key is sent through container stdin, read once by the trusted driver before any repository module loads, and reaches EOF before candidate code executes. It is absent from argv, environment, files and mounts. The driver retains it only in an inaccessible module closure.

For each explicitly configured original path/name pair, the driver counts one in-memory start, one real completion, no skip/todo, and one successful completion result. Missing, duplicate, skipped, interrupted or failed lifecycle facts cannot produce a passing proof. Global protected-file failures and skips also reject the run.

After the test stream finishes, the driver serializes the existing bounded proof object and authenticates its exact bytes with HMAC-SHA-256. It writes the framed proof to stderr using bindings captured before repository code loads. The Mac separately captures stderr, requires exactly one well-formed reserved frame, verifies its MAC with constant-time comparison, validates the strict proof schema, and combines it with the container exit status. Invalid, absent, duplicated or malformed proof becomes `executed: false`, `passed: false`; an otherwise-zero container result receives `PROTECTED_TEST_NOT_EXECUTED`.

Repository code may continue to write ordinary stdout/stderr. Such output remains bounded and retained in the output digest but has no authority. A candidate can inject malformed or structurally valid-looking frames, close streams, consume resources or exit early only to make its own run fail. It cannot create a valid MAC, recover the already-consumed key from stdin, or cause candidate output to enter the driver's in-memory event stream. This is a narrow proof-channel boundary, not a claim of arbitrary semantic isolation among JavaScript modules.

The driver avoids mutable collection prototypes when evaluating proof state and captures its serializer, buffer, HMAC and write operations before repository code loads. The existing network-disabled, read-only, capability-dropped, no-new-privileges OCI container, anonymous workspace/driver volumes, nonroot runner identity, CPU/memory/PID/file/output/time bounds and confirmed cleanup are unchanged.

## Changed files

- `gate/runtime/protected-test-driver.cjs`: in-memory original-test lifecycle observation and authenticated proof emission.
- `gate/src/command_runner.py`: fresh stdin key delivery, separate stderr capture, strict HMAC/frame verification and fail-closed classification.
- `gate/tests/test_task_evidence.py`: permanent exact serialized-event regression and focused pass/fail/skip/missing/early-exit/output/proof-injection controls.
- `docs/PROJECT-3-PROTECTED-TEST-PROOF-REPAIR.md`: this implementation and validation record.
- `SOURCE-MANIFEST.json`: explained hashes for the changed code/test/report and the preserved blocked review.

No model/runtime/profile, semantic action schema, correction allowance, budget, authority, egress, Source-First, lifecycle, provider, retirement, fixture or expected-outcome file changed. The existing amendment already packages the driver, preload and command runner; no additional runtime asset or dependency was introduced.

## Counterexample and focused controls

The retained `/tmp/sanctum-review-counterexamples.py` counterexample has SHA-256 `d5e012e0f40cfd7b8e7253269cc71919e2a9b1a991a6b302522a2ace5e54966d`.

Before repair, its fabricated-event row was:

```json
{"integrity":"PASS","executed":true,"passed":true,"code":"OK","executionState":"COMPLETED","containerAbsent":true}
```

After repair, the same script and attack produce:

```json
{"integrity":"PASS","executed":false,"passed":false,"code":"PROTECTED_TEST_NOT_EXECUTED","executionState":"COMPLETED","containerAbsent":true}
```

The permanent regression uses the same immutable oracle, expected 17, incorrect 99, `DefaultSerializer` event bytes and early `process.exit(0)`. It would fail against the reviewed old implementation because that implementation returned true/true.

Focused contained controls establish:

- a real protected assertion pass is executed and passed;
- a real protected assertion failure is executed but not passed;
- skipped and missing named tests are neither executed nor passed;
- early exit, fake TAP and the exact serialized-event attack receive no proof;
- ordinary candidate stdout/stderr does not affect a real pass;
- a candidate-injected proof-shaped frame invalidates rather than replaces or supplements the authenticated frame;
- protected originals remain immutable and candidate tests/new tests retain their prior allowed behavior;
- grade06's weakened candidate suite still accepts incorrect 99 while the original protected oracle rejects it; correct 17 with the original oracle passes.

The existing Work Mode completion tests also reconfirm that protected failure blocks FINAL and explicit passing-test completion before review, evaluator success cannot substitute for original execution, reviewer ACCEPT cannot waive a failure, and later completion after REVISE rechecks the same host predicates and candidate identity.

## Validation

Validation used the existing inspected `.venv`, installed Node dependencies and pinned local OCI image. No dependency installation was performed.

| Command | Result |
| --- | --- |
| `.venv/bin/python -B /tmp/sanctum-review-counterexamples.py` | Three contained observations: skip rejected, missing name rejected, exact fabricated event rejected; all containers absent afterward. |
| `.venv/bin/python -B -m unittest -v gate.tests.test_task_evidence` | 19 passed, zero failures/skips. |
| `.venv/bin/python -B -m unittest -v gate.tests.test_task_evidence.ContainedEvidence.test_live_finding_negative_control_and_correct_solution` | 1 passed. |
| `.venv/bin/python -B -m unittest -v gate.tests.test_command_runner` | 2 passed, zero failures/skips. |
| `node --test --test-reporter=tap tests/task-evidence.test.mjs tests/work-mode.test.mjs` from `gate/` | 45 passed, zero failures/skips. |
| `.venv/bin/python -B -m unittest -v gate.tests.test_qualification` | 13 passed, zero failures/skips. |
| `umask 022; make test` | 474 passed, zero failures/skips: gate Node 120, gate Python 267, reliability Node 31, reliability Python 11, MCP 8, release Python 26, plugin tests 11. |
| `make build` | Six plugin builds/validations passed; reviewed OpenClaw runtime pins and capability manifest matched. |
| `make audit` | 312 files scanned, zero issues. |
| `.venv/bin/python -B -c '... release_operator.verify() ...'` | Source integrity and reviewed runtime pins passed. |
| `.venv/bin/python -B -m unittest -v gate.tests.test_prelive_package` | 1 passed; 53 overlay files, 57 JavaScript edges and 79 Python edges; isolated builders identical. |
| `git diff --check && git diff --cached --check` | Passed. |

An initial non-complete `make test` was intentionally allowed to reach the release gate before the explained freeze update. Every suite before that gate passed, while 18 release-test setups refused the then-stale driver hash. After updating only the three explained code/test hashes, all 26 release tests passed independently and the single final complete packaged run produced the 474-test result above. No test assertion was changed to accommodate the freeze refusal.

## Package and acceptance boundary

The coherent Work Mode overlay already names `runtime/protected-test-driver.cjs`, `runtime/protected-test-preload.cjs` and `src/command_runner.py` in both initial installation and the stopped-gateway `work_integrity` amendment. Package closure proved these exact changed bytes are copied into an isolated rendered package with the source checkout absent from Python module lookup. The private amendment was not executed.

After a fresh independent source review passes, the remaining sequence is unchanged: perform the supported stopped-gateway amendment; verify installed bytes, FREEZE, receipt and doctor; run exactly one fresh unseen real coding task; if it succeeds cleanly, run one unchanged 11-case qualification; confirm provider cleanup; then conduct a fresh final Project 3 acceptance audit. No live result is inferred from this offline repair.

PROTECTED-TEST PROOF REPAIR READY FOR INDEPENDENT REVIEW — NO LIVE RUN PERFORMED
