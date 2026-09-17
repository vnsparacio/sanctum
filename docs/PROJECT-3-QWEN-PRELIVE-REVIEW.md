# Project 3 Qwen pre-live readiness — independent review

Date: 2026-09-16. **Phase A blocked on two source findings.** The 355 packaged tests pass, but independent counterexamples reproduce premature cleanup confirmation and broken multi-branch verification with the pinned xgrammar wrapper. Neither finding was patched. Phase B and Phase C were not entered. Project 3 remains unaccepted.

## Reviewed state and boundaries

Reviewed the canonical checkout identified in the live baseline, branch `v1.1/project-3-private-lead-workmode`, HEAD `e168f864eb5ed74d3437102323cdf79804505f06`. The starting tree contained 17 modified tracked files, 26 individually counted untracked files, and an empty index. The review target includes the larger uncommitted repair, not HEAD alone. Read AGENTS.md, the live baseline, all four protocol repair/review reports and the complete pre-live readiness report.

The starting inventory contains 273 source files. Reviewed SOURCE-MANIFEST SHA-256: `be567a4f22f0bdfcbe4ccbc1dd9fd5a2242f2410f9665351ad3561869ea5ced2`. All starting files remained byte-identical after the checks. This review report is the only source addition; no manifest refresh, implementation edit, permanent test edit, staging or Git history/branch operation occurred.

Synthetic evidence, starting identities, independent test scripts and command logs are retained in `/tmp/sanctum-prelive-independent-review-20260917`. No private installation, credentials, personal sources, private receipts, model caches, provider resources or legacy tree were inspected. No gateway, model or provider action was performed. The only external source read was the official pinned vLLM implementation used to check its adapter API. No runtime packages were downloaded or repinned.

## Findings

### R1 — P2: Cleanup can claim COMPLETE / CONFIRMED with a surviving lease

Relevant code: `gate/src/experiment_lifecycle.py:116–128`, interacting with `gate/src/lifecycle.py:35–59,240–254,271–275`.

An ordinary PRIVATE_LEAD proposal calls `acquire()` before the experiment admission check. When the experiment owns PRIVATE_LEAD, admission correctly refuses that proposal. Its finally path calls ordinary `release()`, which leaves an inactive, non-closing lease for the normal idle interval. Experiment sweep supersedes the ordinary sweep, so that lease is not reconciled there.

`ExperimentSupervisor._terminal()` checks recorded diagnostic workers and deletes only the experiment's `lease_scope`. It then writes COMPLETE / CONFIRMED without checking other lease rows or active requests. A denied ordinary proposal can therefore leave a lease behind when experiment cleanup is declared complete. With no open experiment remaining, the watcher can subsequently apply ordinary idle behavior to that leftover lease instead of having established the required zero-lease terminal invariant.

Independent reproduction uses the actual ordinary lifecycle admission/release path, actual SQLite ledger and supervisor, with a synthetic provider only. Seed one owned allocation and an inactive diagnostic lease, submit a separate ordinary proposal, observe `experiment_ownership_required`, request cancellation, then sweep. Observed facts:

- Synthetic provider received exactly one managed delete and subsequently returned absence.
- Experiment became `COMPLETE`, cleanup `CONFIRMED`, allocation `ABSENT`.
- The diagnostic lease was removed, but **one ordinary lease remained**, active=0 and closing=0.

An earlier no-allocation variant reproduced the same terminal-state defect. Neither case involved real resources. This is not evidence of unconfirmed provider deletion or extra inference; it is a false claim that all local cleanup prerequisites have been met.

Required repair: prevent denied ordinary admission from leaving diagnostic-conflicting leases, and require an explicit, safe zero-active-request/zero-lease reconciliation before terminal confirmation. Do not blindly delete leases belonging to potentially live ordinary workers. Cover ordinary attempts during an experiment, both private release stores where applicable, and the final receipt's cleanup claim.

### R2 — P2: Reusing the pinned xgrammar wrapper rejects later valid branches

Relevant code: `gate/verify_exact_runtime.py:109–117`.

The verifier compiles one grammar for each full schema, consumes a representative including EOS, calls `grammar.reset()`, then feeds the next representative into the same wrapper. In the official [vLLM 0.20.1 xgrammar implementation](https://raw.githubusercontent.com/vllm-project/vllm/v0.20.1/vllm/v1/structured_output/backend_xgrammar.py), successful EOS sets the wrapper's `_is_terminated` flag. `reset()` resets its matcher and token count but does not clear that flag. `accept_tokens()` immediately rejects when the flag remains true.

The independent API counterexample executes the exact upstream `accept_tokens`, `reset` and `is_terminated` methods, extracted without changes, with a minimal synthetic matcher supplying only termination mechanics. First representative and EOS pass; after reset, wrapper termination remains true and the second representative's first token is rejected. Thus, if xgrammar is the reviewed resolved backend, this tool cannot establish branch reachability for the multi-branch production surfaces even when their schemas and values are valid.

This is a deterministic verifier/API defect, not an actual schema compilation failure. The synthetic matcher is **not exact compiler proof**; no vLLM/compiler/tokenizer environment was installed or exercised. The issue does not establish which backend the private candidate uses.

Required repair: create independent grammar/matcher state for each representative through the supported pinned backend API, without upgrading packages or changing backend selection. Add a regression covering at least two successive accepted branches including EOS. Preserve separate full generation/semantic schema checks and honest NOT_RUN handling.

## Other reviewed controls and limits

The persistent ledger lives in the existing Mac-owned private SQLite store. Reservation uses `BEGIN IMMEDIATE`; completion dispatch cannot enter its context until reservation and local dispatch initiation have committed. Records contain fixed structural facts rather than prompt/task/model content. Binding checks cover experiment, source, installation and deadline. Terminal/expired experiments, excessive tokens and exhausted class/total allowances refuse further reservations. No refund path exists.

Six independently written control tests passed: crash after committed reservation followed by a new ledger instance; six processes competing for the final global slot; concurrent readiness/proposal requests competing for the remaining class slots; stale/missing identity, expiry and token ceilings; cancellation between reservation and dispatch; and refusal to replace an unresolved experiment after restart. Exactly one of six final-slot contenders succeeded. The readiness/proposal race admitted exactly one readiness and one proposal, retaining the six/one/five limits. Cancellation retained one uncertain reservation and initiated no transmission.

Traced signed experiment metadata through executor, authority, worker, diagnostic lifecycle and backend. One absolute deadline with the 120-second cleanup reserve bounds dispatch and worker/control alarms. Provider cleanup remains callable after expiry. Diagnostic readiness keeps its single smoke outside non-inference polling. Ordinary model/profile settings and runtime pins are unchanged. Existing focused tests exercise caller/worker loss, hung worker signaling, deadline, restart, ambiguous create, uncertain deletion and confirmed absence; these are synthetic tests, not new live supervision evidence. R1 prevents accepting the claimed final local-cleanup invariant.

The installed caller supplies the fixed three synthetic microprobes and five-proposal ceiling, with the existing correction policy. Reviewed the distinct diagnostic lifecycle, one persisted allocation intent, no replacement-create loop, watcher integration and janitor sweep routing. Independent supervision and actual provider behavior were not verified in an installed runtime, because Phase A failed.

Readiness artifacts use production request/schema builders and enumerate exactly six production surfaces. Representatives receive host/schema validation; token preparation uses the production backend payload builder and thinking-disabled rendered messages. The verifier requires a reviewed resolved environment, pinned vLLM identity, compiler/package identities, tokenizer files/revision, template digest, selection configuration and schema/artifact identities. It does not silently replace unresolved `auto` with a guessed backend. The unchanged 32768 window, 4096 profile reserve and 1024 proposal ceiling are retained. No exact compiler run, rendered token count or token-headroom pass is claimed. R2 blocks accepting the xgrammar adapter's branch-testing implementation.

The package-closure test materialized the HEAD base plus all 46 current overlay files, ran outside the checkout's module search path, resolved 56 JavaScript and 64 local Python import edges, and produced identical production request artifacts. The unavailable-environment verifier returned NOT_RUN as expected. This establishes source package closure, not installed byte identity or compatibility.

Compared the current source freeze with the retained pre-live starting manifest: 12 changed entries, 12 additions, no removals, matching the explained package delta. Source hashes verify. `gate/runtime`, `gate/SETTINGS.json`, `reliability/runtime-pins.json` and `package-lock.json` are unchanged from HEAD. The amendment implementation was read but never invoked.

## Commands and observed results

Commands ran from the canonical checkout unless their temporary script path is explicit. Focused counts are subsets of the packaged total. Independent tests are separate.

| Command | Observed result |
| --- | --- |
| `cat .venv/pyvenv.cfg`; `.venv/bin/python --version`; `uv pip list --python .venv/bin/python` | Existing environment inspected before bootstrap: Python 3.12.14; Pillow 12.3.0; pypdf 6.18.0; imageio-ffmpeg 0.6.0. |
| `npm_config_offline=true npm_config_audit=false UV_OFFLINE=true make deps` | PASS, cache-only dependency bootstrap; no pin changes. |
| `make build` | PASS, six plugin builds/validations and manifest/runtime-pin checks. |
| `.venv/bin/python -B -m unittest discover -s gate/tests -p 'test_prelive*.py'` | 42 PASS; includes the isolated 46-file package-closure test. |
| `node --test --test-reporter=tap gate/tests/prelive.test.mjs gate/tests/protocol-repair.test.mjs gate/tests/protocol-targeted.test.mjs` | 28 PASS, zero failures/skips. |
| `.venv/bin/python -B -m unittest discover -s gate/tests -p 'test_protocol_*.py'` | 15 PASS, zero failures/errors/skips. |
| `umask 022` then `make test` | **355 PASS**, zero failures/errors/skips. Gate Node 109, gate Python 167, reliability Node 31, reliability Python 11, MCP Node 8, release Python 18, plugin suites 11 (3+1+2+2+1+2). |
| `.venv/bin/python -B /tmp/sanctum-prelive-independent-review-20260917/ledger-controls.py` | **6 independent PASS**, zero failures/errors/skips. |
| `.venv/bin/python -B /tmp/sanctum-prelive-independent-review-20260917/counterexamples.py` | **2 independent FAIL**, reproducing R1 and R2; zero errors/skips. Failures are retained, not counted as passing safety checks. |
| `make audit` | PASS before report: 273 files, zero issues. Final report-inclusive check: 274 files, zero issues. |
| `.venv/bin/python -B -c 'from scripts.release_operator import verify; verify(); print("Source manifest and runtime pins match")'` | PASS before and after report. |
| `git diff --check` plus whitespace scan of every untracked file | PASS before and after report. |
| Starting SHA-256 inventory comparison | All 273 starting files unchanged. Index remains empty; only this report was added. |

The complete packaged suite ran once. No implementation changed afterward. Build/test side effects were inspected: generated plugin outputs and temporary synthetic fixtures, including the already available local OCI test environment. No image build/pull, amendment, private doctor, provider inventory, allocation or inference command was invoked. The report is deliberately outside the unchanged source manifest; verification of recorded hashes does not freeze this additional review artifact.

## Disposition

Phase A fails on R1 and R2. Phase B installation, installed doctor/gateway/schema verification and exact runtime execution were not attempted. Phase C pricing/authorization/allocation/probes were not attempted. No paid-compute authorization is requested while source blockers remain. No real coding task, 11-case qualification, promotion, commit, push, merge or Project 3H work occurred.

PRE-LIVE INDEPENDENT REVIEW BLOCKED — NO INSTALLATION OR LIVE RUN PERFORMED
