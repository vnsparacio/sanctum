# MoodLog context-retention retry — 2026-09-28

The first run after the inspection-prompt fix used merged source
`47f635590db2643fc8b75f5707f8fcb5dfd409c1` and an otherwise unchanged
private `moodretry1` profile. The preserved baseline was byte-for-byte the same
nine-file candidate. One managed RTX PRO 6000 allocation was bounded by a
45-minute owner hold, $6 compute ceiling, and the unchanged task limits.

Task `9ff49a4fd3d7d121cc548623bbc12556` stopped at checkpoint 1 with
`BLOCKED / WORKSPACE_INSPECTION_STALLED` after 11 model calls and 96.58 task
seconds. Qwen read `storage.js`, `logic.js`, `index.html`, `index.js` and
`ui.test.js`, then resumed rereading them. Its decision notes repeatedly named
the correct first constant rename, but it proposed only reads. No edit, test,
evaluator or reviewer ran. The candidate diff was empty and all nine file
hashes matched the baseline. Thus adding `logic.js` to `required_files` repaired
the missing input but did not make Qwen execute.

The five source bodies total 21,148 bytes. The Work Mode reasoner previously
used the ordinary gate's 32 KiB packet limit. A local replay using the same
coordinator request builder and these five source sizes produced a 37,874-byte
packet after the fifth read; fitting it to 32 KiB removed the earlier
`storage.js` and `logic.js` observations. A repeated `storage.js` read then
displaced still more source. This reproduces a plausible context-eviction loop
consistent with the live read order. The live trace records model choices and
tool results, not the full transmitted packet, so this remains a diagnosed
mechanism rather than proof of the model's internal cause.

The source follow-up gives Work Mode alone a fixed 48 KiB packet limit at both
the JS adapter and Mac signer. Ordinary gate chat stays at 32 KiB. Existing
newest-observation retention, byte fitting, egress, authority, task budgets and
completion checks remain in force. Synthetic tests require a representative
five-file packet to retain every observation at the new cap and check that the
Mac signer accepts exactly the cap while rejecting one byte more. Another live
bounded run is required to see whether Qwen edits and completes the UI.

Evidence was copied into the external private prefix before `/work end` removed
the isolated workspace. Managed GPU status finished `OFFLINE` with zero leases
and active requests; independent provider inventory showed no pod. The
persistent volume was retained and local Sanctum services were stopped. The
single allocation cost about $0.31 through confirmed pod absence, excluding
retained storage and provider adjustments. No automatic retry followed.
