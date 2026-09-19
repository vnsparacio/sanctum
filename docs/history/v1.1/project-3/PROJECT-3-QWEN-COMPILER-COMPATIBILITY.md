# Project 3 compiler compatibility diagnosis

Observed 2026-09-17 UTC after the [installed verifier repair](PROJECT-3-QWEN-VERIFIER-INSTALLED.md). This report is outside that completed source freeze. It records the second, separately owner-approved allocation and the subsequent offline diagnosis. It does not declare Project 3 accepted.

## Second approved attempt

The owner approved one bounded retry under the same 900-second, USD 0.75, at-most-USD-2.09/hour, six-total/one-readiness/five-proposal envelope. Experiment `7e35336bd562d5ec8893e71a0635e087` made exactly one allocation attempt. The corrected verifier reached the running environment; cache binding, immutable model snapshot, tokenizer/template identity and stable server identity were verified. The intended Qwen revision and vLLM 0.20.1 were unchanged.

Actual `auto` selection resolved to xgrammar for all six production surfaces. Observed relevant versions were xgrammar 0.2.5.post1, apache-tvm-ffi 0.1.9, torch 2.11.0, transformers 4.57.6, tokenizers 0.22.2, Jinja2 3.1.6, outlines-core 0.2.14 and llguidance 1.3.0. Full distribution/RECORD and compiler-module identities are retained in private evidence.

All six rendered-token totals and remaining headrooms matched the prior local measurements. All six negative compiler controls rejected an invalid representative and invalid schema. The exact compiler gate nevertheless failed:

- Generation grammars compiled, but the ordinary patch branch rejected the escaped newline; the reviewer branch rejected an escaped quote.
- Four semantic schemas did not compile. The post-patch test-only semantic schema compiled and its branches accepted; the reviewer semantic schema compiled but rejected its representative.
- Therefore no readiness smoke, proposal or semantic microprobe was invoked. Reserved/dispatched/completed/uncertain model-call counts were all zero.

Cleanup reached COMPLETE / CONFIRMED with provider absence verified. A fresh inventory/structural check confirmed zero managed allocations, requests, leases or unresolved experiments, PRIVATE_LEAD OFFLINE and PRIVATE_80B RETIRED/zero-owned. Persistent storage was preserved. The full creation-to-confirmed-absence interval was 77.854 seconds; its conservative compute estimate at the quote was USD 0.04520, not a settled invoice.

Receipt SHA-256: `59e77033e3a388f2cf8b788ed2b02a0af44a4c20d94ce38e81b1be9c12b1fc76`. Exact runtime evidence SHA-256: `237633fe792e827718b709b7ea3e2ad5335700223a4a0779d72e82667223fca4`.

**LIVE MICROPROBE FAILED — EVIDENCE PRESERVED — PROJECT 3 REMAINS UNACCEPTED**

## Confirmed local reproduction

An isolated external local environment was created with the observed compiler/library versions constrained to the serving inventory. It does not modify the serving environment, model/profile, repository dependency environment or existing local model runtime. No model weights are loaded and no inference/provider calls are involved. The platform-specific native library bytes differ from Linux, so these checks are local reproductions, not replacement serving identity proof.

The pinned native compiler reproduced the same failures: a lookahead in the authoritative workspace-relative path pattern is unsupported; strings with minLength/maxLength reject JSON escapes for newlines/quotes. Both raw-string matcher checks and token-by-token checks reproduce the escaping failure. An unconstrained string accepts those same escapes. Adding a broad pattern can cause the compiler to ignore length constraints, so such a change was not silently accepted as an equivalent authoritative schema.

## Concrete prototype and required scope decision

An isolated prototype removes minLength/maxLength only from the projected generation schemas and leaves every authoritative semantic schema unchanged. The exact pinned native compiler then accepts all 25 representatives through EOS across all six full generation schemas. No source or installation change was made by this prototype.

The proposed compatibility approach is to keep the GPU generation contract within the compiler's supported language while preserving full length/path/type/enum/authority validation on the Mac. That keeps Qwen/vLLM/profile and host safeguards unchanged. It does change the original preflight requirement that both generation and full host-semantic schemas compile on the GPU; the pinned compiler cannot satisfy the original requirement as written. The owner subsequently explicitly approved this narrow scope change. The repair and installed checks are recorded in PROJECT-3-QWEN-GENERATION-COMPATIBILITY.md and PROJECT-3-QWEN-GENERATION-INSTALLED.md. No additional allocation was authorized by that scope decision.

## Live debugging preference

After this allocation had already been deleted, the owner instructed the agent to fix issues on the fly rather than immediately spinning down. For a future explicitly authorized allocation, non-inference diagnosis/rechecks should use the remaining existing allocation budget before cleanup, with the absolute deadline and cleanup reserve preserved. This does not authorize replacement allocations, extra inference retries, runtime repinning, unreviewed consequential intent repair or source/install identity drift during model dispatch.
