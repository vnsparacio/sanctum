# Completing the guided MoodLog POC

The [milestone](../history/v1.3/WORK-MODE-MOODLOG-MILESTONE.md) records a working
in-memory UI, one accepted logic checkpoint, failed UI tests and absent reload
persistence. This procedure continues that exact private candidate. It does not
claim that the remaining application code has been implemented or qualified.

## Reviewed source preparation

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

## One focused continuation task

1. Preserve the previous candidate and hashes outside Git. Create a new private
   repository from its exact unchanged app files; do not supply a repaired app.
   Inspect/record its baseline before committing. The old failed task remains a
   failed historical result. A new task starts from the new private baseline;
   no automatic retry or reset of the old task's budget is implied.
2. Copy the reviewed
   [persistence oracle](../../gate/qualification/moodlog/persistence.test.cjs)
   unchanged into the candidate root as `persistence.test.cjs`. Commit it as
   owner acceptance input, distinct from Qwen's mutable tests. Never copy the
   repository's synthetic oracle-calibration implementation into the candidate.
3. Register a **new, unstaged** private profile through `scripts/configure.py`
   using an existing reviewed base with no `stages`, its fixed Node test
   command, and the
   [protection contract](../../gate/qualification/moodlog/task-protection.json).
   A registration copies unspecified fields, so do not copy `moodguided` and
   accidentally retain all three stages. The protected test must be immutable
   and its four named tests must execute under `node-test-v1`. Preserve the
   existing logic/UI candidate tests; no skip/delete workaround.
4. Inspect the resulting profile: reviewer enabled, no stages, correct private
   repository/staging paths, protected oracle and fixed commands. Use explicit
   limits no greater than 32 implementation calls, 200,000 total tokens and
   1,200 task seconds, with finite inference/cost limits. Set supported budget
   amendments while stopped, never by editing runtime JSON. The next live run
   needs its own explicit outer deadline (at most 45 minutes for this procedure),
   owner hold and cleanup supervision; retain the owner's spending ceiling.
   Prepare model readiness inside that window before task admission where
   practical so cold startup does not consume the task's entire useful time.
5. Submit `/work start PROFILE -- ` followed by the
   [focused task](../../gate/qualification/moodlog/task.txt). Qwen must repair
   `ui.test.js` using `node:test`, `node:assert/strict` and a small DOM double,
   then implement and wire persistence. It must read actual files and APIs;
   no operator-authored persistence implementation is supplied.
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
