# Project 3 approved microprobe attempt — pre-inference verifier failure

Observed 2026-09-17 UTC. This implements the explicit owner approval following the [installed preflight](PROJECT-3-QWEN-INSTALLED-PREFLIGHT.md). It is not independent acceptance. This evidence report is outside the completed installation freeze; executable source, installation and runtime pins remain unchanged.

**LIVE MICROPROBE FAILED — EVIDENCE PRESERVED — PROJECT 3 REMAINS UNACCEPTED**

The failure occurred in the operator's exact-runtime verification setup before readiness or any proposal. None of the three semantic microprobes ran. This is not an observed Qwen reasoning/schema failure.

## Authorization and identity

The owner explicitly approved one PRIVATE_LEAD allocation, at most 900 seconds, USD 0.75 ceiling at no more than USD 2.09/hour, six total inference reservations (one 16-token readiness and five 1024-token proposals), and the fixed inspection → host-seeded post-patch test → inability sequence. Real coding and qualification were excluded.

The staged authorization, ledger binding and content-minimized receipt are retained under the external private candidate's evidence directory. No independent-review attestation was fabricated; the all-in-one runner was not invoked. The existing installed command-level lifecycle and independent watcher enforced the one-allocation/deadline/accounting/cleanup controls.

| Identity | Value |
| --- | --- |
| Experiment | `b3a3b09d84afebac03dc53873df0c7ae` |
| Source manifest SHA-256 | `8bbd18b1d7000be828a29e06ae977e16507810ae146d41277c554672b13d289b` |
| Installed FREEZE SHA-256 | `01931a75ea41085cdb1a201142a1cbae033a88527676c3679aef0f39bceef4ed` |
| Installed receipt SHA-256 | `1f012dd977fa08e4500af2c7ddfb458cab979eadff115b0e4908cc0ac1b5c4f9` |
| Experiment receipt SHA-256 | `6fc2ee4a7ae63c30dc359b71a2d7927aef55fcca0f2db2b053534a7d011f15f8` |
| Runtime failure evidence SHA-256 | `6f93f0c1db794dbaa486eca1a2d0c3d4ab0d7e55d9d8d4f0d3998da60c2b6964` |

Before allocation, all 283 reviewed source inventory entries matched, doctor passed, the gateway identity/health matched, 80B retirement was confirmed, both releases had zero ownership, and the live provider quote was available at USD 2.09/hour. An independent supervisor heartbeat was observed before the allocation command. The experiment persisted intent and made exactly one allocation attempt; it obtained one allocation. There was no replacement or second allocation.

## Newly observed result

SSH became available and the unchanged cache-only server bootstrap returned success. This establishes launch, not completed model readiness. A separate no-completion process attempted to inspect the serving command, resolve actual structured-output selection and invoke the installed exact-runtime verifier. It returned:

`EXACT_RUNTIME_CHECK_FAILED / LocalEntryNotFoundError`

The controlling caller stopped with `exact_runtime_failed`. It did not call readiness or the signed proposal caller. Ledger evidence records zero reserved, dispatched, known-completed or uncertain-completed inference attempts; readiness remained false. Actual serving compiler/backend/token measurements were not established by this attempt.

The operator launcher has a confirmed configuration omission: the bootstrap exports the pinned `HF_HOME`, but the separate verifier invocation supplied only the offline flags, not that cache binding. The verifier constructed `AsyncEngineArgs` before its explicit tokenizer-path check. The upstream vLLM 0.20.1 implementation performs model-cache resolution during offline `EngineArgs.__post_init__`; this is consistent with the observed exception. The content-minimized exception did not retain a stack trace, so its precise failing frame and the complete state of the server cache were not established.

Static review also identified a later, unreached verifier assertion that compared `engine.model` directly with the original model ID even though offline initialization can replace that ID with a local snapshot path. Both observations concern the temporary operator verifier, not changes to Qwen's profile or installed runtime. No package upgrade, cache download, backend replacement, source amendment or live retry was made to conceal the failure. See the primary [vLLM 0.20.1 argument implementation](https://github.com/vllm-project/vllm/blob/v0.20.1/vllm/engine/arg_utils.py).

## Cleanup and cost

The installed cleanup path requested deletion of the exact managed allocation and confirmed provider absence. The experiment reached `COMPLETE / CONFIRMED`, allocation `ABSENT`, stop reason `PROBE_FAILED`. A fresh provider inventory and structural reconciliation subsequently confirmed:

- zero managed allocations, zero PRIVATE_LEAD leases and active requests;
- zero unresolved experiment or uncertain ownership;
- allocation worker exited; control and inference worker identities cleared;
- independent experiment watcher exited after cleanup; launchd janitor remained loaded, with 3181 runs and last exit code zero;
- PRIVATE_LEAD OFFLINE; PRIVATE_80B RETIRED, zero-owned and still permanently unavailable;
- the configured 150-GB persistent volume remained present in its configured datacenter;
- gateway identity/health, source integrity, runtime pins and configuration integrity still passed doctor.

The ledger was created at 04:14:38.266 UTC and provider absence confirmed at 04:15:15.692 UTC: 37.426 seconds, including pre-allocation work. At the quoted rate, a conservative compute estimate for that entire interval is USD 0.02173, plus less than USD 0.00005 temporary disk. Existing persistent storage continues separately. These are rate-based estimates, not a settled invoice; the approved USD 0.75 ceiling was not approached under the observed lifetime. No provider response bodies or model content are included here.

## Disposition

The single-allocation authorization is consumed. Stop: no second allocation, readiness retry, coding task, qualification suite, source/profile tuning or promotion.

A later attempt first needs an offline-reviewed operator-verifier correction that carries the existing cache environment, verifies the immutable snapshot after offline path resolution, and preserves useful content-minimized stage/error evidence. Existing serving token-return shape checks must still pass; the earlier local tokenizer measurement is not serving-runtime proof. Any new paid attempt requires fresh explicit owner authorization. The unchanged three-probe, real-coding success and eventual independent acceptance gates remain unmet.
