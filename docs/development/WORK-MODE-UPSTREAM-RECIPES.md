# Work Mode: adopting upstream Qwen recipes

Status: source implementation with synthetic coverage; live coding qualification
pending. This is a new Work Mode generation preset, not an extension of the
historical accepted interface characterization scores.

## Sources and compatibility

Reviewed on 2026-09-28:

- [Qwen3.5-122B-A10B model card](https://huggingface.co/Qwen/Qwen3.5-122B-A10B#best-practices):
  published sampling recommendations distinguish thinking from non-thinking mode.
- [Qwen Code software-engineering guidance](https://github.com/QwenLM/qwen-code/blob/a765229c0affd0642973412a3480b992935e2eff/packages/core/src/core/prompts.ts):
  inspect relevant code and dependencies, choose concise goals, implement focused
  changes, diagnose failures, and verify outcomes. The wording here is original;
  these workflow ideas are adapted to Sanctum's existing tools and authority.
- [Entrpi's 122B deployment](https://github.com/Entrpi/qwen3.5-122B-A10B-on-spark/tree/a77cbdab26956ef6ac9cdca544e5fb9ec1f3bb2a):
  a useful native tool/reasoning parser and serving reference. Its Spark-specific
  performance patches and native tool interface are not copied into this change.

These projects demonstrate useful patterns, not one identical tested configuration.
Their successes do not qualify our NVFP4 model, strict Work Intent schema or runner.
Keep upstream reports, synthetic host tests and newly observed live results distinct.

## Immediate changes

`QWEN35_INSTRUCT_V1` applies the model card's non-thinking general-task preset to
ordinary Work Mode implementer and reviewer proposals:

| Setting | Value |
| --- | --- |
| temperature | 0.7 |
| top_p | 0.8 |
| top_k | 20 |
| min_p | 0.0 |
| presence_penalty | 1.5 |
| repetition_penalty | 1.0 |
| enable_thinking | false |
| max_tokens | 4096 |

The preset is fixed in the host backend. Repository text, observations, model
proposals and nested request data cannot override it. Explicit sampling values
avoid depending on serving defaults. The published temperature-0.6 precise-coding
preset accompanies thinking mode; this change does not claim to reproduce that
profile. Presence penalty may affect code quality, so retain failure examples and
compare useful edits and tests rather than assuming fewer repeated tokens is better.

The implementer prompt adapts Qwen Code's workflow to choose a concrete next edit
and validation step, check dependency availability before use, follow observed
conventions and diagnose an error before attempting a focused repair. Its existing
optional decision note can summarize the next step. This adds no planning call,
model-authored persistent plan, new tool, shell access or command-selection power.
The existing small-edit contract, host progress state and stage decomposition remain.

Telemetry now records the fixed `generationProfile` label on backend success and
failure. Unknown or absent labels become `UNKNOWN`; arbitrary provider labels do
not cross the worker/caller boundary. Failed-call usage accounting stays in place.
The owner-authorized diagnostic microprobe retains temperature zero, its original
implicit sampling defaults and 1,024-token reservation, labeled `LEGACY_GREEDY_V1`.
Readiness smoke checks and ordinary Assistant Mode are unchanged.

## Bounded live run after owner merge

1. Apply the reviewed source via the stopped-gateway Work Mode upgrade, run doctor
   and schema preflight, and verify autostart remains disabled with the independent
   janitor available. Verify provider absence and no outstanding ownership first.
2. Reuse the exact unchanged nine-file Qwen storage milestone and the registered
   three-stage `moodprogress` profile. Preserve original/protected tests and file
   hashes; provide no operator-written application fix.
3. Use one cached allocation, no automatic second allocation or task retry. Keep
   the existing 45-minute outer window and $6 compute ceiling, including cleanup
   reserve, within the owner's broader spending authorization. Price/capacity and
   private bindings must pass current read-only preflight before allocation.
4. Retain the shared task limits: 32 model calls, 200,000 reported tokens, 1,200
   task seconds, 900 inference seconds and $1.50 inference estimate, with reviewer
   required. These do not replace the independent allocation deadline or janitor.
5. Capture the source revision, profile label, reported/missing usage, valid and
   invalid proposals, useful edits, tests, checkpoint completion and reviewer
   disposition. This is a combined preset/workflow candidate, not a controlled
   attribution of any improvement to temperature alone. Repeatability remains
   unqualified after one stochastic run.
6. Only attempt browser acceptance after host completion and reviewer acceptance.
   End the task, explicitly release the owner hold/allocation, confirm provider
   absence plus zero leases/requests, and stop local services. Preserve model
   cache, candidate and private evidence even on failure.

See the [MoodLog acceptance checklist](WORK-MODE-MOODLOG-ACCEPTANCE.md) and
[previous output-limit failure](../history/v1.3/WORK-MODE-OUTPUT-LIMIT-RETRY.md).

## Separate follow-ups

Thinking needs a compatible reasoner/structured-output configuration and a reviewed
output/context reservation. Native tool calling needs an adapter into the existing
Mac validation path. Neither is a one-parameter substitute for the present protocol.
Larger output limits, alternative quants, server upgrades, speculative decoding and
persistent model plans remain separate experiments, not prerequisites for this run.
Runtime/dependency pins and the historical interface profile are unchanged. Freeze
only the intentional source, tests and documentation in this change.
