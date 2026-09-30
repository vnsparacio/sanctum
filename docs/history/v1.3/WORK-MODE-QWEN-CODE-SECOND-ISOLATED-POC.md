# Qwen Code second isolated MoodLog proof — 2026-09-28

Status: **failed isolated proof; no Sanctum Work Mode integration or autonomous
MoodLog acceptance**. This was one new paid window after the first proof in
`WORK-MODE-QWEN-CODE-ISOLATED-POC.md`, with no automatic task retry. PR #150's
context-retention change still has no live retry through the existing Work Mode
agent loop.

## Boundary and input

Qwen Code 0.24.6 ran its headless coding loop in a non-root, networkless OCI
container with a read-only root, dropped capabilities, resource limits, and a
copied MoodLog snapshot. It had no host mount, home, credentials, Docker socket,
or external network. A Mac stdio broker allowed only model requests to the
existing private 122B vLLM server through the Mac-owned loopback SSH tunnel.
The Sanctum gateway did not expose an OpenAI-compatible endpoint. Qwen's
permission mode was not treated as an authority boundary.

The Mac retained GPU allocation, lease and janitor control, a 40-minute outer
deadline, a 32-model-request cap, 900 seconds of cumulative inference, a
one-window 45-minute and $50 ceiling, and independent protected testing in the
pinned networkless Work Mode runner. Qwen itself had 48 session turns, 40 tool
calls, and a 20-minute headless wall limit. The baseline was the clean nine-file
MoodLog candidate at `b3b0ce7371639a5fd1829f60b53b23cb0a9e9870`: 8/11
ordinary tests and 4/4 protected tests. The exact task and protected acceptance
were reused. No human edited candidate files during the run.

The private provider entry gave Qwen the server's 32,768-token context window,
a 4,096-token output cap, and a 0.60 auto-compaction threshold. Unlike the
first proof, Qwen did not run in `--bare` mode. The broker retained upstream HTTP
error bodies. A no-cost mock confirmed Qwen read the isolated provider config
and completed through the broker before the paid run.

## Observed run and failure

The server returned HTTP 200 on all four Qwen model requests. Qwen read seven
**distinct** files in two batches: `logic.js`, `storage.js`, `index.js`,
`logic.test.js`, `persistence.test.cjs`, `ui.test.js`, and `README.md`. The third
model request had no tools and the shape of a context-summary call; its prompt
token count fell to 11,066 from 15,784 on the previous call. The fourth was
20,578 prompt tokens. This supports that Qwen's context handling was active;
it does not prove task completion or validate the earlier Work Mode context fix.

The experimental setup had explicitly set `model.skipLoopDetection` to `false`.
After those seven successful, non-repeated reads, Qwen exited with code 1 and
`action_stagnation`, saying its streaming loop detector halted repeated tool
use. This is a premature detector stop in this trace: the paths were distinct,
none of the reads failed, and no repeated read or stalled edit is recorded.
The precise detector heuristic is not established by the trace. Qwen made no
edit, write, or shell call and produced no successful final result. The candidate
snapshot remained byte-for-byte at baseline; its ordinary tests still failed
3/11 and the separate protected oracle still passed 4/4. App reload was not
tested because the coding task did not advance.

This failure is attributable to the Qwen Code loop-detection setting in the
isolated test environment, with no observed model HTTP or tool compatibility
error. Official Qwen Code settings documentation says loop detection defaults
to skipped because it can interrupt legitimate workflows. The private setup
now uses that documented default (`model.skipLoopDetection: true`), while the
CLI tool/turn/wall caps and all independent Mac limits remain. A subsequent
no-cost transport mock passed. **This correction has not had a paid MoodLog
retry**, and it is not evidence that Qwen can complete MoodLog unassisted.

## Evidence, cleanup, and integration gap

The raw prompt, exact executed broker/config/script copies and hashes, original
model requests, broker replies, Qwen stream, starting file hashes, ordinary and
protected test outputs, final snapshot, and cleanup result are private under
`$SANCTUM_PRIVATE_PREFIX/state/qwen-code-poc-20260929/live-20260928-193629`.
The executed config there retains `skipLoopDetection: false`; the later private
working config contains the unqualified correction. Nothing raw was added to
Git. The allocation lasted 385.9 seconds from provider start to confirmed pod
absence, approximately $0.224 at the observed $2.09/hour rate, excluding
retained storage and provider adjustments. The container was removed; the GPU
finished `OFFLINE` with zero active requests, zero leases, and zero provider
pods. The persistent model volume was retained.

This still is **not Sanctum Work Mode**. Qwen's tools changed only a disposable
container snapshot, and no snapshot was imported into an authorized Work Mode
workspace. A production integration must validate and authorize each proposed
snapshot diff before import, or route tools through Mac semantic capabilities;
then Sanctum must own scope, budgets, protected tests, evaluator, reviewer,
receipts, and Human Review. No such path was added or deployed on this failed
proof. A direct model connection, Qwen permission setting, or prompt cannot
provide those controls.

For no-cost transport reproduction, run the private
`state/qwen-code-poc-20260929/run_poc.py --mock` with the preserved candidate.
The exact live invocation omitted `--mock`; its executed assets are frozen in
the evidence directory. A new live attempt requires an explicitly approved
paid window and must be assessed from a fresh clean baseline with the same
protected checks. There is no automatic retry.

Official Qwen Code references:
[headless limits](https://qwenlm.github.io/qwen-code-docs/en/users/features/headless/),
[provider model configuration](https://qwenlm.github.io/qwen-code-docs/en/users/configuration/model-providers/),
and [context and loop settings](https://qwenlm.github.io/qwen-code-docs/en/users/configuration/settings/).
