# Qwen Code isolated MoodLog proof of concept — 2026-09-28

Status: **failed isolated proof of concept; no Sanctum Work Mode integration or
autonomous MoodLog acceptance**. This was one owner-approved paid window, with
no task retry. It does not qualify PR #150's merged context-retention change:
that change still has no live retry through the existing Work Mode loop.

## Two separate paths

1. **Model:** Qwen Code 0.24.6 used the existing private
   Qwen3.5-122B-A10B-NVFP4 vLLM server's OpenAI-compatible
   `/v1/chat/completions` API. A Mac-held lifecycle lease started the cached,
   private GPU model and established its loopback SSH tunnel. A bounded Mac
   broker forwarded only model and model-list requests from the container over
   stdio to that tunnel. The Sanctum gateway did not expose a Qwen Code model
   API; its existing PRIVATE_LEAD adapter remains proposal-only.
2. **Coding tools:** the headless Qwen Code process and its read, edit, write
   and shell tools ran as a non-root user in one `--network none` Docker
   container with a read-only root, dropped capabilities, resource limits and a
   copied MoodLog workspace. It received no host home, credentials, Docker
   socket or live candidate mount. Only the Mac broker could reach vLLM. Direct
   writes affected the disposable snapshot; the Mac copied it out for review
   and ran tests in Sanctum's pinned networkless runner. Qwen Code approval
   settings and prompt text were not the isolation boundary.

This second path is **not Sanctum Work Mode**. Qwen Code's built-in tools did
not invoke Sanctum's per-operation authorization, semantic capabilities,
bounded exact edits, result-egress decisions, evaluator, reviewer or Human
Review transition. The snapshot was never imported into an authorized Work
Mode workspace.

## Input and independent limits

The untouched private candidate started clean at commit
`b3b0ce7371639a5fd1829f60b53b23cb0a9e9870`. Sanctum's isolated runner
observed 8 of 11 ordinary tests passing, with three intended missing-UI-
persistence failures. Its separately protected storage oracle passed all four
named tests. Original file hashes and the exact private prompt, container
image, broker, Qwen event stream, requests, responses and final snapshot are
retained outside Git under the private prefix's
`state/qwen-code-poc-20260928/live-20260928-152234` evidence directory.

The Qwen CLI used `--prompt` and `--output-format stream-json`, not `qwen
serve`. Its own limits were 48 session turns, 40 tool calls and 20 minutes.
The Mac broker independently allowed at most 32 model requests and 900 seconds
of inference. The allocation had one outer 45-minute window, no automatic
task retry and a $50 total ceiling. Read-only provider preflight found one
available GPU at $2.09/hour, no pre-existing pod or lease, disabled autostart
and the independent janitor loaded. The broker fixed each request to a 4,096
token maximum and the reviewed non-thinking sampling values. The private
model cache and persistent volume were reused.

## Newly observed result

Qwen made 19 successful model requests and began a twentieth. Its trace shows
25 coding tool calls: 11 reads, 10 edits, one write and three shell commands.
It changed `storage.js`, `index.html`, `index.js` and `README.md` without a
human editing application files. The commands included `node --check index.js`
and `node --test`; this clearly progressed beyond the prior ten-read,
zero-edit unassisted stall. It did not produce a final Qwen result.

The twentieth vLLM request returned HTTP 400. The experimental broker treated
that response as a fatal transport exception instead of preserving the response
body and relaying the error to Qwen. The last successful response reported
28,672 prompt tokens; the next request included more history and a 4,096-token
output reserve against a 32,768-token model context. A context-window mismatch
is the leading inference, **not a proven server error reason**, because the
broker did not retain the 400 body. This proof was run with Qwen Code's `--bare`
mode and no model-specific `contextWindowSize` setting. There was no automatic
retry or second allocation.

The final snapshot passed lint and build, but only 9 of 11 ordinary tests and
3 of 4 protected tests. Actual-script UI tests confirmed save/reload and
newest-five persistence in their controlled browser double. The protected
oracle found that unavailable storage incorrectly reported success, and the UI
test found that denied storage followed by clear lacked an honest persistence
warning. Browser-page reload was not separately checked after these failures.
The task did not reach a Sanctum `COMPLETE`, protected pass or reviewer
`ACCEPT`; no Human Review handoff occurred. The failure is a combination of
unfinished task behavior and the proof broker's HTTP/context handling. It is
not evidence that Qwen Code solved autonomous MoodLog.

After the run, the operator found that the proof broker had marked its lease
closing without decrementing the active count, so the first cleanup check
still showed one pod. The operator closed that active lease through the
existing lifecycle, requested immediate manual cleanup and independently
confirmed `OFFLINE`, zero leases and active requests, no provider pod, no Qwen
container and no local model tunnel. The persistent volume was retained.
Allocation to confirmed absence lasted about 522 seconds, or approximately
$0.30 at the observed hourly price, excluding retained storage and provider
adjustments. The private reproduction script was corrected after preserving
its exact executed version. A no-cost mock verified the container and model
transport again; the GPU cleanup correction was not live retested. No second
paid run was made.

## Integration gap and next qualification

A Work Mode implementation needs a reviewed way to hand Qwen's proposed file
changes to Mac authority before they affect an authorized candidate. One
option is a container snapshot-import capability that validates path/type,
scope, immutable protected inputs, exact diff and workspace generation before
applying changes. Another is a tool bridge to the existing semantic
capabilities. Either route must retain host-owned task budgets, result egress,
fixed runner commands, protected execution, evaluator/reviewer decisions,
receipts, cleanup and Human Review. A prompt, permission denylist or direct
model connection cannot supply these controls. The model-specific context
window, compaction threshold and HTTP error capture also need contract tests
before another funded run. Pinning the Qwen image and broker through the
stopped-gateway amendment and doctor is still unimplemented.

For a no-cost transport preflight, the private operator script supports
`python3 state/qwen-code-poc-20260928/run_poc.py --mock` from the external
private prefix. The recorded live invocation omitted `--mock` and used the
same preserved candidate and protected checks. Its exact executed assets and
hashes are in the private evidence directory. A future live invocation needs
a separately reviewed model-context fix, source/runtime integration and a
new owner-approved funding window; it is not an automatic retry of this task.

Official Qwen Code references reviewed for this proof:
[headless budgets and output](https://qwenlm.github.io/qwen-code-docs/en/users/features/headless/),
[model-provider configuration](https://qwenlm.github.io/qwen-code-docs/en/users/configuration/model-providers/),
and [sandbox boundaries](https://qwenlm.github.io/qwen-code-docs/en/users/features/sandbox/).
