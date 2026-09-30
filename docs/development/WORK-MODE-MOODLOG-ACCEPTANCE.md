# Completing the guided MoodLog POC

The [first milestone](../history/v1.3/WORK-MODE-MOODLOG-MILESTONE.md) records a working
in-memory UI. The [storage milestone](../history/v1.3/WORK-MODE-STORAGE-MILESTONE.md)
adds a Qwen-authored helper that independently passes all four protected tests.
The later owner-seeded baseline has repaired UI tests, but still needs Qwen to
integrate persistence. Continue that exact preserved baseline; full autonomous
acceptance is still open.

The [fourth isolated Qwen Code proof](../history/v1.3/WORK-MODE-QWEN-CODE-FOURTH-ISOLATED-POC.md)
did integrate persistence unassisted and passed the ordinary and protected tests
plus observed browser save/clear/reload behavior. It ran on a disposable snapshot
outside Sanctum Work Mode. Host task authorization, import, evaluator, reviewer,
receipt, and Human Review acceptance remain open.

## Current continuation after the JSDOM repair

The [first bounded unassisted post-UI run](../history/v1.3/WORK-MODE-UNASSISTED-INSPECTION-RETRY.md)
stopped after 10 repeated file reads and no edit. The follow-up checkpoint now
requires `logic.js` and gives Qwen a small first collision repair before the
broader UI wiring. The merged checkpoint received one live qualification run;
it did not establish autonomous acceptance.

The [next bounded retry](../history/v1.3/WORK-MODE-CONTEXT-RETENTION-RETRY.md)
read `logic.js` but again stopped without an edit. A local packet replay showed
that the 32 KiB Work Mode request evicted earlier source bodies after the fifth
read. The proposed 48 KiB Work Mode-only cap is a testable recovery, not yet
live-qualified. Keep the same protected oracle, reviewer and aggregate limits
for the next owner-reviewed run. After merge, apply reviewed source through the
stopped-gateway Work Mode upgrade, run doctor and inspect the private profile;
a larger packet alone does not establish UI acceptance.

The [assisted result](../history/v1.3/WORK-MODE-MOODLOG-ASSISTED-RESULT.md)
separates the working human-assisted copy from the unfinished model-produced
baseline. The operator fixed the test environment with the
[Node-only UI fixture](../../gate/qualification/moodlog/ui.test.js), then seeded
that fixture into a separate private candidate with the existing app and
protected oracle. The fixture runs the real scripts named by `index.html`; it
needs only Node built-ins. Do not install JSDOM or alter the isolated runner for
this candidate. The baseline UI integration tests should fail on missing
persistence, while the logic and protected storage tests pass. This is the
intended starting condition for another model continuation.

Use the [two-stage post-UI plan](../../gate/qualification/moodlog/post-ui-stages.json)
and [post-UI task](../../gate/qualification/moodlog/post-ui-task.txt) for that
baseline. The operator already registered an equivalent private profile while
the gateway was stopped and ran doctor; one task ran under the previous staged
goal and stopped before making an edit. For a new
private candidate, copy the reviewed UI fixture to `ui.test.js` beside its real
app scripts and commit that qualification input before admission. Keep
`persistence.test.cjs` byte-for-byte unchanged and protected by
[task-protection.json](../../gate/qualification/moodlog/task-protection.json).
Create a private `scripts/configure.py --proposal` document with a
`work_profile` amendment: `name`, `copy_from` the reviewed profile,
`repository` set to the exact private baseline, and `stages` equal to the
two-stage JSON array. Apply it only with the gateway stopped; inspect its
resolved repository, test command, protection, reviewer and aggregate limits,
then run `make doctor PREFIX=/absolute/private/prefix`. Preserve the existing
bounded time, call, token and spending limits and independent cleanup hold.

The first checkpoint must make an actual persistence change to the app. An
already-passing test-repair checkpoint with a required nonempty diff caused the
last comparison to stop before persistence work. Do not add a gratuitous edit or
weaken completion evidence to satisfy that obsolete checkpoint. The older
three-stage procedure below remains historical guidance for a candidate whose
UI test still imports JSDOM; it is not the plan for the current seeded baseline.

## Reviewed source preparation

The [progress recovery plan](WORK-MODE-PROGRESS-PLAN.md) records the current
coordinator fix, next qualification steps and likely blockers. Disclosed edit/check
reminders now survive result eviction, newer reads replace older bodies for the
same path, and repeated unchanged reads receive guidance before a bounded stall
stop. These contracts need live Qwen qualification on the staged continuation.

Work Mode now gives each call up to 32 compact file-existence reminders derived
only from results already allowed through result egress. They survive the
six-result observation window, record their observed workspace generation, and
reset for each checkpoint. Successful arbitrary patches clear them. They are
historical hints, not a new filesystem read, authorization or replacement for
fresh source observation. Omitted and withheld results add no reminders.

The latest disclosed test result now says whether it matches the current
workspace generation. After edits it remains historical failure evidence,
not current validation. Missing-module diagnostics select fixed recovery text:
check local imports, use available built-ins and small browser test doubles,
or report a blocker if a reviewed external dependency is essential. Raw package
names/output are not added to this durable summary. Diagnostic text is untrusted
and cannot authorize installation, expand capabilities, pass an evaluator or
change a budget. No dependencies are added to the runner by this change.

Apply reviewed, owner-merged source through the supported stopped-gateway Work
Mode upgrade and run doctor before using these changes. Keep autostart off and
use the existing cache. See [configuration](../guides/configuration.md).

The [off-peak B200 retry](../history/v1.3/WORK-MODE-B200-STARTUP-RETRY.md)
failed during optional DeepGEMM warmup before admitting a task. The launcher
now explicitly disables that backend for the pinned NVFP4/CUTLASS path.
Synthetic launch tests pass. The subsequent storage-milestone run qualified
B200 readiness and inference once; cold-start speed and availability remain variable. A package upgrade or second allocation is not an automatic
recovery step. Preserve startup failures and confirm cleanup before retrying.

The subsequent [RTX request-budget retry](../history/v1.3/WORK-MODE-CONTEXT-BUDGET-RETRY.md)
reached readiness but stopped after six reads and no edits. PRIVATE_LEAD now fits
its entire UTF-8 request to the configured worker byte cap, omitting only older
disclosed observations while retaining the newest result and host state. An
irreducible request stops as `MODEL_CONTEXT_LIMIT`; review evidence is never
trimmed. The subsequent B200 storage-milestone run passed the former six-call
failure boundary and made edits, but exhausted its aggregate token budget.
This qualifies the corrected path on that run, not full application acceptance.

## Earlier three-stage continuation plan

1. Preserve the latest storage-milestone candidate and hashes outside Git.
   Create a new private repository from its exact unchanged app files, including
   Qwen's `storage.js` and partial `index.js`; do not supply a repaired app.
   Inspect/record its baseline before committing. The old failed task remains a
   failed historical result. A new task starts from the new private baseline;
   no automatic retry or reset of the old task's budget is implied. Run the fixed
   isolated test command on this preserved baseline before admission: expect four
   protected storage tests and logic to pass, with UI failing on `jsdom`. If the
   result differs, investigate the candidate identity first.
2. Copy the reviewed
   [persistence oracle](../../gate/qualification/moodlog/persistence.test.cjs)
   unchanged into the candidate root as `persistence.test.cjs`. Commit it as
   owner acceptance input, distinct from Qwen's mutable tests. Never copy the
   repository's synthetic oracle-calibration implementation into the candidate.
3. Register a **new staged** private profile through `scripts/configure.py`
   using the reviewed unstaged `moodaccept` profile as its base, the same fixed
   Node test command and
   [protection contract](../../gate/qualification/moodlog/task-protection.json).
   Explicitly set `stages` to the array in
   [continuation-stages.json](../../gate/qualification/moodlog/continuation-stages.json);
   do not inherit the old broad `moodguided` goals. These checkpoints repair UI
   tests, integrate persistence, then document the result. The protected test
   must stay immutable and its four named tests must execute under `node-test-v1`.
   Preserve existing logic/UI coverage; no skip/delete workaround.
4. Inspect the resulting profile: reviewer enabled, the exact three stages,
   correct private repository/staging paths, protected oracle and fixed commands. Use explicit
   limits no greater than 32 implementation calls, 200,000 total tokens and
   1,200 task seconds, with finite inference/cost limits. Set supported budget
   amendments while stopped, never by editing runtime JSON. The next live run
   needs its own explicit outer deadline (at most 45 minutes for this procedure),
   owner hold and cleanup supervision; retain the owner's spending ceiling.
   Prepare model readiness inside that window before task admission where
   practical so cold startup does not consume the task's entire useful time.
5. Submit `/work start PROFILE -- ` followed by the
   [continuation task](../../gate/qualification/moodlog/continuation-task.txt).
   The older `task.txt` is retained as historical input to the unstaged attempt.
   Qwen must repair `ui.test.js` using `node:test`, `node:assert/strict` and a small DOM double,
   then wire the existing storage helper. It must read actual files and APIs;
   no operator-authored persistence implementation is supplied.
   Each checkpoint starts fresh context but shares calls, tokens, time and cost.
   A failed checkpoint stops the task; never reset its budget or skip a check.
6. Preserve the final files/hashes, result, tests and trace before `/work end`.
   Stop after one task: success, repeated blocker or budget exhaustion is a
   result to inspect, not permission for another allocation or a larger cap.

The oracle defines a small explicit storage boundary in `storage.js`:
`loadHistory(storage)`, `saveHistory(storage, entries)` and
`clearStoredHistory(storage)`, with guarded CommonJS exports and classic browser
compatibility. It requires a single JSON-array history key, newest-first entries
limited to five, valid mood/note/timestamp data, safe handling of malformed input,
persisted clearing, and explicit failure for unavailable storage. A fresh module
instance must load previously saved data. It supplies tests, not application
implementation. The model must load the script before the UI and integrate it
with real controls, including failure when accessing `window.localStorage`.

Run the oracle and candidate tests **inside the pinned isolated runner**. A Node
VM used by the oracle bounds adapter calls; it is not a security sandbox. Never
run a private candidate directly on the host. Synthetic oracle calibration is
credential-free and covers a passing control plus missing module/save/clear,
unbounded history, invalid records and false success on storage failure.

## Full acceptance checklist

Storage-helper tests alone cannot establish UI wiring or browser semantics.
Record all of these against the exact final Qwen candidate:

| Layer | Required evidence |
| --- | --- |
| Task | Host COMPLETE; protected integrity/execution/pass; reviewer ACCEPT; required lint/build/test pass |
| Tests | Existing logic tests preserved; real UI and storage tests execute; no missing packages, skipped tests or test shims |
| UI | Five moods; visible and accessible selection; labeled note; 120-character limit; keyboard operation; save with/without note and timestamp |
| History | Six synthetic saves retain newest five in correct order; readable timestamps; note text renders as text |
| Reload | Save multiple entries, reload the actual browser page, verify identical moods/notes/timestamps/order; save again and verify history still works |
| Clear | Clear history, reload, confirm it remains empty |
| Recovery | Corrupt/malformed stored records do not crash; storage denial/quota errors keep in-memory controls usable and show an honest persistence warning |
| Hygiene | No external packages/assets/API requests; browser console checked; README accurately describes operation and tests |
| Cleanup | Exact artifacts preserved; workspace removed; zero leases/active requests; provider pod absence independently confirmed; local test services stopped; persistent volume retained |

Use browser automation through the approved UI surface and synthetic data only.
Malformed/denied storage is covered at the adapter boundary by the protected
oracle; exercise browser integration through a controlled browser test fixture
or test double as well. Do not infer the real UI uses the adapter just because
its unit tests pass. Do not mark full acceptance when any row lacks evidence.
Record the result in Linear and a new dated sanitized report, retaining this
partial milestone unchanged. Owner review/merge and Done transitions remain
owner actions.

## Output-limit continuation

Before the next funded retry, follow the [output-limit repair report](../history/v1.3/WORK-MODE-OUTPUT-LIMIT-RETRY.md).
The previous merged progress retry changed no files and completed no checkpoints.
Use short exact edits or an incremental scaffold within the model-facing 512/2,048
code-unit limits; do not increase the 4,096-token response ceiling to force progress.
Check failed-call telemetry as well as successful calls. Any nonzero
`usageIncompleteCalls` or `timingIncompleteCalls` means the corresponding totals
are lower bounds; preserve the independent outer allocation deadline and spending
cap. These accounting improvements do not qualify the candidate or relax this
checklist.

The next candidate also adopts a published non-thinking sampling preset and focused
coding workflow guidance. Follow the [upstream recipe run plan](WORK-MODE-UPSTREAM-RECIPES.md)
for exact settings, provenance, shared limits and cleanup. Its live qualification
is recorded in the [upstream preset retry](../history/v1.3/WORK-MODE-UPSTREAM-PRESET-RETRY.md):
eight calls, no edits, and two length-invalid proposals. The
[edit-length recovery](WORK-MODE-UPSTREAM-RECIPES.md#edit-length-recovery-before-the-next-run)
now gives the existing correction attempt an exact field, length bound and fixed
small-edit guidance, with synthetic and signed-path coverage. Apply only reviewed,
merged source before the next bounded attempt. Upstream success and synthetic
recovery are not evidence that the live candidate has passed.

The [edit-length feedback retry](../history/v1.3/WORK-MODE-EDIT-LENGTH-RETRY.md)
qualified the field/limit diagnostics live, but stopped after seven calls with
two oversized `old_text` proposals and no edits. Small-edit feedback alone did
not recover this attempt. Investigate enforceable bounded edit generation before
another unchanged funded retry; full acceptance remains open.
