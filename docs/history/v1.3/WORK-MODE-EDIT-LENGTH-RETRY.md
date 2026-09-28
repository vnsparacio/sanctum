# Edit-length feedback retry — 2026-09-28

The single bounded MoodLog attempt on merged source `ac5af0f` stopped at
`SAFETY_POLICY_BLOCK / REPEATED_INVALID_PROPOSAL` after seven model calls.
The improved diagnostics identified the offending field and limit correctly,
but Qwen still produced two oversized edits. No files changed and no checkpoint
completed. This qualifies live diagnostic accuracy, not edit recovery or full
application acceptance.

## Preparation and bounds

Merged-source dependency, build, test, audit and source-integrity checks passed.
The supported stopped-runtime upgrade and doctor passed; the owner's unrelated
workflow edit was preserved. All nine baseline file hashes remained unchanged.
A fresh isolated test run passed logic and all four protected storage cases,
while the UI suite failed on unavailable `jsdom`. No operator app repair or new
package was supplied.

The same three-stage profile retained 32 calls, 200,000 reported tokens, 1,200
task seconds, 900 inference seconds, a $1.50 inference estimate and required
reviewer acceptance. The single cache-only RTX PRO 6000 allocation cost $2.09/hour
within the 45-minute/$6 outer window. Autostart stayed off; the independent
janitor remained loaded. Weights loaded in 127.03 seconds and compilation took
37.61 seconds. Managed readiness passed before submission.

The chat's **Controls → Advanced Params → Function Calling → Legacy** setting
was checked before allocation. The first submission admitted the only task;
there was no admission correction, second task or allocation retry.

## Observed result

Qwen made five successful reads, followed by two rejected `worktree_edit`
proposals. Both diagnostics and proposal summaries now agreed on `old_text`,
`maxLength`, received length 1,636 and limit 512 UTF-16 code units. The existing
single correction attempt used the reviewed fixed small-edit guidance. It did
not produce a valid edit. The second proposal had the same offending length;
raw rejected proposals were not retained, so identical contents cannot be
established from that fact.

All seven calls reported `QWEN35_INSTRUCT_V1`, complete streams and parsed
responses. The non-thinking preset remained temperature 0.7, top-p 0.8, top-k 20,
min-p 0, presence penalty 1.5 and repetition penalty 1.0, with a 4,096-token output
cap. There was no observed output truncation or missing usage/timing on this run.

| Measurement | Observed result |
| --- | --- |
| Task elapsed time | 103.98 seconds |
| Model calls | 7 |
| Prompt / completion tokens | 44,141 / 3,511 |
| Inference time | 57.75 seconds |
| Missing usage / timing calls | 0 / 0 |
| Inference estimate at configured ceiling | $0.04813 |
| Allocated compute through confirmed deletion | $0.31753 |
| Executed edits / completed checkpoints | 0 / 0 |

Inference time is contained within allocated compute time; these cost estimates
must not be added. Allocated compute excludes persistent storage and is not an
invoice. Model decision notes described dependency removal as though it had
occurred. These are untrusted explanations: execution receipts, all nine final
hashes and the empty Git diff establish that no edit ran. No model-requested
tests, reviewer acceptance or browser acceptance occurred.

## Cleanup and next decision

Candidate files, hashes, baseline tests, source revision, startup evidence,
decision trace and receipts were preserved outside Git. `/work end` confirmed
workspace cleanup. Managed stop ended the owner hold; its `manual_stop` exit was
expected cancellation. Independent provider listing found no pods. Lifecycle
was OFFLINE with zero leases and active requests; local services were stopped.
The cache volume and independent janitor were retained.

Another unchanged paid retry is not justified by this result. The next source
investigation should reduce the edit interface's dependence on obeying prose:
the current generation projection intentionally omits string-length constraints
because the pinned grammar rejects valid JSON escapes; the Mac still enforces
them. Simply restoring `maxLength` would reintroduce that known incompatibility.
Assess a bounded edit selection interface using host-issued references to freshly
disclosed source, with exact source/generation validation, or an escape-correct
grammar implementation tested against the pinned runtime. Either approach needs
reviewed tests; neither is implemented or qualified by this run. Retain output/task bounds,
protected tests and Mac authority. Do not silently truncate, widen permissions,
execute a rejected proposal or treat a model's success claim as evidence.

See the [preceding preset run](WORK-MODE-UPSTREAM-PRESET-RETRY.md),
[reviewed edit-length repair](../../development/WORK-MODE-UPSTREAM-RECIPES.md#edit-length-recovery-before-the-next-run)
and [full acceptance checklist](../../development/WORK-MODE-MOODLOG-ACCEPTANCE.md).
