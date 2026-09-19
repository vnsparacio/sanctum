# Project 3 protected acceptance evidence repair

Status: **OFFLINE VERIFIED — STOPPED AT INDEPENDENT REVIEW**. The fresh targeted reviewer session was blocked by an automated cybersecurity filter before a final verdict. No independent PASS is available; installation and live testing have not started. No new GPU allocation or inference has occurred for this repair. Project 3 remains unaccepted. The historical coding and qualification reports and receipts remain unchanged.

## Finding and acceptance boundary

The preceding qualification produced 11 expected terminal outcomes, but grade06 changed an independent expected value into a value derived from the implementation. A wrong implementation then passed the weakened test. Reviewer ACCEPT did not detect this. The actual final implementation also passed the original test; that does not restore the lost verification invariant. The historical 11/11 is therefore not clean acceptance evidence.

This repair makes the Mac task contract authoritative. It changes no Qwen model, runtime, prompt, semantic action schema, correction allowance, inference budget, fixture goal, bug, malicious instruction, case count or expected terminal outcome. Reviewer judgment remains advisory.

## Host contract and identity

`sanctum-task-protection/v1` has exactly `schema`, `protected`, `mutable`, `mutable_tests`, `allow_new` and `acceptance`. Paths are explicit relative paths, never inferred from file names. Protected paths bind their original presence or absence, bytes, digest, regular-file type, permission mode, device and inode. The snapshot also binds task ID, absolute host workspace identity and contract digest. A protected file cannot overlap a declared mutable file. Mutable implementation paths and mutable test paths permit changes; `mutable: "*"` permits changes to all existing nonprotected files. `allow_new` controls additions.

`acceptance` is null or the bounded `node-test-v1` runner with explicit protected entry paths and expected test names. These are host configuration, not model arguments. Originals are read without following links and retained as content-addressed, read-only blobs in private host state outside the model workspace; a private manifest digest binds them to the task record. Inventory is bounded to 10,000 entries and 128 MiB. Ambiguous case/Unicode identities, changed symlinks and hard links fail closed. An observed integrity violation is latched in private state, so restoring content cannot waive it.

Patch policy examines both forward and reverse Git path summaries before mutation, including both ends of renames. A rejected proposal has no effect and consumes no schema correction. A mutation actually observed by the integrity check causes fixed `BLOCKED / PROTECTED_INPUT_MODIFIED`; the model and reviewer cannot repair or waive that task state.

## Evaluation and execution

Both FINAL and a model-requested passing test use the same completion gate:

1. Check host snapshot integrity and capture the complete candidate fingerprint.
2. Run existing candidate evaluators and diff/status checks.
3. Build a bounded temporary acceptance view outside the mutable workspace from candidate files plus the original protected files. Preserve candidate additions and mutable tests. Do not follow repository symlinks.
4. Copy that view into the existing pinned, network-disabled OCI runner. An isolated host driver selects exact original entry points; candidate scripts and discovery cannot select them away. The parent counts named test execution events independently of candidate stdout. Failed assertions count as executed but failed; missing/skipped tests, early process exit, fake TAP and malformed execution proof fail closed.
5. Require separate candidate-test and original-test success facts, snapshot binding and unchanged candidate fingerprint. Recheck integrity after evaluation.
6. Supply bounded integrity/execution/result facts to the existing one-shot reviewer, if configured.
7. Recheck integrity and candidate identity immediately before COMPLETE, including after ACCEPT and after a prior REVISE has consumed the reviewer. Apply existing cancellation/budget guards again.

The host driver and preload are copied into a separate anonymous OCI volume, owned by root and not writable by the nonroot candidate process. No host directory is mounted. The preload locks Node assertion and test interfaces before repository imports. Existing image identity, user, network, CPU/memory/PID/output/time limits and confirmed container cleanup are retained. All test code executes within that container.

File integrity, named original-test execution and test result are distinct host facts. Hashes do not establish execution semantics. Fixed entry points and execution events detect skipped discovery, replacement scripts and missing imports; assertions still determine the correctness covered by each oracle. This is not a proof of arbitrary software correctness, exhaustive test coverage or resistance to every possible JavaScript runtime exploit. Mutable imports can legitimately change behavior; the original oracle must independently test that behavior. The configured fixtures use direct independent assertions. The runner rejects tested attempts to replace assertion/test APIs, but does not claim a general semantic sandbox between arbitrary JavaScript modules within one test process.

## Fixture protection mapping

Every unchanged fixture explicitly protects `index.test.js` and the original presence/absence of `package.json` (module interpretation). Only grade06 originally contains the latter. Implementation files remain mutable and new regression tests remain allowed. No fixture requires editing an existing oracle; explicitly mutable test development is exercised separately by synthetic tests.

| Fixture | Original expected test name | Mutable implementation purpose |
| --- | --- | --- |
| grade01 | add | Arithmetic bug |
| grade02 | even | Existing failing unit test |
| grade03 | multi | Cross-file behavior |
| grade04 | api | API/schema mismatch |
| grade05 | same | Behavior-preserving refactor |
| grade06 | config | Configuration value/type |
| grade07 | first item | Ordered collection debugging |
| grade08 | stable | Approval-required stop |
| grade09 | safe | Malicious repository instructions |
| grade10 | stable | Impossible authority request |
| adversarial | container boundary | Existing integrated containment probe |

The fixture payload digest remains `e67ed7a5798f3fdae524ba5f570021f6a7b7874d54cb725b1feffeaa308aa831`. Qualification refuses missing or changed host protection contracts before starting cases. Its new receipt fields separate integrity, original execution/pass, candidate execution/pass, evaluator result and reviewer disposition. COMPLETE requires all predicates; even expected noncompletion requires preserved input integrity. Historical receipts are not reinterpreted.

## Regression and validation

The synthetic grade06 regression has an independent expected integer 17, a weakened test deriving expectation from actual, and an incorrect integer 99. The weakened candidate suite passes both values; the original oracle rejects 99 in the actual pinned OCI runner. The weakened task is latched as an integrity failure. The untouched oracle with the correct implementation passes. New regression files and explicitly mutable test files remain permitted.

Adversarial coverage includes overwrite, delete/recreate, rename, symlink, hard link, case/Unicode ambiguity, file mode/type, staging, generated replacement, discovery/script bypass, fake stdout, early exit, missing/moved/wrong imports, module configuration and assertion API mutation. Coordinator tests cover every completion route, evaluator/reviewer timing, one reviewer after REVISE, stale/cross-task/missing evidence, original execution failure and bounded receipt fields. Signed host-only operations retain exact task/profile authority and replay rejection; they are absent from the model action surface.

The existing dependency environment was inspected before `make deps`; dependency installation passed. The final packaged suite passed **471 tests, zero failures and zero skips**: gate Node 120, gate Python 264, reliability Node 31, reliability Python 11, MCP Node 8, release Python 26, plugin tests 11. This includes 16 focused Python integrity/contained tests, eight focused completion/receipt tests, qualification contract tests, and existing protocol/pre-live/security suites. The actual pinned OCI grade06 negative control and private installed-driver permissions regression passed. Package closure passed for 53 overlay files, 57 JS edges and 79 Python edges using isolated imports/builders. `make build`, `make audit`, source-integrity/runtime-pin verification and whitespace checks passed. The publication audit found zero issues. The initial full run passed 469 tests; two additional installation/failure-classification regressions brought the final total to 471. During focused development, tests exposed the Git rename-summary omission and fixture issues; all were repaired before these passing gates. Independent review remains required before installation.

## Explained source freeze and installation closure

This repair explicitly freezes only these additions/changes beyond the preserved starting manifest:

- `gate/src/task_evidence.py`: typed host contract, private snapshots, prepatch checks and original execution view.
- `gate/runtime/protected-test-driver.cjs`, `protected-test-preload.cjs`: fixed original entry points and locked assertion/test interfaces.
- `gate/src/command_runner.py`, `gate/worker.py`, `gate/src/authority.py`: contained execution and signed host-only evidence operations.
- `gate/plugin/work-mode.mjs`, `work-command.mjs`, `work-ledger.mjs`: mandatory completion guards, evaluator/reviewer facts and typed receipts.
- `gate/qualify_work_mode.py`: explicit fixture contracts and separate evidence predicates.
- `scripts/configure.py`: fixed-file, named-freeze `work_integrity` amendment and explicit task protection at profile registration.
- `scripts/upgrade_work_mode.py`: package closure and host contracts for initial Work Mode installation.
- `scripts/test.py`: include the new completion suite.
- `gate/tests/test_task_evidence.py`, `task-evidence.test.mjs`, `test_qualification.py`, `test_prelive_package.py`, `work-mode.test.mjs`, `protocol-repair.test.mjs`, `fixtures/task-evidence.mjs`, `fixtures/targeted-harness.mjs`, `tests/test_release.py`: synthetic regressions, explicit fixture host callbacks, package/install/rollback contracts.
- This report.

No generic refresh of unrelated hashes is permitted. Model/runtime pins remain separately unchanged. The supported package overlay includes the new Python module and both driver assets; isolated package closure is tested without importing source from the checkout.

`scripts/configure.py` accepts a standalone `work_integrity` proposal naming the exact reviewed SOURCE-MANIFEST digest. It requires a stopped gateway, confirmed retired 80B, offline lead with no ownership uncertainty, no leases or unfinished experiments, disabled autostarts and a loaded independent janitor. It installs ten fixed runtime files and updates only the explicit task contracts in existing profiles, preserving all other settings and budgets. Installed FREEZE and receipt are updated through the existing private write-ahead transaction. Rollback uses that exact transaction while the gateway is stopped and compute is cleaned up; originals/private task receipts are retained. No installation has occurred yet.

## Remaining gates and final stop

After full offline validation, a fresh independent Astra reviewer must attempt to falsify the protection/execution/completion/install claims. Blockers must be repaired and re-reviewed before any live run. Only then: supported stopped-gateway amendment, byte/FREEZE/receipt verification, doctor, authenticated bridge and `/work`, installed non-inference schema/runtime preflight, and exact runtime identity verification before inference.

Run exactly one fresh unseen small coding task. If any gate fails, stop and do not run qualification. If clean, run exactly one unchanged 11-case qualification with the new separate host predicates, without tuning, case retries or larger inference budgets. Preserve all outcomes, confirm provider allocation/lease absence, keep 80B retired and persistent volumes, and stop for a fresh final independent Project 3 audit. Do not merge, promote or self-accept Project 3.

## Independent-review checkpoint

A separate GPT-6 Astra / High reviewer was launched with no inherited conversation or implementation reasoning. It received the owner requirements and source references, with read-only source and synthetic offline validation scope. The reviewer reported that the completion gates and fixture contracts looked coherent during its work, then its session failed with: “This content was flagged for possible cybersecurity risk.” That partial progress is not an approval. The review service returned no final PASS/BLOCKED source verdict. No attempt was made to bypass that filter.

Per the owner’s Phase 11 gate, work stops here for a fresh independent Astra review of this exact repair. Do not install or allocate compute on the basis of the author’s checks. The private runtime remains at its pre-repair installation. A private unseen coding baseline and host contract have been prepared; its bounded contained baseline test failed as expected, and it has received no model inference. It must remain unseen until review passes and the supported amendment is installed. The 11-case qualification has not been rerun. The requested final success state has **not** been reached.
