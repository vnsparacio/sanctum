# Qwen Code fourth isolated MoodLog proof — 2026-09-28

Status: **successful unassisted isolated proof; Sanctum Work Mode integration and
Human Review acceptance remain open**. The owner approved one new paid window
after merging the third proof report. This was one run with no automatic retry.
PR #150's context-retention change has still not had a live retry through the
existing Work Mode agent loop.

## Two execution paths and limits

Qwen Code 0.24.6 used its [headless coding run](https://qwenlm.github.io/qwen-code-docs/en/users/features/headless/).
Its OpenAI-compatible provider setting addressed a Mac stdio broker, which
forwarded only `/v1/models` and `/v1/chat/completions` to the existing private
122B vLLM server through a Mac-managed loopback tunnel. This was a direct model
connection, not a Sanctum gateway endpoint. Qwen's read, edit, write, and shell
tools ran in a disposable OCI container on a copy of the candidate. The
container was non-root, networkless, had a read-only root, dropped capabilities,
no new privileges, CPU/memory/PID limits, and no host home, credentials, Docker
socket, or host workspace mount. Permission settings and prompt wording did not
form the security boundary; the container and Mac broker did.

Qwen had a 48-turn, 40-tool-call, 20-minute headless cap. The independent Mac
runner had a 40-minute wall deadline, 48 model-request cap, 900-second inference
cap, bounded request/response sizes, no model retry, one workload, and explicit
GPU acquire/release/sweep. Preflight price was $2.09/hour; the measured allocation
to confirmed pod absence was 563.2 seconds, approximately $0.327, below the
owner's 45-minute and $50 ceilings. No second paid run was started.

## Preserved task and observed outcome

The untouched private MoodLog baseline was clean at
`b3b0ce7371639a5fd1829f60b53b23cb0a9e9870`. The same seeded UI fixture,
protected `persistence.test.cjs` oracle, task, and pinned Sanctum test runner as
the earlier comparisons were used. Baseline: 8/11 ordinary tests passed and all
4 protected tests passed. The failures were UI persistence across fresh
instances, newest-five persistence/malformed storage, and denied-storage
warnings.

Qwen ran unassisted and exited normally after 37 model requests, all HTTP 200.
Its trace contains 18 file reads, 14 edit attempts, one write, and two shell
commands. Five tool calls reported errors; Qwen continued and made actual edits
to `index.html`, `index.js`, `README.md`, and `storage.js`. Its shell commands
checked `index.js` syntax and ran the ordinary Node tests. The Mac's independent
pinned runner then passed **11/11 ordinary** and **4/4 protected** tests with no
skips. The protected oracle file was byte-for-byte unchanged. The four-file
unified diff was 5,258 bytes; raw source and patch bodies remain private.

An actual browser served the exact final candidate on loopback. Synthetic save
and reload retained the entry. Six saves displayed only the newest five in order
before and after reload. Clear and reload remained empty. The browser tab and
local test server were closed. The Node UI fixture covered malformed and denied
storage; the protected oracle covered the adapter. No browser-console capture or
manual browser injection of denied storage was recorded, so this is not the full
[Work Mode acceptance checklist](../../development/WORK-MODE-MOODLOG-ACCEPTANCE.md).
The final Qwen message was not used as pass evidence.

The Qwen container was removed. The private lead is OFFLINE with zero leases,
active requests, and provider pods; the persistent volume was retained. The
independent janitors remained loaded. Exact executed runner, broker, settings,
prompt, Dockerfile, model traffic, Qwen tool trace, baseline/result checks, final
candidate, and browser observation are mode-0600 private evidence under
`$SANCTUM_PRIVATE_PREFIX/state/qwen-code-poc-20260929/live-20260928-214912/`.
No raw prompts, source bodies, or private evidence are committed here.

## What this proves and what remains

The previous assisted MoodLog success did not establish autonomous coding. The
first isolated Qwen attempt hit a model/broker HTTP 400; the second stopped in
read-only loop detection; the third edited but exhausted the 32-request Mac cap
after a failed test. This fourth run is the first unassisted isolated result to
make the required edit and pass both independent test sets and observed browser
reload behavior. It does not establish that Qwen Code is Sanctum Work Mode.

The current `/work` path owns the task, workspace, semantic tool authorization,
budget, protected evaluator, reviewer, ledger, and Human Review transition.
Qwen's internal tool loop wrote to a separate container snapshot. That snapshot
was never imported into a `/work` task; no Work Mode authorization, evaluator,
reviewer, receipt, or Human Review decision consumed it. Merely pointing Qwen
at the model, or mounting a Mac worktree into its container, would not close
that gap safely.

The narrow integration is a Mac-owned Qwen worker path under `/work`: create a
task-bound workspace and immutable input snapshot; copy only that snapshot into
the pinned isolated container; run headless Qwen under its own and the Mac's
independent limits; collect a no-follow final inventory; require the unchanged
starting snapshot/task identity and protected inputs; import only an exact,
bounded diff through the existing Mac patch authority; then run the existing
protected evaluator, independent reviewer, ledger/receipt, and Human Review
transition. Every failure or uncertain import must stop closed with private
trace and cleanup. This needs a distinct integration and contract test surface,
including snapshot swaps, symlinks, protected edits, oversize patches, process
timeouts, budget aborts, and partial import/rollback. No new paid qualification
is implied by this proof.

## Reproduction on the owner's Mac

The exact private runner assets and final evidence directory above are retained
outside Git. From the preserved clean candidate at the commit above, inspect the
recorded `baseline.json` and asset hashes, ensure independent janitors are loaded
and private lead/provider ownership is empty, then run the private one-shot
`run_poc.py` once inside a separately approved ≤45-minute, <$50 window. It
creates a fresh private evidence directory, runs baseline and final checks in
the pinned Sanctum runner, bounds both Qwen and Mac execution, and confirms
container/GPU cleanup. The `--mock` path exercises orchestration without paid
compute. Do not use `qwen serve` for this unattended test. A new live run needs
fresh owner approval and must not overwrite or retry this evidence.
