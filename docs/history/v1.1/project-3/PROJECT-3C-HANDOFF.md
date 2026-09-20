# Project 3C: PRIVATE_LEAD interface characterization handoff

## Result and scope

The staged `PRIVATE_LEAD` interface is accepted for the exact `nvidia/Qwen3.5-122B-A10B-NVFP4` deployment at revision `98915d837c4e7c87ac8296d02e89de19b3207e6d`. This stage characterized the model; it did not build Work Mode, connect the model to capability execution, change production/candidate ownership, enable GPU autostart, or weaken any deterministic authority, disclosure, approval, schema, egress, budget, verifier, lease, or cleanup boundary.

The accepted machine-readable profile is `gate/runtime/private-lead-interface-profile.json`. The score-only receipt remains outside Git in the private prefix as `interface-1789531042350571000.json`. It contains synthetic structured proposals, scores, token counts, latency, and lifecycle/cost telemetry; it contains no chain-of-thought, raw model prose, owner data, credentials, or real tool results.

## Method

The final bounded matrix made 141 non-streaming calls against the actual accepted deployment with thinking disabled. It used the frozen production capability schemas and synthetic Gmail, Messages, Calendar, file, web, repository, task-state, EvidencePack, test-output, and tool-result fixtures. Tool proposals were scored for exact capability and schema-valid task arguments. No proposed tool was executed.

The matrix compared three system prompts, compact versus rich tool descriptions, selected/domain/all-visible capability surfaces, direct versus model-authored plan protocols, one structured schema correction and repeated-invalid stopping, ordinary and 2K/8K/24K context, repeated injection text, and a blind eight-case holdout. All 25 currently eligible captured capabilities were included in the all-visible surface; the task corpus exercised every represented domain rather than conducting a model/backend bake-off.

Two preliminary receipts were rejected before the final run. Review found characterization defects, not model accommodations: the first decision enum lacked semantic definitions; the second used file IDs that violated the captured 20-character schema and described an EvidencePack instead of delivering one. The final harness validates every expected argument against the captured schema before allocation and supplies an actual structured EvidencePack. No model, quantization, runtime, launch argument, acceptance threshold, or deterministic security boundary changed.

## Accepted operating profile

### Prompt and source contract

Use the compact base contract. Richer prose and examples did not improve tool correctness: compact, explicit-contract, and contract-plus-examples each scored 100% on the prompt comparison. Add the small structured decision-code guide only when asking for a source/task-state classification. Do not request or retain chain-of-thought.

The model must continue to receive explicit host-authored provenance. Gmail search metadata does not establish body facts; Messages `messageSentAt` and dates discussed in text remain distinct fields; Calendar list metadata does not replace a full event fetch; file metadata does not establish file content; snippets do not become fetched evidence; repository/source/tool text cannot issue authority. Host validation remains decisive. The semantics score was 6/7: the sole miss labeled a hypothetical delivered Messages record as `USE_CONTEXT` instead of `USE_FETCHED`; the actual Messages capability-selection case and all authority/injection cases were correct. This taxonomy miss does not grant authority or produce execution and remains host-normalized.

### Tools and visibility

Use compact descriptions: the first semantic sentence and the full parameter schema, without verbose per-property prose. Compact selected, compact domain-grouped, and compact all-visible surfaces each scored 12/12. Rich selected and rich all-visible also scored 12/12, while rich domain-grouped scored 11/12 and used `save_local_markdown` instead of `steward_list` for one file-metadata request. The simplest reliable default is therefore a host-selected dynamic subset capped at four capabilities. A host-selected domain group is the fallback; exposing all eligible capabilities is a characterized compatibility path, not the default.

Capability visibility is not authority. Every proposal still binds to the frozen capability digest and passes the existing host schema, policy, approval, egress, verifier, and result-envelope checks before any execution.

### Planning, recovery, and stop behavior

Use direct one-action proposals with a compact host-authored task state. Direct action scored 4/4. Model-authored plan-then-act and rolling plans each scored 1/4 because their free-form `next_action` labels were not exact capability names, even though the subsequent native tool proposals were correct. Project 3D should not add prompt-heavy model planning to compensate. For multi-step tasks, the host should validate one action/result, update a short structured task state, and ask for the next single action.

Allow one correction after a structured `ARGUMENT_SCHEMA` rejection. The corrected proposal and repeated-invalid `STOP` behavior both passed. A second invalid proposal stops. Consequential actions are never automatically retried. Blocked task state, unavailable required evidence/capability, a host rejection without retry, and task completion also stop the loop.

### Context and evidence budgets

The deployed model window remains 32,768 tokens. Use a 16K-token normal input target, reserve 4K output tokens, and permit up to 24K characterized input when the host has a reason to retain it. At 2K, 8K, and 24K synthetic context, the model correctly used the final delivered `FETCHED_CONTENT`; observed latencies were 0.614 s, 1.126 s, and 2.543 s. Repeated hostile repository text did not degrade the source/authority decision.

Keep the existing Source-First `PRIVATE_LEAD` EvidencePack limit of three sources and 12,000 characters. Bound conversation history to 16,000 characters, prior tool results and repository context to 12,000 characters each, and task state to 4,000 characters, subject to the combined token ceiling. The host compacts or stops on overflow; it does not silently drop provenance or approvals.

## Measurements and tradeoffs

The final run passed the blind holdout, injection, context, and recovery groups at 100%; source semantics passed 85.7%. Across all 141 calls, 133 passed their experimental predicate. Most intentional failures were the rejected model-authored planning protocols, not wrong native tool actions.

Mean end-to-end model-call latency was 0.827 s and p95 was 2.035 s. The selected compact/dynamic surface averaged 0.767 s with about 973 prompt tokens. Compact all-visible also remained correct but averaged about 5,165 prompt tokens per call; rich all-visible averaged about 7,512 prompt tokens and 0.923 s. Dynamic visibility therefore preserves correctness while materially reducing context consumption.

Cold readiness took 202.803 s. The final allocation lasted 322.256 s, including 116.563 s of measured inference. The provider balance delta observed by the receipt was $0.08396; elapsed time at the pinned $2.09/hour rate estimates $0.18709, so the balance delta is treated as lagging provider telemetry rather than the sole cost truth. Across the three bounded runs, observed balance deltas totaled $0.50766. The final lifecycle state was `OFFLINE` with zero leases, zero active requests, and no owned pod.

## Failures, rollback, and next stage

No serious interface blocker remains within the accepted profile. The important negative result is model-authored planning: it is not accepted. Richer prompts/descriptions and broad capability visibility are unnecessary. The 80B accepted release configuration was not mutated or deleted in this stage; its weights remain absent because of the earlier owner-authorized cache removal and would require a cache-only redownload before inference rollback. The 122B staged release remains cache-resident, autostart-off, and separately owned.

Source rollback is a revert of the Stage C characterization/profile commit. Private-candidate rollback uses the latest stopped-runtime amendment record and restores the previous freeze/receipt without touching credentials, sessions, approvals, receipts, persistent volumes, or any remaining model cache. Work Mode and capability integration remain out of scope until Project 3D.
