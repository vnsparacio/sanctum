# MoodLog progress retry and output-budget repair

Status: historical live failure plus a source repair; full acceptance remains pending.

## Observed live result

The 2026-09-28 continuation used merged PR #133 (`ca2a3fb`) and the exact
nine-file Qwen storage milestone, without an operator-written application fix.
Independent isolated tests confirmed logic and the four protected persistence
checks passed; UI tests still imported unavailable `jsdom`.

The first stage made five valid read calls, followed by an incomplete sixth
response with `finishStatus=length`. The coordinator stopped at
`BUDGET_EXHAUSTED / MODEL_OUTPUT_LIMIT` after about 106 seconds, with no edits
and no completed checkpoints. All nine file hashes remained unchanged. Partial
response content was not retained, so the intended sixth action is unknown.
Repeated read compaction was observed; this did not qualify application execution.

The receipt included only the five valid responses: 27,323 prompt tokens, 885
completion tokens and about 17.13 inference seconds. It omitted usage and time
for the failed sixth call. These totals are incomplete, not the full test cost.
Allocated compute was approximately $0.37 including startup, excluding persistent
storage. The pod was released, provider absence confirmed, leases and active
requests reached zero, and local test services stopped. Persistent cache remained.
Exact source, receipts and timeline remain in the external private evidence store.

## Source repair

Work Intent edit proposals now allow at most 512 UTF-16 code units in `old_text`
and 2,048 in `new_text`. The prompt teaches short unique replacements and larger
file assembly: create a small valid scaffold, read it, insert a small section at
a unique retained anchor, then read again before the next edit. The underlying
file tool still has its original limits and authority checks.

The pinned decoder intentionally omits string-length constraints because its
handling of JSON escapes is incompatible with them. The Mac validates complete
proposals against the smaller semantic limits before authorization. The prompt
also carries the numeric limits explicitly. These character budgets reduce output
pressure; they do not guarantee a fit for every tokenization. The response ceiling
remains 4,096 tokens. Truncated output never executes and does not automatically
retry or extend a budget.

The worker retains allowlisted numeric usage and timing on failed responses,
including usage arriving after a streaming `length` finish. The caller records
one telemetry event per dispatch before parsing or rejecting the result, for
implementer and reviewer calls. Coordinator attempt counts include failures;
pre-dispatch context-fitting refusals still count zero. No partial source, arbitrary
provider fields or hidden reasoning is persisted by this telemetry path.

Missing or invalid usage remains unknown. Task summaries expose
`usageIncompleteCalls` and `timingIncompleteCalls`; accumulated token/time/cost
values are lower bounds when the corresponding fields are missing. HTTP rejection
is a counted dispatch attempt, not evidence that model generation occurred.
Reported usage reaches the existing shared budgets before another call can start.
The independent wall-clock/allocation controls remain necessary when usage is absent.

## Qualification boundary and next attempt

Synthetic tests cover the real Python worker and signed caller transport,
truncation with trailing usage, malformed output, missing/invalid usage, reviewer
accounting, semantic size boundaries and multi-edit file assembly through the
fresh-read guard. They establish host contracts, not Qwen's ability to follow them.

After owner merge, use the supported stopped-gateway source upgrade, doctor and
schema preflight. Reuse the unchanged storage milestone and three-stage profile;
make one supervised bounded attempt, preserving protected tests and the shared
budget. Inspect failed-call accounting and whether small edits progress. Only host
completion, reviewer acceptance and the full real-browser checklist establish
[MoodLog acceptance](../../development/WORK-MODE-MOODLOG-ACCEPTANCE.md).

The source freeze covers only the reviewed implementation, tests and documentation
in this repair. Runtime pins, decoder settings, infrastructure and private runtime
configuration remain unchanged. No live inference is performed by this source PR.
