# Upstream preset retry — 2026-09-28

The single bounded MoodLog run on merged source `c0fc0df` stopped at
`SAFETY_POLICY_BLOCK / REPEATED_INVALID_PROPOSAL`. It made six successful reads,
then two invalid proposals, with no executed edits or completed checkpoints.
The upstream preset is now observed in live inference; coding acceptance remains
open. This is not evidence that temperature alone improved or worsened coding.

## Preparation and admission

The stopped-runtime upgrade, source validation, audit, doctor and production
schema preflight passed. The owner's unrelated workflow edit was preserved.
The exact nine-file Qwen storage baseline was unchanged. A fresh run in the
isolated runner confirmed logic and all four protected storage cases pass while
the UI suite fails on unavailable `jsdom`. No operator app repair was supplied.

The existing three-stage profile retained shared limits of 32 calls, 200,000
reported tokens, 1,200 task seconds, 900 inference seconds and a $1.50 inference
estimate, with reviewer required. One cached RTX PRO 6000 allocation at $2.09/hour
ran inside the 45-minute/$6 outer window. Autostart stayed off and the independent
janitor remained active. Initial readiness took about 5.9 minutes; weights loaded
in 130.6 seconds and compilation took 37.2 seconds.

The first WebUI submission was rejected before task creation because the chat's
default native-function setting introduced implicit WebUI tools. Selecting
**Controls → Advanced Params → Function Calling → Legacy** removed that extra
input. The identical owner command then admitted the only task. This was an
admission correction, with no second allocation or model-task retry. Future
preflight should check this setting before paid allocation; the Mac gate's
extra-tool rejection must remain intact.

## Observed model behavior

All eight calls reported `QWEN35_INSTRUCT_V1`, complete streams and parsed responses.
The fixed non-thinking preset was temperature 0.7, top-p 0.8, top-k 20, min-p 0,
presence penalty 1.5 and repetition penalty 1.0, with the 4,096-token output cap.

After six reads, the seventh and eighth responses were rejected by the host's
argument schema. Both structured diagnostics reported `maxLength`, with string
lengths of 1,636 and 1,724 UTF-16 code units. The diagnostic field was `UNKNOWN`;
the parallel proposal summary instead reported keyword `type` and no field.
The eighth response contained 3,778 completion tokens and ended normally. This
run did not hit the previous output-truncation failure.

Decision notes described replacing the unavailable dependency with a DOM double,
but these are untrusted model explanations, not executed edits or private
reasoning. Rejected raw proposals were not retained, so the exact offending
field and full proposed implementation cannot be reconstructed from these
receipts. All nine final file hashes matched the baseline and Git diff was empty.
No model-requested tests, reviewer acceptance or browser acceptance occurred.

| Measurement | Observed result |
| --- | --- |
| Task elapsed time | 136.75 seconds |
| Model calls | 8 |
| Prompt / completion tokens | 51,408 / 6,130 |
| Inference time | 96.12 seconds |
| Missing usage / timing calls | 0 / 0 |
| Inference estimate at configured ceiling | $0.08010 |
| Allocated compute through confirmed deletion | $0.39185 |

The inference estimate is a different accounting view of time within the paid
allocation; do not add it to allocated compute. Allocated compute excludes
persistent storage and is not an invoice. Complete accounting was observed on
these parsed calls; failed-stream usage propagation remains synthetically tested,
not newly exercised by this run.

## Cleanup and next repair

The candidate, hashes, baseline tests, source revision, startup log, decision
trace and receipts were preserved in the external private prefix. `/work end`
confirmed workspace cleanup. Managed stop closed the owner hold; its
`manual_stop` exit was expected cancellation. Independent provider listing found
no pods, with lifecycle OFFLINE, zero leases and zero active requests. Local
services stopped; the persistent cache volume and janitor were retained.

Before another funded test, make schema correction actionable: allowlist the
fixed edit-field names, report the applicable length bound and the actual
validation keyword, and provide fixed guidance for one short exact replacement.
Cover nested edit-operation schema selection and oversized replacement recovery
with synthetic fixtures. Retain the same response cap, task bounds and Mac
validation; do not truncate or execute rejected content or infer success from
decision notes. More generic prompting or another identical retry is not yet
justified by this result. Any decoder-side length enforcement requires a
compatible reviewed grammar change; it is not established by this experiment.

See the [preset and provenance](../../development/WORK-MODE-UPSTREAM-RECIPES.md)
and [full acceptance checklist](../../development/WORK-MODE-MOODLOG-ACCEPTANCE.md).
