# Project 3 Qwen pre-live readiness — independent targeted review

Date: 2026-09-16 (local review date). **Phase A BLOCKED.** The ordinary-admission repair and fresh-grammar repair pass their bounded checks, but two cleanup counterexamples prevent acceptance of R1's complete safety contract. All 367 packaged tests pass. No implementation was patched and Phase B was not entered. Project 3 remains unaccepted.

## Review target and boundaries

Reviewed the canonical checkout identified in [the live baseline](../V1.1-LIVE-BASELINE.md), branch `v1.1/project-3-private-lead-workmode`, HEAD `e168f864eb5ed74d3437102323cdf79804505f06`. Local `v1.1-dev` and its merge base with HEAD are `3c84eac9eccd43a7827965f424ba92c8709070de`. The feature branch's local tracking reference is `ffdf5521beba0b8f49d967045fd1d6a80a402811`; HEAD is eleven ahead and zero behind. No fetch or remote-history mutation occurred.

The initial index was empty; the working tree contained 17 modified tracked files and 29 individually counted untracked files. The larger uncommitted Project 3 repair remains present. Review included staged, unstaged and untracked state, not HEAD alone. Read AGENTS.md, the complete live baseline, protocol targeted review, pre-live readiness runbook, previous independent pre-live review and targeted repair report.

Synthetic evidence, independent scripts, downloaded public upstream API source, identities and logs are retained in `/tmp/sanctum-prelive-targeted-review-20260917`. Historical source-only inventories and baseline copies were read from the preceding repair/review evidence directories. No private candidate runtime, credentials, personal sources, private model outputs, raw provider responses or legacy-tree files were inspected. No installation, private doctor, gateway operation, provider operation, GPU allocation, inference, microprobe, real coding task or 11-case live suite ran. No Git index, branch or history operation occurred.

This report is the only source addition made by review. Implementation, permanent tests, SOURCE-MANIFEST, runtime/model/dependency pins, settings and earlier reports were not edited.

## Blocking findings

### R1a — P2: ordinary 80B sweep can erase the unresolved rows that terminal cleanup must preserve

Source: `gate/src/lifecycle.py:198–220`, especially line 207; `gate/watch.py:26–31`; `gate/src/experiment_lifecycle.py:130–135`.

The new admission guard correctly covers both releases, and `_terminal()` correctly counts both stores. However, the production PRIVATE_80B sweeper still deletes expired lease rows without checking experiment ownership or verifying their workers. PRIVATE_LEAD's experiment-aware sweep override does not cover the 80B watcher. Thus the new count can become zero through the very automatic deletion prohibited by the requested local-reconciliation contract.

Independent counterexample uses the actual SQLite ledger, actual PRIVATE_LEAD supervisor and actual PRIVATE_80B lifecycle sweep. The provider is synthetic. Seed an unresolved expired ordinary 80B lease (`active=1`) to represent recovered/unknown local ownership, cancel an experiment with a synthetic owned allocation, and sweep the diagnostic supervisor. It performs one synthetic managed delete, confirms absence, preserves the ordinary row and returns `CLEANUP_REQUIRED / LOCAL_PENDING`, as required. Then run ordinary 80B sweep and diagnostic sweep again. Observed:

| Fact | Result |
| --- | --- |
| First diagnostic cleanup | `LOCAL_PENDING` |
| Ordinary lease rows after 80B sweep | 0 |
| Explicit ordinary-owner reconciliation | None |
| Final allocation state | `ABSENT` |
| Final experiment state / cleanup | `COMPLETE / CONFIRMED` |

This does not claim that newly guarded admission can create that foreign row during an experiment. It tests the explicitly required stale/unknown-row recovery state. It also does not claim a row survives the final count: the defect is unsafe deletion before that count. A zero-row check alone cannot establish safe reconciliation.

Required repair: make ordinary cleanup coexist safely with unresolved diagnostic ownership across both release stores, preserving unknown rows until explicit reconciliation. Retain ordinary idle behavior when no experiment is unresolved. Cover the actual 80B watcher/sweep and its interaction with diagnostic cleanup, rather than only calling `_terminal()` in isolation. The PRIVATE_LEAD override also reads experiment ownership before entering ordinary sweep; any repair must consider that check/use interval.

### R1b — P2: unavailable worker identity is treated as verified worker exit

Source: `gate/src/experiment.py:25–32`; `gate/src/experiment_lifecycle.py:19–20,115–125`.

`process_identity()` returns `None` for both absence and lookup failure, including an OSError or the bounded `ps` timeout. `alive()` collapses this uncertainty into false. `_terminal()` treats false as sufficient to pass its worker-exit gates, deletes the bound diagnostic lease and can publish `COMPLETE / CONFIRMED`. Unknown identity therefore becomes implicit permission to delete an active lease.

Independent counterexample starts a separate harmless local child blocked on standard input, records its actual PID/start identity and an active diagnostic lease, and cancels a no-allocation experiment. Only the process-identity lookup is made unavailable, simulating its documented failure result; the production `alive`, supervisor and database paths remain real. The supervisor removes the lease and reports `COMPLETE / CONFIRMED`. Immediately afterward the child is still running with the same independently re-read identity. The synthetic child is then closed by the test harness. No model or provider process is used or signaled.

The no-allocation branch calls the same `_terminal()` used after provider absence. Provider absence cannot repair an unknown local-worker fact. This behavior predates the five-file delta but is directly within the requested terminal-proof and unknown-worker review scope. Existing tests with an injected always-false `is_alive` do not distinguish confirmed exit from lookup failure.

Required repair: distinguish verified exit/PID replacement from unavailable identity evidence. Unknown local worker/control/attempt identity must retain unresolved cleanup and the lease; it must not permit terminal confirmation or unsafe signaling. Add failure/timeout coverage with an independently live worker and recovery once identity/exit is verifiable.

Neither finding was patched. The independent cleanup script ends with **2 failed tests, zero errors/skips**; these are retained failures, not passes.

## Checks that pass within their stated scope

### R1 admission, production creation and direct terminal counting

`Private80BLifecycle.acquire()` is inherited by PRIVATE_LEAD. It obtains the shared PRIVATE_LEAD experiment transaction before reading ownership and before inserting or incrementing either release's lease. Infer/propose call acquire before entering their request/finally blocks, so denied admission creates no row and does not enter ordinary readiness. `CLEANUP_REQUIRED` remains unresolved ownership.

`ExperimentLedger.create()` checks every lead lease row while holding that transaction. The actual `experiment_control.main()` create path explicitly supplies `Path(settings['state_directory'])`, so it checks the 80B store too. An independent control-command test uses the real ledger constructor and command path, replacing only installation/settings identity inputs with synthetic fixtures; it does not inject a preconstructed ledger to accidentally supply the second store. Both stores reject active, inactive and expired rows without changing them.

Independent deterministic controls cover both launch orders and both releases, including refusal to increment a recovered matching-scope row in ACTIVE and CLEANUP_REQUIRED states. The packaged repair tests additionally run separate-process create/acquire races in both launch orders. Ordinary acquire/release without an experiment retains its inactive, non-closing idle lease.

The original independent R1 rejected-proposal counterexample now passes: denial leaves no ordinary lease, one synthetic delete establishes absence, and terminal cleanup has zero rows. Permanent regressions confirm that direct diagnostic cleanup preserves foreign rows in either store, including matching scopes across releases, returns local pending, and completes after explicit synthetic owner reconciliation. The exact experiment lease is deleted only from PRIVATE_LEAD, not from the other store. These narrower successes do not close the two findings above.

### Lock, transaction, crash and concurrency analysis

Reviewed ledger transactions, both lease stores, lifecycle flock, supervisor flock and watcher routing. The new ordering is PRIVATE_LEAD database first, then PRIVATE_80B database. PRIVATE_LEAD acquisition reuses its existing connection. Production creation and terminal counting take the same admission transaction, so ordinary creation/increment cannot slip between the count and terminal commit. A new ordinary lease admitted after terminal commit is a new ordinary lifecycle, not a surviving diagnostic-era row.

Release and heartbeat hold only their own store. Release commits before calling sweep; it does not hold the 80B database while requesting the lead ledger or lifecycle lock. Ordinary sweep holds its lifecycle lock while briefly accessing its own database, but admission does not wait for that lifecycle lock. The diagnostic supervisor uses a separate nonblocking flock, releases ledger transactions before provider operations and attempts the lifecycle flock nonblocking after provider absence. Diagnostic allocation likewise separates database transactions, lifecycle state writes and provider calls. No new cycle requiring one participant to hold 80B while awaiting lead, with the opposing participant awaiting a lifecycle/supervisor lock, was found in these paths.

This is source-backed lock-order analysis, not a claim that passing tests prove deadlock absence. The ordinary sweep bypass in R1a is a semantic cleanup race despite the absence of such a lock cycle. SQLite contention can still refuse work: the shared database primitive configures a 30-second busy timeout and uses connection contexts for commit/rollback; admission does not turn a busy exception into successful acquisition. SQLite documents one simultaneous writer and possible SQLITE_BUSY on BEGIN IMMEDIATE or commit in its [transaction documentation](https://www.sqlite.org/lang_transaction.html). No 30-second timeout timing claim is made from this review's tests.

Independent crash cases kill a child during the admission transaction or immediately after it for both releases. Uncommitted same-database lead insertion rolls back. In the 80B case, its nested commit can survive death before the outer lead transaction commits; that ordinary row remains visible and blocks experiment creation after restart. Committed rows in both releases remain blocking. All four recovered databases pass integrity checks. An exception inside a transaction rolls back its synthetic write and permits subsequent clean creation. These checks exercise actual acquisition and database transactions without provider operations.

No admission transaction is held across readiness, provider calls or model transmission. Brief bounded process-identity checks in other ledger operations are not provider work. Unknown identity remains a safety blocker as described above.

### R2 fresh request grammar: closed for source/API orchestration

`gate/verify_exact_runtime.py:109–128` invokes `backend.compile_grammar()` inside the representative loop for each full generation and semantic schema. It no longer resets and reuses a terminated wrapper. It feeds each representative token sequence, checks EOS acceptance and termination, aggregates invalid/failed compilation into FAIL, and destroys each successfully constructed backend in `finally`.

The pinned [vLLM xgrammar backend](https://raw.githubusercontent.com/vllm-project/vllm/v0.20.1/vllm/v1/structured_output/backend_xgrammar.py) creates a new matcher/wrapper per compile call; its wrapper's reset leaves termination sticky. The pinned [outlines backend](https://raw.githubusercontent.com/vllm-project/vllm/v0.20.1/vllm/v1/structured_output/backend_outlines.py) similarly creates a fresh guide/wrapper while allowing cached immutable index reuse. The repair changes neither selection configuration nor schema/backend identities.

Four independent tests extract and execute the unchanged upstream xgrammar `compile_grammar`, `destroy`, `accept_tokens`, `is_terminated` and `reset` method ASTs with synthetic compiler/matcher/tokenizer plumbing. The old reset counterexample is reconstructed as a negative control: after EOS and reset the same wrapper still rejects another branch. The repaired production verifier passes with **50 distinct wrappers across 12 full-schema checks**, covering all six surfaces. A changed invalid representative fails, as do compiler exceptions; all six backends are destroyed. The permanent fake also models sticky termination rather than returning unconditional success after EOS.

These are API/orchestration tests only. The synthetic compiler does not prove JSON-schema grammar compatibility, actual backend resolution, tokenizer behavior or rendered-token headroom. Exact compiler, tokenizer/template, live endpoint and model inference remain NOT_RUN. No external package was installed to manufacture an environment pass.

## Exact source identity and package closure

The review-start inventory contains **276 files**, SHA-256 `d658cc69ececf375837d5c8a6112c97b81a36bb5ed461bf2312a661c1646eb0e`. All 276 hashes match the targeted repair's retained final inventory. Compared with its 274-file starting inventory, exactly the five runtime files below and SOURCE-MANIFEST changed; the other 268 starting files are unchanged. The only two additions are the targeted regression and repair report.

| Runtime path | Reviewed SHA-256 |
| --- | --- |
| `gate/experiment_control.py` | `912b470b9d23ae330aed856d86db61b854d19e2837b0fff07ab9b11cb8759856` |
| `gate/src/experiment.py` | `8ccfdbd2504395cf98cf108c2679a44785dc1eb4557714b68268a2b437114aff` |
| `gate/src/experiment_lifecycle.py` | `b7921b875fa654b221fbaf7db4cab94c074497cad1b4030bcc11fc2e64ff12e5` |
| `gate/src/lifecycle.py` | `b3f4fdeb9acd37faaf1b33301d47e4fa6a312e1a62f542b60ac9ce56863d4220` |
| `gate/verify_exact_runtime.py` | `a4394ffaf5e89e8890683ede0dc460c4b66ba8e27e7ff9fe583107d02ef8e4be` |

New `gate/tests/test_prelive_targeted.py`: `2d586eb820d7c46cc6ce382842480a695d3009f85b93cad57da56560d140fa52`. Its 12 methods are discovered by the existing Python suite; no registration change was needed. Each retained pre-edit runtime copy was authenticated against the repair-start inventory before independently generating the narrow runtime diff, SHA-256 `d6b4782bc48d84d776d7cddc6c92a0c5ecaf0e91cc9e3ab90416de6bb71935c4`.

SOURCE-MANIFEST changed from `be567a4f22f0bdfcbe4ccbc1dd9fd5a2242f2410f9665351ad3561869ea5ced2` to reviewed `f31f9697638c6f68babe15c1d677ae72995d00fe2b68e29be2d07b9aaf3d13f3`. Its delta has five changed entries, three additions (unchanged prior independent pre-live review, targeted repair report, targeted test), and zero removals. No unrelated hash refresh was found. `gate/runtime`, `gate/SETTINGS.json`, `reliability/runtime-pins.json` and `package-lock.json` remain byte-unchanged from HEAD.

All five runtime files are already included in the unchanged **46-file** coherent amendment overlay. The isolated package test materializes the HEAD base plus current overlay outside the checkout module path, verifies **56 JavaScript and 65 Python local import edges**, imports the production Python modules, and produces identical production request artifacts. Its exact-runtime CLI correctly returns NOT_RUN without an environment. No new source-checkout dependency was introduced by this repair. This proves source package closure, not installed identity.

The review report is deliberately outside the unchanged source freeze. Final audit includes it, while source verification checks the existing recorded entries. Review did not refresh hashes to include itself or claim a new installation freeze.

## Commands and observed results

Commands ran in the canonical checkout unless an evidence path is shown. Focused suites are subsets of the packaged total. Independent tests are separate.

| Command | Observed result |
| --- | --- |
| `cat .venv/pyvenv.cfg`; `.venv/bin/python --version`; `uv pip list --python .venv/bin/python` | Existing venv inspected: Python 3.12.14; Pillow 12.3.0; pypdf 6.18.0; imageio-ffmpeg 0.6.0. |
| `npm_config_offline=true npm_config_audit=false UV_OFFLINE=true make deps` | PASS, cached dependencies; 383 npm packages, three Python requirements checked. |
| `make build` | PASS, six plugin builds/validations and manifest/runtime-pin checks. |
| `.venv/bin/python -B -m unittest discover -s gate/tests -p 'test_prelive*.py'` | **54 PASS**, zero failures/errors/skips; includes 12 targeted methods and isolated package closure. |
| `node --test --test-reporter=tap gate/tests/prelive.test.mjs gate/tests/protocol-repair.test.mjs gate/tests/protocol-targeted.test.mjs` | **28 PASS**, zero failures/skips. |
| `.venv/bin/python -B -m unittest discover -s gate/tests -p 'test_protocol_*.py'` | **15 PASS**, zero failures/errors/skips. |
| `umask 022` then `make test` | **367 PASS**, zero failures/errors/skips: gate Node 109, gate Python 179, reliability Node 31, reliability Python 11, MCP Node 8, release Python 18, plugin suites 11 (3+1+2+2+1+2). |
| `.venv/bin/python -B /tmp/sanctum-prelive-targeted-review-20260917/admission-controls.py` | **4 independent PASS**, zero failures/errors/skips; includes deterministic orders, actual create command, four process-death cases and rollback. |
| `.venv/bin/python -B /tmp/sanctum-prelive-targeted-review-20260917/compiler-controls.py` | **4 independent PASS**, zero failures/errors/skips; upstream sticky-reset negative control, fresh production verifier, invalid representative and compiler failure. |
| `.venv/bin/python -B /tmp/sanctum-prelive-independent-review-20260917/ledger-controls.py` | **6 independent PASS**, zero failures/errors/skips; global/class limits, final-slot process races, crash/restart, stale identity/deadline/tokens, cancellation and unresolved replacement refusal. |
| `.venv/bin/python -B /tmp/sanctum-prelive-independent-review-20260917/counterexamples.py Counterexamples.test_cleanup_does_not_report_confirmed_with_ordinary_rejected_lease` | **1 independent PASS**; original R1 admission/leftover-row case closes. |
| `.venv/bin/python -B /tmp/sanctum-prelive-targeted-review-20260917/cleanup-counterexamples.py` | **2 independent FAIL**, zero errors/skips; R1a and R1b reproduced. |
| `make audit` | PASS, 276 files before report; final report-inclusive check 277 files, zero issues. |
| `.venv/bin/python -B -c 'from scripts.release_operator import verify; verify(); print("Source manifest and runtime pins match")'` | PASS before and after report. |
| `git diff --check` plus untracked-file trailing-whitespace scan | PASS before and after report. |
| Starting inventory comparison | All 276 starting files unchanged; only this report added; index/branch/HEAD unchanged. |

The packaged suite ran once. Build regenerated ordinary plugin outputs and tests used temporary synthetic state plus the existing cached local OCI test environment. No image pull/build, daemon start or owner-runtime amendment occurred. Independent admission checks were repeated after correcting a test name that had overstated busy-timeout coverage; no such timing test is claimed. Cleanup counterexamples were repeated with a separate independently live child replacing the first same-process identity fixture, strengthening R1b without changing production code. Both runs reproduced the same two failures.

## Disposition and Phase B status

R2's source/API defect is closed. R1's ordinary admission and direct two-store count are repaired, but R1a and R1b prevent the required safe terminal-cleanup proof. Source changes are required, so the owner's Phase A stop rule applies. No installation is permitted from this review result.

Phase B source/runtime safety gates, coherent amendment, installed-byte/FREEZE binding, private doctor, authenticated gateway/work help, installed schema preparation, exact compiler/backend execution, tokenizer/template identities, token measurements, installed experiment/supervisor state, provider capacity/pricing/billing and monetary-ceiling preparation were **not attempted**. No old runtime result or synthetic evidence substitutes for those checks. No spending authorization is requested while the source gate is blocked.

PRE-LIVE TARGETED REVIEW BLOCKED — NO INSTALLATION OR LIVE RUN PERFORMED
