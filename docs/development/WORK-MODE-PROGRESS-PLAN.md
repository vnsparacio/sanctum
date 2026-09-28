# Work Mode progress recovery and next qualification

Status: implemented coordinator contracts; live Qwen qualification pending.
This continues the [storage milestone](../history/v1.3/WORK-MODE-STORAGE-MILESTONE.md)
and [MoodLog acceptance runbook](WORK-MODE-MOODLOG-ACCEPTANCE.md).

## Failure and general repair

The funded B200 attempt made 27 implementation calls: 21 reads, one listing and
four edit attempts executed; the final proposal stopped at the token cap. The
storage helper passed all four protected tests independently, but UI integration
and the missing `jsdom` dependency remained unresolved. Repeated inspection,
including an attempted duplicate creation, consumed the budget. The trace is
consistent with lost working context; it does not establish the model's internal
reasoning or prove that context loss was its only limitation.

The coordinator now carries twelve recent disclosed edit/check summaries and
up to 24 inspected file names. Summaries identify operation, outcome and workspace
generation, without source, command output, model notes or plans. They survive
ordinary result eviction and request-byte fitting, and reset at stage boundaries.
Successful edits and disclosed lint/build/test attempts reset the inspection
cycle; failed edits do not. A successful tool operation is not accepted task
completion. Existing test state, protected tests, fresh source guards and reviewer
remain authoritative.

A newer disclosed successful read replaces the older read body for that path in
the six-result window. Every read still executes and passes result egress and
source-observation mediation; this is prompt compaction, not a tool cache.
Undisclosed, omitted and failed reads cannot supply progress or displace successful
source results. The host compares bounded disclosed source fingerprints privately;
these digests are not added to model prompts.

After two repeated reads of unchanged content at the same workspace generation,
the prompt directs the model to make a concrete edit, validate if ready, or identify
a specific missing dependency. Six repeats since the last disclosed successful
edit or validation attempt stop with `BLOCKED / WORKSPACE_INSPECTION_STALLED`
before another inference. Distinct files and changed content do not increment
this count; new files do not erase accumulated repeats. This protects a bounded
attempt when guidance fails. It does not guarantee a successful model response.
List-only, alternating-content and repeated-test loops still rely on the existing
shared call/token/time/cost limits. No automatic retry or budget extension is added.

## Next steps

1. Review and owner-merge this source change into `v1.3-dev`. Apply the supported
   stopped-gateway upgrade from canonical source, with an explicit source freeze
   for only these intentional changes, then run doctor. Runtime pins are unchanged.
2. Prepare the exact preserved Qwen candidate as a new private baseline. Recheck
   its hashes and isolated test result: storage/logic pass; UI import fails.
   Keep protected acceptance input unchanged and supply no operator-written app fix.
3. Register the merged three-stage continuation profile: repair the UI tests with
   available built-ins; wire persistence and recovery into the actual UI; document
   behavior and validate. Inspect cumulative required files and shared limits.
4. Run one supervised attempt within the acceptance runbook's explicit outer
   deadline and owner spending cap. Keep autostart off, prepare cached model
   readiness before admission, and paste the literal `/work start ... -- ...`
   command so UI smart punctuation cannot change the delimiter.
5. Preserve per-stage results, source hashes, tests, disclosed progress and trace.
   Compare repeated reads and useful edits against the historical attempt, along
   with total prompt/completion tokens. Do not compare cost alone across different
   cold-start durations. Do not call a scripted regression live Qwen qualification.
6. Require host completion and reviewer acceptance, then exercise the exact final
   candidate in a real browser using the full acceptance checklist. Publish a
   sanitized result and update Linear. Confirm pod absence, zero leases/requests
   and stopped local services before ending supervision; retain persistent cache.

## Likely blockers and bounded responses

| Blocker | Next response / acceptance boundary |
| --- | --- |
| UI tests import unavailable packages | Use `node:test`, assertions and a small DOM double exercising the real scripts. Preserve coverage; no installation, skips or fake package shim. If a dependency is essential, stop for a reviewed runner change. |
| Storage helper passes but UI does not persist | Test actual HTML script order and save/load/clear controls, then real reload. Cover classic-script global collisions and actual helper signatures. Unit helper success alone is insufficient. |
| Denied storage, quota, malformed data | Test the `localStorage` getter as well as methods; retain usable in-memory controls and an honest warning. Verify failed writes do not claim persistence. |
| Exact replacement or output limits | Read the target and make small exact replacements within existing limits. Never blind retry stale/missing source, emit partial files or broaden patch authority. |
| Repeated inspection continues | Preserve the candidate and report the new stall reason. Inspect the failed stage and missing evidence before proposing a narrower task; no automatic new allocation. |
| Shared budget ends before all stages | Treat passing stages as partial evidence only. Review decomposition and prompt load; do not silently reset counters or skip reviewer/protected tests. |
| Irreducible request or reviewer context | Stop as context exhaustion. Preserve exact evidence; review a separate evidence-compaction design rather than trimming protected review evidence to force acceptance. |
| B200 capacity, cold startup, credit or disk | Prior readiness took about 22 minutes. Check preflight resources, cache and supervision before allocation; stop/clean up inside the window. No competing model server or automatic second pod. |
| Passing automation but browser defects | Fix through another reviewed Qwen task only after recording the failure. Full acceptance still requires keyboard, reload, clear, storage-recovery and console checks. |

## Offline evidence and limits

Synthetic coordinator regressions cover progress surviving eviction, request-byte
fitting, bounded summaries, duplicate-read compaction, warnings and bounded stop,
changed/distinct reads, mutation/check recovery, withheld/omitted/failed results,
and the edit-test-review completion path. They establish host behavior, not Qwen's
ability to complete the next application stage. This change makes no live inference,
quality, performance or full-acceptance claim.
