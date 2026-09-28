# MoodLog storage milestone — 2026-09-27

Qwen's new storage module passes all four protected persistence tests in an
independent isolated-runner check. This is a second **partial** application
milestone. The task itself exhausted its token budget before testing; the UI
suite still fails and browser persistence remains incomplete.

## Newly observed result

The owner-funded retry used merged source `49440c5` (PR #131), one B200 at
$6.79/hour, the existing persistent cache and a 45-minute/$6 outer limit with
cleanup reserve. Autostart stayed disabled. B200 reached readiness with the
reviewed DeepGEMM disable/CUTLASS configuration and then served real task calls.
Startup took about 22 minutes; checkpoint loading alone took 361 seconds on the
volume's FUSE filesystem. This qualifies readiness/inference on this allocation,
not fast startup or general B200 reliability.

The context-sizing correction passed its live failure boundary: the task went
beyond six reads, made edits and completed 27 model calls without the previous
packet-size refusal. It stopped as `BUDGET_EXHAUSTED / TOKEN_BUDGET` after about
242 seconds: 192,003 prompt tokens plus 8,066 completion tokens exceeded the
200,000-token aggregate limit. The last result was stopped before execution.
There were 21 executed reads, one listing and four edit attempts; three edits
succeeded and one duplicate create was refused. Only `storage.js` and `index.js`
differ from the baseline. The protected oracle is byte-for-byte unchanged.

The unchanged saved candidate was checked using the installed pinned command
runner: non-root, no network or host mounts, read-only root filesystem and a
copied workspace. It reported:

| Check | Result |
| --- | --- |
| Existing logic test file | Pass |
| Protected save/fresh-load/newest-five test | Pass |
| Protected clear/fresh-load test | Pass |
| Protected malformed/invalid-data test | Pass |
| Protected unavailable-storage test | Pass |
| UI test file | Fail: unresolved `jsdom` import |

These are independent post-task observations, not a host COMPLETE or reviewer
ACCEPT. `index.html` still omits `storage.js`; the UI diff only adds a startup
load attempt. Save/clear persistence and honest storage-error feedback are not
finished. No new browser acceptance is claimed and the operator did not repair
Qwen's code. Protected helper tests do not establish every integration behavior.

## What worked and what did not

The B200 startup fix, request-byte budget, edit authority, duplicate-create
refusal, token stop, private decision trace and cleanup all worked in this run.
The model produced a useful storage helper that survives the independent
protected tests.

The broad prompt asked for an initial tour of five files, then several unrelated
edits. Whole older observations must be omitted to stay within the packet cap.
The trace repeatedly describes missing file contents and requests another read,
including rereads before edits. A second create of the existing storage module
was safely refused. The resulting repetition consumed the token budget before
the package problem or UI integration was finished. This supports narrowing the
work; it is not evidence that a higher token cap will solve the problem.

The next reviewed continuation uses the exact saved Qwen candidate and three
existing host checkpoints: repair UI tests, wire/test persistence, document the
result. Each checkpoint gets fresh context while sharing the existing aggregate
limits. Its prompt asks for one file/change at a time and omits the up-front
reading tour. This prompting/decomposition change is not yet live-qualified;
it adds no packages, memory mechanism, authority or budget increase. See the
[acceptance guide](../../development/WORK-MODE-MOODLOG-ACCEPTANCE.md).

## Cleanup and retained evidence

The candidate, hashes, diff, task summary/events, decision trace, server log,
independent test result and UI cleanup screenshot were preserved privately.
The owner hold exited; `/work end` confirmed workspace cleanup and GPU OFFLINE.
An independent provider listing confirmed zero pods, and local test services
were stopped. The persistent volume/cache remain. Allocated-compute estimate:
**$3.1247**; task inference-only estimate: **$0.18024**. These are not invoices
and exclude persistent storage.

No second task or allocation followed this result. Full acceptance stays open.
