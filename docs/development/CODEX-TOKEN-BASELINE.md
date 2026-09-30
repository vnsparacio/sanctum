# Codex development token baseline

This report measures development-of-Sanctum efficiency. It does not instrument the Sanctum product runtime, influence execution or merge authority, or equate public API cost estimates with an owner's Codex subscription allowance.

## Local collection boundary

Splunk Token Meter was reviewed at commit `f6afa157682cdb16b71c14583b50aead337d50b2` and installed in the owner's development environment. On 2026-09-20 its loopback health endpoint reported ready state, Codex inventory, no runtime-adapter failures, and 111 discovered Codex sources. Automatic update checks and installation were disabled so the baseline stays on the reviewed revision.

Token Meter reads existing local Codex session records. The repository helper [codex_token_baseline.py](../../scripts/codex_token_baseline.py) accepts only a bare loopback HTTP origin and only attributes sessions whose resolved project path is an immediate, Linear-shaped child of the supplied Symphony workspace root. Its output excludes session identifiers, project paths, prompts, responses, raw traces, credentials, source text, and API-equivalent cost estimates.

Run a content-free sample locally:

```sh
python3 scripts/codex_token_baseline.py \
  --workspace-root /absolute/path/to/symphony-workspaces \
  --issue TTE-9 --issue TTE-14 --issue TTE-45
```

JSON is the default. Add `--format markdown` for a compact table. Keep raw Token Meter responses and any richer trace inspection local; commit only reviewed aggregates.

## Initial sample

The baseline was captured on 2026-09-20 before any workflow optimization. It covers three ordinary Linear to Symphony to Codex implementation issues. Linear records all three as Done with an attached GitHub pull request. Outcome attribution used only the issue identifier, Linear state, and PR attachment; it did not export session content.

| Issue | Sessions | Restarts | Total tokens | Input tokens | Cached input | Cache share | Output tokens | Reasoning | Turns | Tool calls | Tool output estimate | Peak context | Recorded duration | Outcome |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| TTE-9 | 31 | 30 | 36,412,932 | 36,197,665 | 34,559,104 | 95.47% | 215,267 | 31,166 | 850 | 638 | 670,804 | 88,203 (34.13%) | 6,646 s | Done; PR attached |
| TTE-14 | 6 | 5 | 8,178,573 | 8,136,966 | 7,695,872 | 94.58% | 41,607 | 11,676 | 147 | 140 | 283,963 | 116,500 (45.09%) | 1,237 s | Done; PR attached |
| TTE-45 | 3 | 2 | 11,716,285 | 11,669,367 | 11,331,584 | 97.11% | 46,918 | 15,937 | 150 | 135 | 194,847 | 165,956 (64.22%) | 1,683 s | Done; PR attached |

`Recorded duration` is the sum of session activity spans, not end-to-end issue lead time. `Tool output estimate` and peak context are Token Meter-derived fields. One TTE-45 session was trace-truncated. The local records expose final per-session context, not a complete intra-session growth series. The collector deliberately reports context growth, unused tool/context overhead, workflow retry count, repeated failed approaches, completion/rework outcome, and PR/CI outcome as unavailable rather than inferring them from content.

Across the sample, 53,586,560 of 56,003,998 input tokens were cache reads (95.68% when aggregated). The runs still processed 56,307,790 total tokens over 1,147 turns and 913 tool calls. High cache reuse lowers the relative cost of repeated stable context, but it does not make repeated processing free and does not represent subscription billing.

## Major contributors

1. **Issue/session breadth.** TTE-9 accounts for 63.1% of sampled tokens and has 31 sessions, 850 turns, and 638 tool calls. Its 30 session restarts are the clearest high-impact correlate in this small sample. This is correlation, not proof that restarts caused the total.
2. **Large repeated input.** Input exceeds output by 168x to 249x per issue. Cache share is excellent, but each run still carries substantial context; uncached input totals 2,417,438 tokens across the sample.
3. **Long-context continuation.** TTE-45 reached 165,956 context tokens (64.22% of the reported window) despite only three sessions. That makes checkpoint/restart behavior a higher-priority experiment than issue decomposition for this shape of run.
4. **Tool-result volume.** The sample includes 913 calls and an estimated 1,149,614 tool-output tokens. TTE-14's tool output is about 6.8 times its model output, which makes result shaping and unused tool/context exposure measurable secondary candidates.

No tool errors were reported in this sample. That means error-count reduction is not supported as an initial optimization target. Token Meter does not presently provide enough content-free evidence to rank repeated failed approaches or distinguish necessary from unused exposed tools.

## Ranked follow-up experiments

These are proposals for separate Linear issues, not changes authorized by this measurement ticket. Each experiment must retain the Linear/Symphony/Codex/PR/Human Review authority model, change one variable, and compare several completed issues of similar size against this baseline.

1. **Bound issue and session size (highest expected impact).** Define a ticket-size threshold and an explicit checkpoint contract, then compare tokens, sessions, restarts, turns, duration, and successful PR outcome. TTE-9 provides the strongest signal because it dominates total consumption and restart count.
2. **Checkpoint long-running sessions.** At a predetermined context threshold, start a fresh session from a content-minimized durable checkpoint. Compare like-for-like work on peak context, uncached input, rework, and successful completion. TTE-45 is the reference shape; this experiment must not automatically kill or reroute sessions.
3. **Stabilize prompt/context packaging.** Separate stable policy/instructions from issue-specific volatile context without removing authority or safety text. Measure cache share, uncached input, and total tokens. The current 94.58% to 97.11% per-issue cache shares are the before values, so an intervention must improve uncached consumption or outcome rather than merely report a high hit rate.
4. **Reduce tool-result and exposed-tool overhead.** For one matched issue class, narrow eagerly supplied tool definitions or cap verbose result payloads while keeping required tools available. Compare tool-output tokens, total input, tool errors, turns, and outcome. Do not infer unused tools until the experiment captures both exposure and use counts consistently.
5. **Set bounded retry budgets and evaluate routing.** First add content-free retry/outcome markers, then test one retry limit or standard/deep routing rule at a time. The current dataset cannot support success claims here because retry, failed-approach, rework, and CI signals are unavailable.

## Measurement protocol

For every follow-up, record the issue identifier, collector revision, Token Meter revision, model/routing class, session count, restarts, input/cached/output/reasoning tokens, peak context, turns/executions, tool calls/errors/output estimate, recorded duration, and final Linear/PR/CI outcome. Use a predeclared comparison cohort and do not mix multiple workflow changes into the same intervention. Preserve unavailable values as unavailable.

Collection remains observational and fail-open for engineering availability. Telemetry grants no execution, routing, approval, completion, or merge authority. Follow-up implementation belongs in separately reviewed Linear issues; no optimization is declared successful until its before/after measurements and engineering outcome are recorded.
