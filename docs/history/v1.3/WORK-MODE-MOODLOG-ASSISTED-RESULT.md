# Assisted MoodLog result and JSDOM-free continuation

The MoodLog proof of concept works in the preserved **assisted** private copy. This
is evidence that the small app can meet its behavioral checklist with human
intervention. It is not a Work Mode `COMPLETE` result, a reviewer `ACCEPT`, or
evidence that Qwen independently recovered from the final errors. The earlier
failed runs remain failed. The private candidate, raw model responses, traces,
receipts, browser fixture and screenshots stay in the external owner runtime.

## Who did what

Qwen wrote the original in-memory MoodLog UI and the storage helper from earlier
runs. In the latest bounded direct comparison, Qwen produced the first persistence
integration in `index.html` and `index.js`: storage script loading, startup load,
save and clear wiring. The direct route returned code as data and had no file-edit
authority. Both its first result and one correction attempt left duplicate
top-level `ALLOWED_MOODS` declarations across classic scripts; isolated execution
stopped with `SyntaxError: Identifier 'ALLOWED_MOODS' has already been declared`.

The operator did the following assistance:

1. Replaced the candidate's `jsdom`-dependent `ui.test.js` with the
   [Node-only qualification fixture](../../../gate/qualification/moodlog/ui.test.js).
   Its small DOM double loads the actual scripts listed in `index.html` in order
   and triggers their real event handlers. No package, isolated-runner image or
   dependency pin changed. A deliberate mutation of the app's save behavior made
   these tests fail, confirming that they exercise the app rather than a copied
   implementation.
2. Repaired Qwen's reproduced script collision by giving three storage constants
   (`ALLOWED_MOODS`, `MAX_NOTE_LENGTH`, `MAX_HISTORY_SIZE`) storage-specific names
   and updating their references. This was a human code correction, not a model
   recovery.
3. Corrected the visible storage-failure wording so it warns that changes may
   revert after refresh; added status/live-region semantics to that warning.
4. Added integration cases for reload, persisted clear, newest-five order,
   malformed storage, denied access and failed writes/clears; wrote the private
   app README; ran isolated tests, lint, build and browser checks. The controlled
   browser error fixtures were test-server inputs, not changes to the saved app.

The assisted copy passed 11 isolated tests with no skips, lint and build. In a
real browser it passed mood selection, keyboard activation, note limit, text-safe
history, newest-five order, exact reload persistence, post-reload save and
persisted clear. Denied, malformed and failing storage cases left the in-memory
controls usable and displayed a warning. These checks establish the assisted
copy's behavior at the preserved revision; they do not establish unattended
coding ability.

## What the Work Mode comparison showed

The bounded Work Mode comparison made four model calls: three reads and one test.
Its candidate and protected tests passed, and the JSDOM error did not recur.
It then stopped `BLOCKED / FINAL_WITHOUT_PASSING_EVIDENCE`, with no file diff and
zero completed checkpoints. The operator had left the obsolete `test-repair`
checkpoint in the profile after supplying a working UI test. The evaluator
correctly required a nonempty change for that checkpoint. Qwen did not reach
persistence wiring in this comparison; the stop is a profile setup error, not
evidence of a persistence edit or reviewer decision.

While the gateway was stopped, the operator used the supported configuration
path to register a private two-checkpoint profile: persistence wiring followed by
documentation. Doctor passed. The seeded candidate has the Node-only tests and
protected storage oracle; its remaining integration failures concern missing UI
persistence, not JSDOM. No second paid Work Mode task ran after this correction.
The bounded allocation was released, zero active leases/requests and no provider
pod were confirmed, and the persistent volume was retained.

## Reusable source inputs and remaining acceptance

The source now includes the [UI fixture](../../../gate/qualification/moodlog/ui.test.js),
[post-UI stages](../../../gate/qualification/moodlog/post-ui-stages.json),
[task prompt](../../../gate/qualification/moodlog/post-ui-task.txt) and
[runbook](../../development/WORK-MODE-MOODLOG-ACCEPTANCE.md). These are sanitized
qualification inputs; the working app and live evidence are not copied into the
repository. The source manifest is explicitly refrozen for these reviewed
inputs and documentation; dependency and runtime pins are unchanged. The
existing three-stage plan remains historical input for a candidate that still
lacks repaired UI tests.

Full autonomous acceptance still requires a new bounded Work Mode task from the
fixed baseline, host `COMPLETE`, protected checks and reviewer `ACCEPT`, followed
by browser verification of that exact final model-produced candidate. The
assisted copy is a useful behavioral reference, not a substitute for that run.
