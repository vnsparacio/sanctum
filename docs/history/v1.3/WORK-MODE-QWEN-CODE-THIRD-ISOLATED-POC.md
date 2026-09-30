# Qwen Code third isolated MoodLog proof — 2026-09-28

Status: **failed isolated proof; no Sanctum Work Mode integration or autonomous
MoodLog acceptance**. The owner explicitly approved this one new bounded paid
window after merging the second proof report. No automatic retry followed.
PR #150's context-retention change still has no live retry through the existing
Work Mode agent loop.

## Paths, baseline, and limits

The model path was Qwen Code 0.24.6 to a Mac stdio broker to the existing
private 122B vLLM OpenAI-compatible endpoint through the Mac-managed loopback
SSH tunnel. The Sanctum gateway did not expose that endpoint. The coding-tool
path was Qwen Code's headless read, edit, and shell tools inside a non-root,
networkless OCI container with a read-only root, dropped capabilities, resource
limits, and a copied MoodLog snapshot. It had no host mount, home, credentials,
Docker socket, or external network. Qwen's prompt and permission mode were not
used as a security boundary.

The clean nine-file candidate started at
`b3b0ce7371639a5fd1829f60b53b23cb0a9e9870`, with 8/11 ordinary tests and
4/4 protected tests. The exact task, candidate, and acceptance contract from
the prior runs were reused. No human edited candidate files during the run.
Qwen's provider config declared the 32,768-token model context, a 4,096-token
output cap, 0.60 auto-compaction threshold, and the documented default of
skipped streaming loop detection. The previous premature detector stop did not
recur.

Qwen had its own 48-turn, 40-tool, and 20-minute headless limits. Independently,
the Mac allowed at most 32 model requests, 900 seconds of cumulative inference,
a 40-minute outer deadline, one allocation, and the owner-approved 45-minute
and $50 window. The host controlled lease heartbeat, janitor, protected checks,
snapshot collection, and cleanup. A no-cost mock passed before allocation.

## Observed coding and acceptance

Qwen made 32 successful model requests, all HTTP 200. The 33rd was refused by
the Mac broker before upstream inference because it exceeded the independent
request cap. Qwen made 18 reads, 13 edit attempts, and two shell calls. Its
edits changed `storage.js`, `index.html`, `index.js`, and `README.md`; the
protected oracle file stayed byte-for-byte unchanged. Six edit attempts failed
and were followed by further reads or edits. Qwen ran `node --check` successfully
and then `node --test`, which reported one failure. It read the failing UI test
before the host stop. It had no final answer because the broker ended the run.

The Mac's pinned, networkless Work Mode test runner independently found **10/11
ordinary tests passing** and **4/4 protected tests passing** in the final
snapshot. The sole ordinary failure is the basic UI clear case: with no storage
object in its DOM double, the UI shows `Warning: Failed to clear storage.` when
the test expects `History cleared.` The denied-storage warning test, save/reload
integration test, newest-five test, and storage oracle passed. Those UI tests
execute the real app scripts in a controlled DOM double; no separate real-browser
reload check was performed after the failing suite. The result does not meet the
required all-tests and app/reload acceptance, even though it progressed well
beyond the earlier zero-edit unassisted Work Mode stalls.

This stop is a host **workload-budget exhaustion with an unfinished task**.
There was no observed model HTTP error, context overflow, or repeated-read loop.
The trace cannot establish that another call would have fixed the last test.
The exact executed script with the 32-call cap is frozen in private evidence.
After the run, the private working script's cap was raised to 48 requests while
retaining Qwen's 40-tool limit, 900-second inference limit, 40-minute outer
deadline, and one-window/no-retry rule. A no-cost mock passed. That correction
has **not** had a paid MoodLog qualification.

## Cleanup, evidence, and remaining authority gap

The raw prompt, source bodies, original requests, broker responses, Qwen tool
stream, executed asset copies and hashes, baseline and final snapshots, test
outputs, and cleanup state remain outside Git under
`$SANCTUM_PRIVATE_PREFIX/state/qwen-code-poc-20260929/live-20260928-203246`.
The container was removed. The managed GPU ended `OFFLINE` with zero leases,
zero active requests, and zero provider pods; its persistent model volume was
retained. Allocation to confirmed pod absence took 563.2 seconds, approximately
$0.327 at the observed $2.09/hour, excluding retained storage and provider
adjustments. There was one allocation and no task retry.

This is still **not Sanctum Work Mode**. Qwen edited only a disposable snapshot.
No Mac-authorized import applied its diff to a Work Mode workspace, and no
Work Mode evaluator, separate reviewer, receipt-based `COMPLETE`, or Human
Review transition occurred. Integration still needs a reviewed snapshot-import
capability with path/type/scope, protected-file, exact-diff, and workspace-
generation checks, or a bridge that sends each Qwen tool action through existing
Mac semantic capabilities. Sanctum must continue to own authorization, budgets,
protected tests, validation, evidence, reviewer decisions, and Human Review.
A direct model connection is insufficient.

For a no-cost transport check, run the private
`state/qwen-code-poc-20260929/run_poc.py --mock` against the preserved baseline.
The exact live invocation omitted `--mock`; its executed assets are frozen in
the private evidence directory. Another paid run requires a new explicit
owner-approved window and the same clean baseline and protected checks.
