# Work Mode: off-peak B200 startup failure

Date: 2026-09-27 UTC. Decision record:
[TTE-97](https://linear.app/ttercode/issue/TTE-97/record-moodlog-poc-milestone-and-close-work-mode-acceptance-gaps).
Observed source: merged `ec5da82` after
[PR #129](https://github.com/vnsparacio/sanctum/pull/129).

The bounded off-peak retry obtained one B200 allocation after RTX capacity was
unavailable. The reviewed hardware guard passed, cached model weights loaded,
and compilation progressed. Startup then failed during DeepGEMM warmup, before
readiness or task admission. No MoodLog task, model inference, reviewer call or
application edit occurred. Full acceptance remains unqualified; the earlier
[partial milestone](WORK-MODE-MOODLOG-MILESTONE.md) remains the latest observed
application result.

## Failure and proposed correction

The startup stack runs from `kernel_warmup` through `deep_gemm_warmup` and
`_fp8_linear_may_use_deep_gemm` to an unavailable
`get_mk_alignment_for_contiguous_layout` implementation. The diagnostic says
that the DeepGEMM backend is unavailable or outdated. This establishes the
unavailable API, not the precise packaging defect; no package inventory or
repair was performed after the failure.

In the pinned [vLLM 0.20.1 warmup code](https://github.com/vllm-project/vllm/blob/v0.20.1/vllm/model_executor/warmup/deep_gemm_warmup.py),
the FP8 probe asks for that alignment before checking the layer type. The
[warmup entry point](https://github.com/vllm-project/vllm/blob/v0.20.1/vllm/model_executor/warmup/kernel_warmup.py)
and [backend support check](https://github.com/vllm-project/vllm/blob/v0.20.1/vllm/utils/deep_gemm.py)
honor `VLLM_USE_DEEP_GEMM`. The Sanctum launcher now explicitly exports it as
`0` for both allowed GPUs. NVFP4 quantization, CUTLASS MoE, Triton attention,
FP8 KV cache, model revision and vLLM version remain pinned as before. This
disables the optional backend instead of adding an unreviewed package repair
or merely postponing its warmup until inference.

Synthetic tests execute the actual launcher with stub hardware and server
binaries, checking the server's received environment with absent, disabled and
enabled inherited settings. Rejected hardware must never launch the server.
These are launch-contract tests, not evidence of B200 inference. A new bounded
live run after owner review/merge and supported deployment must still establish
readiness, inference and the entire MoodLog acceptance checklist.

## Boundaries and cleanup

The attempt used one allocation inside a 45-minute, $6 test window under the
owner's $50 ceiling. Allocation-to-confirmed-absence was about 23 minutes;
estimated GPU compute was $2.61 at $6.79/hour, excluding storage and not an
invoice. No second allocation was attempted.

The pod was deleted, provider absence independently confirmed, leases and
active requests returned to zero, and the lifecycle reached OFFLINE. Local
services stopped. The persistent model volume and independent janitor were
retained, autostart stayed off, and the usual RTX binding was restored through
the supported amendment followed by a passing doctor check. Raw logs, resource
references, timing and approval evidence remain in the external private prefix.

The source freeze for this correction covers the launcher, its regression
tests, this report and the continuation runbook. Runtime package pins are
unchanged. Apply only owner-merged source using the stopped-gateway Work Mode
upgrade; never edit installed scripts or refresh hashes to conceal drift.
