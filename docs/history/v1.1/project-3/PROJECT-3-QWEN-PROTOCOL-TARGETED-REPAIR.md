# Project 3 Qwen protocol — R1–R4 targeted repair

Date: 2026-09-16. Offline implementation evidence; Project 3 remains experimental and unaccepted. This report supplements the unchanged [original repair](PROJECT-3-QWEN-PROTOCOL-REPAIR.md) and [independent review](PROJECT-3-QWEN-PROTOCOL-REVIEW.md). It does not replace their historical findings or certify independent acceptance.

## Starting target and delta

The checkout remained on `v1.1/project-3-private-lead-workmode`, HEAD `e168f864eb5ed74d3437102323cdf79804505f06`. At entry it contained the reviewed 12 modified tracked files, eight original additions, and the independent review report. The index was empty. All 20 SHA-256 identities listed in the review matched before editing. A separate 256-file starting inventory includes untracked source, rather than treating HEAD as the repair identity.

The targeted implementation changes only four existing runtime files and the packaged-suite registration. Four new permanent test/fixture files and this report are added. SOURCE-MANIFEST receives an explicit new **source review freeze** for this explained delta and the unchanged historical review report. Existing unrelated hashes, runtime pins, and all original repair bytes outside those five files remain unchanged. No stage, commit, stash, reset, clean, checkout, worktree, merge, push, or PR operation was performed. Historical `ffe539f3d097ff2e652acc842438590a3ba117ea` is not a newly verified installed identity.

## Closure matrix

| Finding | Original permanent reproduction, before production edits | Minimal fix | After / unresolved scope |
| --- | --- | --- | --- |
| R1 | Actual initial/correction HTTP requests lacked the authoritative reason rule; initial and surface-guidance checks failed. Nonterminal and context tests also failed their new guidance assertions. | `decision-surface.mjs` derives the pattern from the authoritative ESCALATION branch and supplies a compact description. `work-mode.mjs` puts that requirement in host-authored state, references it from the system instruction, and includes it in both generic and semantic corrections. It is not an observation or decoder constraint. | Invalid reason then valid escalation: BLOCKED / MODEL_ESCALATION, two attempts, zero effects. A second invalid still stops. Separate invalid → valid read → invalid → valid escalation sequence clears the old correction and grants one allowance on the subsequent decision. Applicable runtime surfaces and context limits pass. Actual Qwen response improvement remains untested. |
| R2 | Exponent overflow escaped as unavailable or was recognized before a typed parse failure. Event nonfinite metadata was accepted or labeled syntax. | `protocol_stream.py` traverses parsed objects/arrays and rejects every nonfinite float before recognition/canonicalization. Completed result: JSON_PARSE/nonfinite and private_lead_result_schema. Event metadata: nonretryable STREAM/nonfinite and answer_incomplete. | Overflow followed by valid correction succeeds; overflow after another invalid class exhausts the same single allowance. Positive/negative overflow, nested containers, literal NaN/Infinity variants, finite controls and duplicate-key distinction pass. No normalization or shared serializer changes. |
| R3 | Read interruption already stopped but produced no ledger diagnostic. | Catch only supported OSError (including TimeoutError) and IncompleteRead from the actual iterator advance; attach fixed STREAM/completion facts. Explicit HTTPError pass-through preserves 400/422 handling. | Before content, after partial content, and after finish/before DONE: one attempted dispatch, zero effects, no correction or retry, one diagnostic. Cancellation, typed parser failures, HTTP decoding rejection and unrelated errors retain separate behavior. |
| R4 | Actual createWorkCommand reviewer failure stopped REVIEWER_UNAVAILABLE with zero protocol diagnostic events. | At the reviewer request boundary capture the host generation/semantic digests, sanitize and ledger the invocation diagnostic once, then rethrow. | Generic-invalid FINAL, malformed JSON, incomplete/timeout and forged diagnostic identities each produce exactly one reviewer-bound diagnostic and no added inference. ACCEPT/REJECT/REVISE controls pass. The separate FINAL.text verdict parser and its existing policy are unchanged. |

R1 communicates exactly `^[A-Z][A-Z0-9_:-]{0,79}$`: a 1–80-character code, first character ASCII A–Z, continuation ASCII A–Z, digits 0–9, underscore, colon or hyphen; no spaces, line terminators or extra prose. Tests explicitly compare the pattern to the authoritative host contract and exercise accepted/rejected boundaries. No fixed reason, model answer example, tool preference or altered acceptance was added. FINAL-only reviewer requests do not receive ESCALATION guidance. The assembled-message tests include the new guidance and active correction at 63999, 64000 and 64001 characters: the first two preserve the essential task and MAC_CAPABILITY provenance; the last stops before inference. This is still a character guard, not tokenizer fit or compaction.

## Permanent regressions and production boundaries

`gate/tests/protocol-targeted.test.mjs` is explicitly registered in `scripts/test.py`; `gate/tests/test_protocol_targeted.py` is picked up by its existing Python discovery. The permanent JavaScript test names are:

- `R1 initial and correction HTTP requests communicate the retained reason rule`
- `R1 guidance matches host acceptance on all applicable runtime surfaces`
- `R1 valid nonterminal result clears correction before a subsequent independent correction`
- `R1 guidance and active correction count toward the exact context boundary`
- `R2 overflow takes JSON_PARSE nonfinite through the real worker and shared correction`
- `R2 nonfinite event metadata is transport rejection without correction`
- `R3 interrupted reads retain fixed facts and never retry or execute`
- `R3 cancellation, HTTP decoding rejection, typed parser and unrelated errors stay distinct`
- `R4 actual reviewer caller logs once with captured reviewer identities`
- `R4 ACCEPT REJECT REVISE and separate verdict parser retain existing policy`

The permanent Python test names are:

- `test_R2_overflow_and_literal_nonfinite_reject_before_recognition`
- `test_R2_finite_numbers_are_preserved_not_coerced`
- `test_R2_duplicate_keys_remain_separate`
- `test_R2_nonfinite_event_metadata_is_not_a_retryable_result`
- `test_R2_finite_event_metadata_remains_valid`

The fixtures materialize the current gate package into a disposable synthetic prefix, write a synthetic freeze/settings/key, then execute the real `worker.py` with `__name__ == '__main__'`. Release verification, signed executor, HMAC authorization, nonce database/replay denial, worker dispatch/error forwarding, backend health/request construction, stream/result parsing, adapter, coordinator and hash-chained ledger remain production code. Only lifecycle and endpoint delivery are synthetic at that boundary. An identical signed replay is denied without another endpoint delivery. Attempts are counted before dispatch independently from success telemetry; this test counter is not the future persistent global attempt ledger.

Lead trajectories substitute workspace snapshots, effects, authority/egress decisions and evaluator outcomes to isolate protocol behavior. The R4 harness uses the actual `createWorkCommand`, its real reviewer caller and ledger, with synthetic workspace, evaluator and remote inputs. Every persisted ledger chain is recomputed; injected content/exception markers are absent. Forged model/error identity fields cannot replace captured reviewer identities. One injected-error case stops before endpoint delivery; its two attempted signed calls correspond to one delivered completion. The separate context-bound test drives the production coordinator directly to calibrate six accumulated observations.

## Before/after evidence and validation

Evidence is retained locally under `/var/folders/fp/s8cnyrrn3r5c72sj_zgm0bn80000gn/T/sanctum-qwen-targeted-xkknq8o4`. It contains starting status, full starting identities, the original source manifest, pre-fix logs and post-fix validation logs. The test harness was written and run before the four production repairs.

- `node --test --test-reporter=tap gate/tests/protocol-targeted.test.mjs`: pre-fix calibrated result **10 tests, 2 pass, 8 fail, 0 skipped** (`before-node-calibrated.log`). An earlier run (`before-node.log`) also had a test expectation typo, REVIEWER_REJECTED instead of the existing REVIEW_REJECTED; that harness-only typo was fixed before the calibrated run, with production bytes still unchanged. The post-fix targeted run passed **10/10**, zero failures/skips (`after-node.log`). Later forged-identity/marker assertions retain those same test names/counts and pass in the focused and packaged runs.
- `.venv/bin/python -B -m unittest discover -s gate/tests -p 'test_protocol_targeted.py'`: pre-fix **5 methods, 7 subtest failures and 4 subtest errors**, no skips (`before-python.log`); the three control methods passed. Post-fix **5/5**, zero failures/errors/skips (`after-python.log`). Subcases are not counted as extra tests.
- `node --test --test-reporter=tap gate/tests/protocol-targeted.test.mjs gate/tests/protocol-repair.test.mjs`: focused **20/20**, zero failures/skips (`focused-node.log`).
- `.venv/bin/python -B -m unittest discover -s gate/tests -p 'test_protocol_*.py'`: focused **15/15**, zero failures/errors/skips (`focused-python.log`).
- Inspected `.venv/pyvenv.cfg` and `uv pip list --python .venv/bin/python` before `npm_config_offline=true npm_config_audit=false UV_OFFLINE=true make deps`: PASS from pinned cache (`deps.log`); Python 3.12.14, Pillow 12.3.0, pypdf 6.18.0, imageio-ffmpeg 0.6.0. No dependency downloads/upgrades or pin changes.

| Complete check (commands from checkout root) | Result |
| --- | --- |
| `make build` | PASS: six plugin builds/validations, capability-manifest check, reviewed OpenClaw runtime pins; `build.log`. |
| `umask 022; make test` | PASS: **305 tests**, zero failures/errors/skips, one full run; `full-test.log`. Breakdown: gate Node 101, gate Python 125, reliability Node 31, reliability Python 11, MCP Node 8, release Python 18, six plugin suites 11 (3+1+2+2+1+2). |
| `make audit` | PASS: 261 source files, zero issues; `audit.log`. |
| `.venv/bin/python -B -c 'from scripts.release_operator import verify; verify(); print("Source manifest and runtime pins match")'` | PASS; repeated after final report-only update and its explained manifest entry update. |
| `git diff --check` | PASS; repeated after final report-only update. |
| Read-only identity/package comparison | All seven generation/semantic pairs equal the independent review; all 38 amendment entries exist; only six original source files differ (four runtime, suite registration, SOURCE-MANIFEST), all other 250 match their starting hashes; `invariants.log`. |

The final report-only update records these results; no implementation changed after the successful full run. Final audit, source-integrity and whitespace checks cover the finished report/freeze. `final-identities.json`, `manifest-delta.json`, `final-status.txt` and `final-integrity.log` in the evidence directory bind the final bytes and confirm the unchanged branch/HEAD and unstaged-only state.

Focused counts are subsets of the full suite and are not added again to its total. The supported build/test/audit side effects were inspected first. Existing cached local synthetic OCI tests are permitted: no new daemon/service, image build/pull, model/provider access or live trajectory is involved. No doctor was run against the old private installation as evidence for these bytes.

## Packaging and retained invariants

The existing amendment list already contains all four changed runtime files and `foundation/protocol-diagnostics.mjs`, newly imported by the reviewer boundary. No runtime dependency or amendment-list edit is needed. The existing permanent packaging-closure regression checks changed runtime files and their relative imports; AST inspection verifies all 38 amendment entries still exist. The signed fixtures independently import/run the current rendered Python worker package and the real JavaScript caller. The amendment itself is not executed: this verifies source packaging, not installed receipts or live rollback.

All seven generation/semantic preflight digest pairs remain equal to the independent review. Runtime/preflight/probe continue to use shared construction, manifest ordering, default four-capability selection and existing generation projection. No schema, canonical acceptance, capability visibility, immutable binding, nonce/replay, authority, exact egress, Source-First, APFS/OCI or at-most-once policy was changed. Passing-test → fresh evaluator → bounded reviewer, hidden FINAL when ineligible, MUTABLE_WORKTREE_V1, valid inability and one-reviewer REVISE semantics remain. The existing diff/status fingerprint limits remain; this adds no full-tree race protection.

Model checkpoint/revision, quantization, backend/runtime pins, sampling/thinking, token/output/context limits, iteration/correction limits, other model tiers, rollback descriptor, and all 11 qualification fixtures/expected outcomes are byte-unchanged from the captured baseline. Qwen remains the substantive reasoner; no hosted planner or substitute model was introduced.

## Exact delta identities

SHA-256 values below distinguish this delta from the original uncommitted repair. `new` means absent from the captured starting inventory. SOURCE-MANIFEST binds this report and the unchanged historical review; its self-hash and this report's final hash are recorded in the external final identity inventory to avoid self-reference. No unrelated manifest entry is refreshed.

| Path | Reviewed starting SHA-256 | Targeted SHA-256 |
| --- | --- | --- |
| `gate/foundation/decision-surface.mjs` | `0a86eed10700e268013306a5274b602833016f9ca27617f1d8cd5c2868e5494c` | `daea5d39e485d68413bf06d28150f8a5c57263dbbd9628130739e06862653cd6` |
| `gate/plugin/work-mode.mjs` | `1ddfa456b8de30111fcb81cd4bc2e311ad1a65c476a31e95c7569e9ab57494fa` | `85e02b40219d838ee59f322b9db1269036609067c6939c1f495b84e5d2d1a321` |
| `gate/src/protocol_stream.py` | `b262c1705b18dfa33726c73255a96d15fb84a6a2e37980e2f478ca545d0453bb` | `1853f0d71fa27bec4717f7b152345da18a7d3494cd6a267e0ce2a2afa4c12813` |
| `gate/plugin/work-command.mjs` | `97b02cc05f5fc771fcdb1743c35edb223d25f15eb7d28be245461f30f52c7d63` | `1052f29b6081d32487803aaaed34d85dbe5f5f46b1867e7d60dec02ec7f3b7e7` |
| `scripts/test.py` | `851e12cdc8e8a1481896196c92e8f5a7c1fe1b1c753cbab8a262030df387bc6a` | `e429d370110cbd88d4866160a3b3f942ee057471656d748f471f5f5a8d0ee574` |
| `gate/tests/fixtures/actual_protocol_worker.py` | `new` | `8b2e39c769205275d3c32b1f551bc10f0c5f5486e78f2c7f4aacc92451d5f3e3` |
| `gate/tests/fixtures/targeted-harness.mjs` | `new` | `1c0a243f74e900e51c562c8be7fcd70a15283db17de2fb6bc1166750abff5d25` |
| `gate/tests/protocol-targeted.test.mjs` | `new` | `c8f4815939f68753760b1cf5b59e2bc40337deb08a7f3b9123c0f407248e70fd` |
| `gate/tests/test_protocol_targeted.py` | `new` | `c2e02678836640abafae6f72a4da19505878571cafad30d7a776722f1c14a8c6` |

Starting SOURCE-MANIFEST: `3619497550dfdbeafc319c9c44497bdad574c88823a51bba7aeebb045fdcd07a`. Starting 256-file inventory SHA-256: `b7f0abd24dc31caae5c09f63c9995814329010e95e7646d628f3892a0db6c657`. The unchanged historical review report SHA-256 is `a93fd03608a6446f88bca1f5b959190da2dcb4e45c0fe92535ce0b102c398cd4`; original repair report SHA-256 is `245c1018c22e9d49e8379b1fc26cb0dcd82cf5f4d132ea56623bc1db9a1977a7`.

## Remaining pre-live work and delta review

The persistent readiness-inclusive attempt budget/ledger and independent supervisor remain unimplemented here. Exact pinned compiler/schema/template/runtime verification remains unverified; no compiler installation or template/tokenizer experiment was run. Native-tool alternatives, context compaction and live runbook execution remain out of scope. Test dispatch counters and successful-call telemetry do not close those prerequisites. No synthetic result explains why the historical 22 responses failed or establishes better Qwen action selection.

The private runtime, credentials, personal-source data, installed receipts, provider resources and legacy tree were untouched. No live run, GPU allocation, runtime amendment or qualification was performed. The next independent delta review should inspect these four minimal runtime edits, the signed-entry fixtures and reviewer identity/redaction assertions, before/after evidence, context boundaries and the explained source freeze. All four findings are implemented and offline-regressed; independent acceptance remains open.

R1–R4 TARGETED REPAIR READY FOR DELTA REVIEW — NO LIVE RUN PERFORMED
