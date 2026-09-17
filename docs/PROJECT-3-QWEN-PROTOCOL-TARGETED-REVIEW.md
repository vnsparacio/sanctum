# Project 3 Qwen protocol — independent R1–R4 delta review

Date: 2026-09-16. **R1–R4 source acceptance passes. Pre-live readiness does not.** No residual blocker was reproduced within the four targeted findings. Fifteen independent tests, the 35 focused protocol tests, and all 305 packaged tests pass. This accepts only the targeted source delta against the earlier offline review; Project 3 remains experimental and unaccepted.

## Reviewed state and evidence

Reviewed the canonical checkout identified in [the live baseline](V1.1-LIVE-BASELINE.md), remote `https://github.com/vnsparacio/sanctum.git`, branch `v1.1/project-3-private-lead-workmode`, HEAD `e168f864eb5ed74d3437102323cdf79804505f06`. Local tracking comparison was 11 commits ahead, zero behind; no fetch was performed. The index was empty. At entry there were **12 modified tracked files and 14 untracked files**, counted individually with `git status --porcelain=v1 -uall`. The larger repair remains uncommitted. Staged, unstaged and untracked state were all included; HEAD alone was not the target.

Read AGENTS.md, the live baseline, the original repair, the independent review and the targeted repair report completely. The earlier review blocked on four bounded findings; this report reviews their repair without reopening the larger design. Historical installed identity `ffe539f3d097ff2e652acc842438590a3ba117ea` was not reverified.

Independent scripts, inventories, diffs and logs are under `/tmp/sanctum-qwen-delta-review`. Source-only historical evidence was inspected under `/tmp/sanctum-qwen-review.OFTOWm` and the targeted report's `/var/folders/fp/s8cnyrrn3r5c72sj_zgm0bn80000gn/T/sanctum-qwen-targeted-xkknq8o4`. These contain synthetic test artifacts, not owner runtime receipts. No private prefix, credentials, personal sources, private model outputs, raw private receipts, provider resources or legacy tree were inspected.

The historical isolated package retains exact copies of the four pre-R1–R4 runtime files. Each copy's SHA-256 matches the independent review's recorded baseline. Diffing those authenticated copies against this checkout yields the exact runtime delta, saved as `runtime-delta.patch` (SHA-256 `03e820a27776cdb87d6f378d00017d89b7bc36aa9efa2c4daacf4c606cd280be`). Removing only the new targeted-test registration from current `scripts/test.py` reconstructs its recorded baseline hash. This avoids attributing the entire HEAD diff to R1–R4.

No implementation, permanent test, historical report, source manifest, runtime configuration or pin was edited during review. This report is the only source addition. No stage, commit, stash, reset, clean, branch switch, rebase, merge, push, PR or amendment occurred.

## Findings and closure, in prior severity order

**No new actionable R1–R4 finding.** The four prior P2 findings are closed for this source delta. Acceptance rests on inspected changes and independent counterexamples, not the implementation report or the packaged count alone.

### R1 — authoritative ESCALATION guidance: closed

`gate/foundation/decision-surface.mjs:13–19` obtains the pattern from the ESCALATION branch of the authoritative `workIntentSchema`; it does not introduce another regex constant. Its prose accurately describes that pattern. The permanent test compares against the host schema and tests acceptance. The authoritative schema and host validators themselves are unchanged.

`gate/plugin/work-mode.mjs:128` includes `resultRequirements` in host-authored state and explicitly identifies it in the system instruction. Lines 141 and 154 include the same requirements in generic-result and semantic corrections. It is separate from untrusted task/observation data. Captured actual backend HTTP requests preserve the initial instruction, state and correction. Ordinary/research eligible and ineligible surfaces and the post-patch test-only surface carry the rule. FINAL-only reviewer requests do not. No answer, preferred escalation code, task example, capability preference or qualification hint was added to runtime guidance. Synthetic answers remain in test fixtures.

The generation schema still omits the reason pattern; all seven generation/semantic identity pairs are unchanged. This is host-authored format guidance, not new decoder constraints or verified grammar support.

Independent tests checked both generic and Work Intent acceptance for lengths 1, 80 and 81; empty, lowercase, digit-first, leading/trailing spaces; LF, CR, CRLF, NUL, non-ASCII, U+2028 and U+2029; allowed digits/underscore/colon/hyphen; and every ASCII byte as a continuation character. Accepted values exactly match the requested ASCII code contract.

Signed trajectories confirm invalid reason → corrected valid ESCALATION reaches `BLOCKED / MODEL_ESCALATION`, two dispatch attempts and zero effects. Two consecutive invalid results stop `REPEATED_INVALID_PROPOSAL`. Invalid → valid read/list → independent invalid → valid escalation receives a new single correction; stale correction is absent after the valid nonterminal result. A semantic argument error also receives the requirements.

Independent accumulated-observation tests calibrated 63999, 64000 and 64001 serialized user-message characters, both without and with active correction. The first two preserve the task, guidance and `MAC_CAPABILITY` provenance; the last stops `MODEL_CONTEXT_LIMIT` before another invocation. Guidance and correction consume the existing limit. This remains a character guard, not rendered-token measurement or context compaction.

### R2 — nonfinite parsed numbers: closed

`gate/src/protocol_stream.py:5–13` traverses the parsed root, object values and array members and rejects nonfinite floats. `parse_result` invokes it at lines 89–96 before result-kind recognition and before backend canonicalization. There is no normalization, clamping, substitution or change to the shared serializer.

Independent parser cases covered `1e400`, `-1e400`, NaN, Infinity, negative Infinity, and overflow just above the largest finite binary64 value, at root and within nested arrays/objects. Each completed result produces `private_lead_result_schema` and fixed `JSON_PARSE / nonfinite / FAILED` facts. Finite controls included positive/negative maximum finite binary64, `5e-324`, ordinary integers, negative zero and the existing underflow behavior of `1e-400`; Python types and negative-zero sign remain unchanged. Duplicate keys retain `duplicateKey`, independently of the nonfinite predicate.

One independent signed case used an ESCALATION-shaped object with a private-looking extra key containing nested `-1e400`. The actual frozen worker entry point verifies its synthetic release, authorizes the signed request and consumes its nonce. The backend rejects before generic recognition/serialization; worker allowlisting forwards the fixed diagnostic; the adapter maps `private_lead_result_schema` into the existing correctable result-shape error; the coordinator logs `JSON_PARSE/nonfinite` and uses one correction; the next valid escalation terminates with no effect. Overflow after a parse, generic or semantic invalidity consumes the same allowance and stops on the second invalid result. Exact signed replay is denied without another endpoint delivery.

SSE/event metadata is checked at lines 62–64. Nested nonfinite metadata yields `answer_incomplete` and `STREAM/nonfinite`, one dispatch and no correction. Finite usage metadata remains accepted. Diagnostics and hash-chained ledger rows contain neither offending numeric strings nor injected private markers or arbitrary error strings.

### R3 — interrupted reads: closed

`gate/src/protocol_stream.py:49–54` catches only `OSError` (including TimeoutError) and `http.client.IncompleteRead` from the iterator advance. HTTPError is explicitly rethrown first. Parsing and unrelated computation are outside that catch. The resulting fixed facts are `STREAM/completion`, `INCOMPLETE`, `BEFORE_PARSE`, with the observed finish status when available. Exception text and partial IncompleteRead bodies are not copied.

Independent direct and signed tests exercised OSError, TimeoutError and IncompleteRead before content, after partial JSON content, and after `stop` but before DONE. Every signed case made exactly one attempted dispatch and one endpoint delivery, produced one diagnostic, executed zero effects, and created no correction or inference retry. The signed replay checks added no endpoint delivery or effect.

Direct tests proved cancellation Refused, another typed Refused, RuntimeError, ValueError, and HTTP 400/422 retain their identity at this boundary. Focused signed tests additionally confirm cancellation, structured-decoding HTTP rejection, malformed event rejection and unrelated backend errors remain distinct. Malformed *completed* JSON remains a correctable `JSON_PARSE/syntax` error. Private-looking exception/body markers disappear before persistence. This repair adds observability without changing the existing uncertain-transport stop policy.

### R4 — reviewer diagnostic forwarding: closed

The actual path is `createWorkCommand` → reviewer request → PRIVATE_LEAD/generic adapter → signed worker/backend → adapter exception → reviewer catch → task ledger → coordinator `REVIEWER_UNAVAILABLE`. At `gate/plugin/work-command.mjs:126`, generation and semantic digests are captured into local constants before the awaited invocation. Lines 128–132 sanitize an existing invocation diagnostic, append it once using those constants and rethrow. The coordinator's reviewer failure handler at `gate/plugin/work-mode.mjs:98` stops without a second append or reviewer retry.

Independent actual-caller tests covered malformed JSON, generic-invalid FINAL including NUL, interrupted/incomplete response, forged model fields, forged exception diagnostics, and private markers. Every diagnosed invalid invocation logs exactly one sanitized reviewer-bound diagnostic before `REVIEWER_UNAVAILABLE`, with one lead attempt and one reviewer attempt. The injected pre-backend error case has only one endpoint delivery in total, as expected. Reviewer schema identity differs from the lead identity and equals the captured FINAL-only surface.

A separate direct-transport test forged both outer error identities and diagnostic identities, attempted to mutate the outgoing request, and verified the ledger against the captured values. The adapter's request and nested workIntent are frozen; attempted mutation throws. The implementation neither trusts returned digest fields nor recomputes identity from mutable state after failure.

ACCEPT, REJECT and REVISE controls add no failure diagnostic. ACCEPT completes, REJECT stops `REVIEW_REJECTED`, and REVISE retains the existing one-reviewer behavior: a later freshly evaluated lead FINAL may complete without another reviewer. Every independent persisted ledger chain was recomputed, and injected markers were absent.

The separate FINAL.text verdict/findings parser at `work-command.mjs:134–136` is byte-unchanged from the reviewed baseline. A generic-valid FINAL containing invalid verdict JSON still stops `REVIEWER_UNAVAILABLE` without a protocol diagnostic, as the existing separate policy does. R4 forwards invocation-level protocol diagnostics; it does not redefine that later verdict parser or strengthen REVISE semantics.

## Exact R1–R4 identities and source freeze

All 20 starting identities in the earlier independent review match the targeted repair's 256-file starting inventory. That inventory's SHA-256 is `b7f0abd24dc31caae5c09f63c9995814329010e95e7646d628f3892a0db6c657`. The starting source manifest hashes to `3619497550dfdbeafc319c9c44497bdad574c88823a51bba7aeebb045fdcd07a`. All 261 entries of the implementation's final identity inventory match this checkout before adding this review.

| Path | Earlier reviewed SHA-256 | Current reviewed SHA-256 |
| --- | --- | --- |
| `gate/foundation/decision-surface.mjs` | `0a86eed10700e268013306a5274b602833016f9ca27617f1d8cd5c2868e5494c` | `daea5d39e485d68413bf06d28150f8a5c57263dbbd9628130739e06862653cd6` |
| `gate/plugin/work-mode.mjs` | `1ddfa456b8de30111fcb81cd4bc2e311ad1a65c476a31e95c7569e9ab57494fa` | `85e02b40219d838ee59f322b9db1269036609067c6939c1f495b84e5d2d1a321` |
| `gate/src/protocol_stream.py` | `b262c1705b18dfa33726c73255a96d15fb84a6a2e37980e2f478ca545d0453bb` | `1853f0d71fa27bec4717f7b152345da18a7d3494cd6a267e0ce2a2afa4c12813` |
| `gate/plugin/work-command.mjs` | `97b02cc05f5fc771fcdb1743c35edb223d25f15eb7d28be245461f30f52c7d63` | `1052f29b6081d32487803aaaed34d85dbe5f5f46b1867e7d60dec02ec7f3b7e7` |
| `scripts/test.py` | `851e12cdc8e8a1481896196c92e8f5a7c1fe1b1c753cbab8a262030df387bc6a` | `e429d370110cbd88d4866160a3b3f942ee057471656d748f471f5f5a8d0ee574` |
| `gate/tests/fixtures/actual_protocol_worker.py` | new | `8b2e39c769205275d3c32b1f551bc10f0c5f5486e78f2c7f4aacc92451d5f3e3` |
| `gate/tests/fixtures/targeted-harness.mjs` | new | `1c0a243f74e900e51c562c8be7fcd70a15283db17de2fb6bc1166750abff5d25` |
| `gate/tests/protocol-targeted.test.mjs` | new | `c8f4815939f68753760b1cf5b59e2bc40337deb08a7f3b9123c0f407248e70fd` |
| `gate/tests/test_protocol_targeted.py` | new | `c2e02678836640abafae6f72a4da19505878571cafad30d7a776722f1c14a8c6` |

Current `SOURCE-MANIFEST.json`: `f01e3404b8ab1d54c14c1b7bec2477cf9314349c905d5cec86cfc3c0f82d9e4e`. Targeted repair report: `7602b77727b5ef27e14ab62f9e3aace04e23afa9383f1277a3bf850f779a7f58`. Historical independent review: `a93fd03608a6446f88bca1f5b959190da2dcb4e45c0fe92535ce0b102c398cd4`. Original repair report: `245c1018c22e9d49e8379b1fc26cb0dcd82cf5f4d132ea56623bc1db9a1977a7`. All match the recorded claims and current bytes.

Compared with the starting inventory, exactly six existing files differ: the four runtime files, suite registration and manifest. The other 250 are unchanged. The manifest has exactly five changed entries (the four runtime files and registration) and six additions (four tests/fixtures, unchanged historical review and targeted repair report), with no removals or unrelated hash refresh. Every recorded source hash verifies. Runtime pins remain separately unchanged and pass verification.

The reviewed source freeze describes the finished repair bytes. It is not an installed freeze. This newly added independent report is deliberately outside that existing freeze; review did not refresh the manifest to include itself. `verify()` checks recorded entries, not the completeness of a subsequent report addition. The final publication audit includes this report.

## Packaging and cross-cutting assessment

AST inspection confirms all **38** existing amendment entries exist. The four modified runtime files and the reviewer catch's newly imported `foundation/protocol-diagnostics.mjs` are already included. Python adds only standard-library imports. No amendment-list change is necessary for R1–R4.

Independently materialized the base HEAD's non-test gate package into a disposable directory, overlaid the 38 current amendment files and applied synthetic rendering substitutions. Checked **44 relative JavaScript import edges and 45 local Python import edges**, required settings/prompt/profile/release/runner assets, and Python worker/helper and JavaScript reviewer/microprobe imports with the working directory outside the checkout. All local modules resolve within that package. Intentional references to the existing pinned Python/Node/OpenClaw dependency runtime are not accidental source-module imports. All seven complete preflight artifacts equal the earlier review's artifact, including capability ordering and both schema identities.

The overlay relies on the existing base package's unchanged dependencies; it is not a standalone installer. The amendment's source/install verification, stopped-gateway checks, ownership/janitor checks, coherent copy, private receipt/freeze update and rollback were inspected, not executed. Installation, actual rollback and doctor remain unverified for these bytes.

The exact delta leaves the following unchanged:

- Qwen3.5-122B-A10B checkpoint/revision, quantization, vLLM/backend launch profile, thinking setting, temperature/sampling, input/output/token limits and iteration/model-call/correction budgets; 80B rollback descriptor and other model tiers.
- Dynamic selection and default four-capability surface; shared runtime/preflight/probe construction; generation and semantic schemas/digests; canonical Project 1 validation; immutable captured context; task/workspace/session binding, freshness, HMAC, nonce/replay, authority and exact result egress.
- Source-First, APFS/OCI containment, no replay after uncertain effects, `MUTABLE_WORKTREE_V1`, hidden FINAL while ineligible, valid inability, passing explicit test → fresh evaluator → bounded reviewer, one-reviewer REVISE policy, and all qualification fixtures/expected outcomes.

These conclusions combine the authenticated narrow diff, full inventory comparison, explicit HEAD comparisons of pins/profile/settings/qualification/authority/lifecycle/workspace files, and related packaged regressions. They do not constitute a new live qualification of each subsystem. The documented diff/status fingerprint limitations and one-reviewer REVISE limitations remain unresolved. Qwen remains the substantive reasoner; no alternative planner was introduced.

## Validation commands and results

Commands ran from the checkout with existing cached dependencies. Independent parser and signed-path counterexamples ran before focused and full packaged validation. Temporary scripts contain synthetic input only; the JavaScript signed tests reuse the inspected transport fixture but supply independent cases and assertions. Independent context tests were adapted from the earlier review harness. Package construction reused its inspected offline overlay procedure with a new output directory.

| Command | Result |
| --- | --- |
| `.venv/bin/python -B /tmp/sanctum-qwen-delta-review/independent.py` | 6 PASS, zero failures/errors/skips; recursive nonfinite, finite controls, duplicate keys, metadata, interrupted reads/narrow catch, completed malformed JSON. |
| `node --test --test-reporter=tap /tmp/sanctum-qwen-delta-review/independent.mjs` | 6 PASS, zero failures/skips; reason boundaries, signed correction/reset, signed nested overflow, signed interruption, actual reviewer errors/identities and verdict controls. |
| `node --test --test-reporter=tap /tmp/sanctum-qwen-delta-review/context.mjs` | 2 PASS, zero failures/skips; six exact boundary cases with/without correction. |
| `node --test --test-reporter=tap /tmp/sanctum-qwen-delta-review/reviewer-identity.mjs` | 1 PASS, zero failures/skips; frozen outgoing request and forged outer/diagnostic identities. |
| `node --test --test-reporter=tap gate/tests/protocol-targeted.test.mjs gate/tests/protocol-repair.test.mjs` | 20/20 PASS, zero failures/skips; 10 targeted and 10 original protocol tests. |
| `.venv/bin/python -B -m unittest discover -s gate/tests -p 'test_protocol_*.py'` | 15/15 PASS, zero failures/errors/skips; 5 targeted and 10 original methods. |
| `cat .venv/pyvenv.cfg`; `.venv/bin/python --version`; `uv pip list --python .venv/bin/python` | Existing environment inspected before bootstrap: Python 3.12.14, Pillow 12.3.0, pypdf 6.18.0, imageio-ffmpeg 0.6.0. |
| `npm_config_offline=true npm_config_audit=false UV_OFFLINE=true make deps` | PASS from cache: 383 npm packages installed with scripts disabled, three pinned Python packages checked; no downloads, upgrades or pin changes. |
| `make build` | PASS: six plugin builds/validations, capability manifest and reviewed OpenClaw pins. |
| `umask 022` then `make test` | **305 PASS**, zero failures/errors/skips, one complete run. Gate Node 101, gate Python 125, reliability Node 31, reliability Python 11, MCP Node 8, release Python 18, six plugin suites 11 (3+1+2+2+1+2). |
| `.venv/bin/python -B /tmp/sanctum-qwen-delta-review/package.py` | PASS: 38-file overlay, 44 JS/45 Python import edges, isolated imports and seven exact schema artifacts. |
| `.venv/bin/python -B /tmp/sanctum-qwen-delta-review/identity.py` | PASS: baseline/current identities, nine targeted hashes and explained manifest delta; repeated after supported checks to verify no reviewed-source drift. |
| `make audit` | PASS before report: 261 source files, zero issues. Final report-inclusive result: 262 source files, zero issues. |
| `.venv/bin/python -B -c 'from scripts.release_operator import verify; verify(); print("Source manifest and runtime pins match")'` | PASS before and after report; source freeze and cached runtime pins match. |
| `git diff --check` | PASS before and after report. Added report checked separately for whitespace because it is untracked. |

The **15 independent tests** are separate from the packaged suite. Focused tests are subsets of the 305 and are not added to that total. No implementation changed and the full suite was not repeated. One initial inventory-check script asserted the wrong table count because its regex also matched schema-table rows; restricting it to the documented byte-identity section fixed that temporary harness error. It was not a product failure. All independent behavioral tests passed on their first execution.

Inspected Makefile, build/test/audit scripts, amendment code and relevant test side effects before execution. Offline bootstrap used cache only; build regenerated plugin outputs; tests used disposable synthetic state and the existing cached local OCI runner/daemon. No daemon start or image pull/build was invoked. Existing containment tests, including blocked network checks inside isolated containers, are not provider access or live Qwen trajectories. No private amendment, private doctor, gateway start, model inference, GPU allocation, live probe or 11-case qualification ran.

## Claims confirmed and limits of confirmation

Confirmed independently: branch/base/index state; four-runtime-file delta; unchanged baseline files; targeted hashes and freeze; test registration; package closure; 305 current packaged passes; build/audit/integrity/whitespace results; and the R1–R4 behavior above. The retained pre-fix logs also report the claimed calibrated Node 2 pass/8 fail and Python 7 subtest failures/4 errors, followed by the reported passes. Those old logs are historical corroboration, not a new execution of the old implementation.

The checkout and retained source evidence support the implementation report's scope. They cannot independently prove the historical absence of every deployment, provider action, inference, push or PR; those external systems were deliberately not inspected. No such action occurred during this review. No conclusion relies on private installed state or historical output contents.

Synthetic correction success does not explain the historical 22 failures, prove that reason formatting caused them, or show improved Qwen action selection. Actual checkpoint behavior, exact decoder compatibility and useful task completion remain unobserved here. No source or report falsely closes the separate pre-live work.

## Pre-live prerequisites still open

1. **Persistent readiness-inclusive inference attempt ledger/budget.** Lifecycle readiness still invokes `health_check(smoke=True)` at `gate/src/lifecycle.py:147,160`; its calls do not share the microprobe counter.
2. **Experiment-scoped atomic dispatch guard.** Readiness/proposal calls across worker processes do not yet reserve from one persistent allowance immediately before dispatch.
3. **Independent supervisor and absolute deadline across processes.** Existing caller abort timers do not establish bounded worker/provider lifetime or confirmed cleanup.
4. **Exact pinned compiler/backend/template/tokenizer verification.** Host schema/AJV checks and unchanged launch pins do not establish the resolved runtime grammar backend, transitive compiler versions, template bytes or full-schema branch reachability.
5. **Rendered-token measurement.** Character and transport limits do not establish fit in the pinned tokenizer/chat template.
6. **Coherent installed amendment and doctor verification.** Source packaging passed; installation and current private runtime identity were not observed.
7. **Live microprobe execution.** Not run and not authorized by this report.
8. **Context compaction.** Not implemented; the preserved policy stops at the context boundary.
9. **Native-tool alternative.** Not implemented/evaluated; remains separate design work, not a required redesign of this passing content-JSON delta.
10. **Actual Qwen task-success evidence.** No new unseen task, real patch/test trajectory or 11-case qualification evidence exists from this review.

Items 8 and 9 are retained out-of-scope alternatives, not newly imposed conditions requiring a redesign before any diagnostic run. The operational controls and evidence required for a particular live experiment still need their own review and authorization.

## Exact next bounded work package

On a separate request, prepare the **offline diagnostic harness and exact-compiler preparation package** described in the earlier independent review. Do not change the reasoner, sampling, schema acceptance, ordinary task surface or qualification fixtures.

The package must implement and independently test a Mac-owned persistent experiment ledger and atomic dispatch reservation shared across readiness/proposals and worker restarts/concurrency. Reserve immediately before every completion dispatch, including failed/uncertain attempts; never refund. Refuse absent/stale experiment ownership, exhausted attempt/output budget or deadline expiry. Preserve the proposed ceiling of at most six total attempts: at most one 16-token readiness smoke plus five 1024-token proposals. Failed readiness ends the experiment; no uncounted warmup, retry or characterization. Three first decisions and at most two corrections fit; an additional needed correction ends incomplete. Keep this an explicit diagnostic mode rather than casually changing ordinary lifecycle retry policy.

Propagate an absolute experiment deadline through executor, worker, readiness, HTTP and cleanup, backed by independent supervision. Add offline boundary, crash, restart and concurrent-reservation tests. Prepare a stopped-gateway coherent-installation and cleanup runbook; do not execute it as part of this review. Require installed identities, doctor/authenticated non-inference readiness, validated independent janitor and no unresolved managed ownership before a later allocation. Uncertain deletion retains ownership records and janitor supervision; preserve persistent volumes.

Prepare exact full-schema compiler verification and rendered-token measurement in a separately authorized compatible environment: resolved backend/compiler/transitive versions, tokenizer/template identities, full production-schema compilation and representative branch reachability. Distinguish CPU preparation evidence from any endpoint/backend checks that can only occur after an explicitly authorized allocation. Mocks and AJV are insufficient compiler proof. No dependency installation, live backend check or model call is authorized here.

The earlier proposed one-allocation, 900-second envelope and USD 0.75 compute ceiling at no more than USD 3/hour remain **unapproved proposals**, not a current quote or billing guarantee. A future request must account for actual rates/minimums/storage, supervised cleanup and provider-confirmed deletion; local time expiry alone is not proof that billing stopped. The package prepares reviewable controls and a bounded runbook, not permission to spend or run the 11-case suite.

Neither this source acceptance nor the follow-on package accepts Project 3, authorizes deployment/spending, proves improved Qwen action selection, or authorizes live qualification.

R1–R4 DELTA REVIEW PASSED — PRE-LIVE GATES STILL OPEN — NO LIVE RUN AUTHORIZED
