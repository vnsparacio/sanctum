# Work Mode milestone: guided MoodLog partial acceptance

Date: 2026-09-26 Pacific (2026-09-27 UTC). Decision record:
[TTE-96](https://linear.app/ttercode/issue/TTE-96/qualify-staged-moodlog-with-private-decision-traces-after-prs-126127).
Observed source: merged `d0a5768` after PRs
[#126](https://github.com/vnsparacio/sanctum/pull/126),
[#127](https://github.com/vnsparacio/sanctum/pull/127), and
[#128](https://github.com/vnsparacio/sanctum/pull/128).

This is the first observed browser-functional MoodLog POC in this sequence.
It is **partial acceptance**, not a completed application or evidence of reliable
unattended development. Qwen authored all candidate application code and tests.
The operator supplied decomposition, prompts, actual API names and edit
instructions, preserved the candidate, and independently tested its behavior.
No operator code repair was used to produce the browser result.

## What worked

- The reviewed runtime started the cached private Qwen model on RTX PRO 6000,
  performed inference and contained execution, and enforced bounded task stops.
- Three configured checkpoints separated logic, UI and persistence. In the
  guided attempt, logic passed the host evaluator and the separate reviewer
  returned ACCEPT. Fresh checkpoint context then advanced work to the UI.
- Independent browser checks of the unchanged candidate passed mood selection,
  accessible pressed state, note entry, saving mood/note/readable timestamp,
  newest-five history ordering, clear history, keyboard selection and no-note
  save. No browser console errors were observed.
- Private decision notes, one reviewer explanation, token/timing telemetry,
  host receipts and a hash-checked HTML timeline were retained. This provided
  useful evidence of repeated tool mistakes and stale model descriptions.
- Workspace/lease cleanup completed. The provider independently returned no
  pods. Local services and preview stopped; persistent model storage and the
  independent janitor were retained.

## What did not work

| Attempt | Result | Checkpoints | Observed failure |
| --- | --- | --- | --- |
| Initial staged task | ITERATION_LIMIT, 32 implementation calls | 0/3 | Tests used nonexistent APIs; repeated invalid patch/create/replace actions; no UI |
| Guided continuation from Qwen's unchanged files | TOKEN_BUDGET, 30 implementation calls plus one reviewer call | 1/3 | UI test imported unavailable `jsdom`; repeated edits consumed the shared budget; persistence not reached |

The guided trial consumed 183,614 input and 22,167 output tokens. The host
stopped further execution after the request crossed the 200,000-token threshold;
this is a post-request stop, not an exact provider token reservation. It ran for
about 973 task seconds, including capacity and startup waits. Both attempts
fit the original 45-minute outer window. Estimated provider compute was about
$1.03 for the two live attempts, excluding storage and not an invoice. An earlier
B200 startup-only failure cost approximately $0.52 separately; its launcher
repair was merged, but B200 inference was not qualified by these RTX runs.

Independent isolated tests reproduced one passing logic test file and one
failing UI test file (`ERR_MODULE_NOT_FOUND`). Browser reload erased history.
The reviewer accepted only logic; neither generated tests nor that verdict
establish full app acceptance. Explanations sometimes identified the right
repair before an invalid action, or referred to stale file/test state. They are
untrusted model-written summaries, not hidden reasoning or proof of correctness.
Thinking remained disabled.

## Lessons and next acceptance boundary

Explicit API and read-before-replace guidance improved progress, but prompting
alone did not eliminate duplicate creates or imagined dependencies. Retain a
small disclosed file history, distinguish prior test results from current
validation, and give actionable dependency recovery guidance. Preserve the
working candidate and focus the next task on UI-test repair plus persistence;
do not repeat the counter or restart MoodLog from an empty directory.

The [continuation runbook](../../development/WORK-MODE-MOODLOG-ACCEPTANCE.md)
defines the protected persistence oracle, remaining browser checks and the
bounded follow-up. Its source changes and synthetic tests are preparation;
full live acceptance remains unqualified until that procedure passes.

Raw source, prompts, screenshots, task IDs, traces, receipts and provider
references stay in the external private prefix. This document is the sanitized
milestone record, not an export of that live evidence. Preserve the exact
candidate hashes and failed results when recording later success.
