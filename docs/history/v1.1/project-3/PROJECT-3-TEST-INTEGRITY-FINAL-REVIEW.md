# Project 3 final test-integrity review

Date: 2026-09-17. **BLOCKED: the fabricated-event defect remains reproducible in the current working tree.** This is an independent review, not an implementation repair or live acceptance.

## Review target and delta

Reviewed branch: `v1.1/project-3-private-lead-workmode`, HEAD `e168f864eb5ed74d3437102323cdf79804505f06`. The review target includes the intentionally uncommitted working tree. Initial inventory: 31 modified tracked files, 63 untracked files, zero staged files. These accumulated Project 3 changes are not attributed to the latest reported repair.

Read `AGENTS.md`, the live baseline, qualification report and test-integrity repair report. Inspected the current protected driver, preload, contained runner, task-evidence implementation and retained integrity tests, plus the preceding review's available history and temporary counterexample.

No source/test delta fixing the fabricated-event finding could be identified in this checkout. The driver still directly counts Node runner events; the permanent false-output regression still prints TAP text. The current driver/preload timestamps are 15:49 UTC, runner/test timestamps 15:58 UTC, and repair report/source manifest timestamps 16:02 UTC. The retained fabricated-event reproduction is dated 16:17 UTC. Timestamps alone do not prove history, but the current source and fresh reproduction contradict the premise that the defect has been repaired here. No later repair report was found among the working-tree reports. A different or unsaved repair cannot be accepted as this source.

Current SHA-256 identities:

| File | SHA-256 |
| --- | --- |
| `SOURCE-MANIFEST.json` | `c4818902ca1547939c84e1dd52bab7ceb7b5f233ceed7ae154c8dcc3a2fda9e5` |
| `gate/runtime/protected-test-driver.cjs` | `c112904b5a428f33dbccd316e7784954b7320c7d94bb35a23af1943e5fbfdc1a` |
| `gate/runtime/protected-test-preload.cjs` | `ea5e8666354fca6944d758fcfe6a8d5b6b0b10646649c2fffa6569c9bccbb31b` |
| `gate/src/command_runner.py` | `6256c2c5144d6e0196d676cc3b35faadda0ae42c2b05a0d78b590cf43f842f96` |
| `gate/src/task_evidence.py` | `7950a92fe32bce9eecd4c07cadda5a56242b26d330326dd313d7db5496033ed0` |
| `gate/tests/test_task_evidence.py` | `05752dc1d8c11a6908db52a262fb07f96d698a14215a10e27e9519057a22f47d` |

## Blocking finding: candidate output still supplies execution authority

**P1 — `gate/runtime/protected-test-driver.cjs`, lines 9–19.** The parent consumes `node:test.run()` events and accepts matching `data.file` and `data.name` as execution proof. In the existing process-isolated runner, the candidate can write a serialized Node test event directly to its stdout. That event reaches this loop as `test:pass`; its claimed file and test name are not independent evidence that the original assertion ran.

The retained synthetic counterexample preserves the original `oracle.test.js`, whose assertion requires value 17. Its mutable imported implementation writes a fabricated matching event and exits zero during module evaluation, before the original test registers or executes. Its declared value is the incorrect 99. No protected-file mutation or assertion-API replacement is needed.

Fresh execution through the actual existing network-disabled contained runner returned:

```json
{"integrity":"PASS","executed":true,"passed":true,"code":"OK","executionState":"COMPLETED","containerAbsent":true}
```

The output digest was `e727cf5668e181d42573a1154a549d5a63588600b5af7c08d28049b344a96f79`, matching the retained reproduction. The parent generates valid final JSON from the fabricated event. Consequently, strict JSON validation at `gate/src/command_runner.py:118–126` accepts it, and `gate/src/task_evidence.py:184–186` returns the false execution/pass facts with passing integrity and candidate identity. Host-owned driver bytes and read-only originals do not repair this proof-channel defect.

This directly violates the requested acceptance invariant. It does not depend on a broader claim about arbitrary JavaScript semantic isolation. An end-to-end COMPLETE reproduction is unnecessary to establish the specifically prohibited host `executed: true` / `passed: true` result.

Smallest required correction: replace or supplement the event-counting proof with host-controlled observation of the designated original test's execution and outcome that candidate output cannot fabricate. Bind that observation to the original test identity and fail closed on absent, skipped, failed, premature or malformed execution. Retain this exact serialized-event counterexample as a regression; fake TAP alone is insufficient. Review the corrected bytes and explicitly freeze them before installation. No correction was made in this review.

## Validation performed and stop

Exact reproduction command, from the repository root:

```sh
.venv/bin/python -B /tmp/sanctum-review-counterexamples.py
```

The existing script's SHA-256 is `d5e012e0f40cfd7b8e7253269cc71919e2a9b1a991a6b302522a2ace5e54966d`. It was inspected and reused without modification. It produced three contained diagnostic results: skipped original rejected; missing designated name rejected; fabricated event incorrectly accepted. All three returned `containerAbsent: true`. The script exits zero because it prints observations rather than asserting rejection; that exit code is not a passing security or correctness verdict.

`git diff --check` and `git diff --cached --check` both passed. Branch, staged/unstaged/untracked inventory and targeted file hashes were recorded with read-only commands.

Following the explicit instruction to report a concrete blocker and then stop, no remaining acceptance tests were run: zero complete packaged runs in this conversation; no fresh grade06, completion/reviewer, qualification-contract or package-closure verdict; no build, audit or source-integrity/runtime-pin verification. Historical passing counts are not presented as fresh evidence. Completion-path acceptance and absence of unrelated regressions are therefore not certified.

No source, test, fixture, manifest, runtime, dependency or Git state was changed. Only this requested report was added. No installation, model invocation, GPU allocation or live qualification occurred. The installation/live-acceptance sequence remains gated on targeted repair and a fresh independent passing review.

FINAL TEST-INTEGRITY REVIEW BLOCKED — TARGETED REPAIR REQUIRED
