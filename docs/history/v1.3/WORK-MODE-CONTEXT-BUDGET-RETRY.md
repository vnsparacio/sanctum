# MoodLog RTX retry and request budget — 2026-09-27

The single bounded retry on merged PR #130 reached model readiness and made six
successful read-only calls. It did not edit the application or reach acceptance.
The previous partial MoodLog milestone remains the latest application result.

## Newly observed live behavior

- Source: `2176cccdcb46957c925670d84e77df8b90a17d9a` on `v1.3-dev`.
- One RTX allocation at $2.09/hour; cache-only model startup succeeded with the
  explicit DeepGEMM disable setting. This does not qualify B200 startup.
- The owner-approved outer window was 45 minutes/$6, with a 42-minute hold and
  three-minute cleanup reserve. The independent janitor remained enabled.
- The unstaged continuation used the preserved partial candidate, immutable
  persistence oracle, reviewer, and reviewed focused task. Limits were 32 calls,
  200,000 tokens, 1,200 task seconds, 900 inference seconds and $1.50 task cost.
- Six model calls listed the workspace and read `logic.js`, `index.js`,
  `index.html`, `ui.test.js`, and `persistence.test.cjs`. The task then stopped
  with `ENVIRONMENT_FAILURE / PRIVATE_LEAD_UNAVAILABLE`; no provider code was
  retained. No edits or acceptance checkpoint completed.
- Task telemetry recorded 28,781 prompt tokens, 897 completion tokens and
  17.70 inference seconds. The task's inference-only estimate was $0.01475;
  allocated compute through confirmed deletion was approximately **$0.3034**.
  These are estimates, exclude persistent storage, and are not an invoice.
- Candidate hashes matched the baseline. Candidate files, task summary/events,
  content-minimized decision trace, server log and cleanup evidence were saved
  outside Git. `/work end` confirmed workspace removal and GPU OFFLINE; a fresh
  provider listing independently confirmed zero pods. Local test services were
  stopped. Persistent remote storage was retained.

## Replay-supported diagnosis

The installed worker caps the canonical UTF-8 `{system, request}` packet at
32,768 bytes. The coordinator previously bounded only the user message at
64,000 characters, with up to six observations. Profile text, schemas, other
request fields and multibyte characters also count toward the worker limit.
The adapter mapped `private_lead_proposal_limit` to generic runtime loss.

An offline reconstruction using the same ordered reads, preserved file contents,
profile and coordinator produced packet sizes of 11,984; 12,875; 15,931; 21,321;
23,808; 29,138; and **33,679 bytes**. The seventh exceeds the worker limit. This
is a reproducible explanation consistent with six completed calls, not a claim
that the exact failed wire packet or raw worker refusal was retained. The
reconstruction approximated listing metadata. Server logs show successful
inference responses, without a new startup failure.

## Source correction and its limits

The PRIVATE_LEAD adapter now checks the full canonical UTF-8 packet against the
configured worker cap (including its 196,608-byte ceiling). If needed, it removes
whole oldest disclosed observations from a copy of the implementer request.
The newest observation, task, instructions, schemas, file facts, latest test
state and completion constraints remain intact. An omission count tells the
model that earlier observations were removed. The authoritative coordinator
state and result-egress decisions are unchanged; no content is fetched or newly
disclosed. Existing coordinator/request shape guards remain in force.

An irreducible packet stops before dispatch with
`BUDGET_EXHAUSTED / MODEL_CONTEXT_LIMIT`. The exact worker refusal maps to the
same outcome. Review evidence is never trimmed; oversized review packets also
stop without accepting completion. No byte cap, runtime pin, capability,
evaluation requirement or paid retry allowance is increased.

Applying the correction to the reconstructed seventh request produces
**29,828 bytes**, omitting two older observations while preserving the newest
read and leaving the original request unchanged. Synthetic regressions cover
full-envelope overhead, Unicode, exact limits, the worker ceiling, withheld
results, unchanged host state, pre-dispatch refusal, worker-refusal mapping and
review failure. This is offline verification; the corrected adapter has not
been qualified by a new live MoodLog run.

The intentional source freeze covers the adapter, coordinator, settings wiring,
regressions, acceptance guide and this report. Runtime pins remain unchanged.
After owner review/merge and a supported stopped-gateway upgrade plus doctor,
follow the [acceptance procedure](../../development/WORK-MODE-MOODLOG-ACCEPTANCE.md)
for a fresh bounded attempt. Full persistence/UI acceptance is still open.
