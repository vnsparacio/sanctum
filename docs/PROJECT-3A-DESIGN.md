# Project 3A — Private Lead modernization and Work Mode design

## Status, authority, and inspected baseline

Project 3A is inspection and design only. It begins at merge commit `3c84eac`, the current `origin/v1.1-dev` head containing Project 2 PR #3, on branch `v1.1/project-3-private-lead-workmode`. The branch and remote integration head matched after fetch, the working tree was clean before this document was added, stable `main` and tag `v1.0.0` remained at `83a1edf`, and the Project 1 and Project 2 merge commits are `6ae2a93` and `3c84eac` respectively. The configured legacy rollback tree was not modified or repinned.

The accepted Project 1 foundation is present: a runtime-derived shared capability manifest; exact `ToolProposal`, `AuthorityDecision`, `EgressDecision`, normalized result, reasoner, verifier, and audit contracts; native approvals and one-use replay controls; one bounded pre-execution repair; deterministic tri-state verification; and provenance-preserving result normalization. The accepted Project 2 Source-First path is present: deterministic source-need composition and query minimization; one bounded search/fetch coordinator; exact search/fetch egress; `EvidencePack`; reasoner-specific evidence presentation; and host validation of grounded answers and citations.

The external private candidate was inspected without starting it or allocating compute. All 12 Project 2 curated gate files match accepted source byte-for-byte. Its installed web search bound is six, its private receipt and `make doctor PREFIX=/absolute/private/prefix` checks pass, its gateway is stopped, cached GPU state is `OFFLINE` with no Pod identity or allocation uncertainty, the lease table is empty, and the prefix-specific janitor is loaded. This establishes installed source/configuration integrity and local stopped state; it is not a fresh provider-side listing or a new model-performance claim.

The governing invariant remains: **reasoning is replaceable; authority stays on the Mac**. `PRIVATE_LEAD` is a logical role. Qwen3.5-122B-A10B is the first Phase 11 candidate implementation, not a policy identity and not an authority principal.

## Accepted reasoning and evidence baseline

| Logical profile | Accepted implementation | Project 3 treatment |
| --- | --- | --- |
| `LOCAL_4B` | Qwen3-4B-Instruct-2507 through the authenticated loopback OpenClaw agent and existing Mac tool loop | Preserve unchanged as the local tier |
| `PRIVATE_80B` | Qwen3-Next-80B-A3B W4A16 through the signed private worker and managed Runpod lifecycle | Retain as a named rollback release until Private Lead acceptance and rollback proof |
| `PRIVATE_LEAD` | Not executable yet; Project 2 already has a model-neutral evidence profile alias | Add as the new logical role, initially backed only by a separately staged Qwen3.5-122B-A10B release |
| `HOSTED_235B` | Qwen3-235B-A22B-2507 through the pinned hosted reasoning transport | Preserve as a distinct text tier |
| `MULTIMODAL` | Qwen3-VL 30B in current canonical settings, with deterministic attachment preparation and exact disclosure controls | Preserve; do not move visual responsibility to Private Lead |
| `OPENAI_FRONTIER` | Selective strongest external escalation under exact destination-bound disclosure | Preserve as the last-resort capability tier |

The brief refers to Qwen 235B multimodal, while accepted canonical settings currently identify the multimodal implementation as Qwen3-VL 30B. Project 3 must preserve the accepted logical `MULTIMODAL` tier and its controls; it must not silently repin that implementation in order to resolve wording. A multimodal provider/model change would be a separate reviewed amendment.

Project 3 changes the logical ladder to:

```text
LOCAL_4B -> PRIVATE_LEAD -> HOSTED_235B -> MULTIMODAL when visual -> OPENAI_FRONTIER
```

This is an eligibility/routing ladder, not permission for automatic disclosure or a requirement to visit each tier. High-stakes, visual, tool, evidence, exclusion, and exact-destination rules remain Mac decisions.

## Current private-80B runtime architecture

The accepted private path is a reasoning-only OpenAI-compatible backend behind Mac control:

- `gate/plugin/core.mjs` creates a purpose-, scope-, revision-, packet-, capability-, and destination-bound disclosure ticket. A prompt-only session grant is accepted only for `PRIVATE_80B` and only when the packet has exactly `prompt`.
- `gate/plugin/core.mjs` launches a detached, bounded worker request signed with a Mac-held HMAC key. `gate/src/authority.py` checks the signature, expiry, settings digest, strict operation shape, tier, approval kind, state, nonce, credential patterns, and durable nonce uniqueness.
- `gate/worker.py` routes private inference only to `Private80BLifecycle`; remote model output has no tool channel or action authority.
- `gate/src/lifecycle.py` owns the cross-process lock, persistent allocation intent, leases, heartbeats, manual stop, capacity wait, readiness, idle grace, maximum runtime, reconciliation, confirmed deletion, and status/cost estimate. Ambiguous allocation is adopt/reconcile-only and ambiguous deletion stays degraded.
- `gate/src/runpod.py` holds the narrow provider adapter. It verifies a pinned `runpodctl`, retrieves the API credential from Mac Keychain, validates the configured persistent volume and datacenter, requires Secure Cloud and at least 96 GB VRAM, checks price and balance ceilings, creates one GPU Pod, exposes SSH only, and forwards remote loopback port 8000 to Mac loopback.
- The accepted release uses `runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04`, vLLM 0.13.0, `RedHatAI/Qwen3-Next-80B-A3B-Instruct-quantized.w4a16`, alias `vinceai-qwen80b`, 32K maximum model length, and 0.90 GPU-memory utilization.
- The persistent network volume is mounted at `/workspace`; current bootstrap state, vLLM environment, model cache, logs, and PID data live under `/workspace/vinceai`. Compute deletion preserves that volume. No volume mutation API is exposed.
- Current source caps price at $3/hour, runtime at two hours, capacity wait at 30 minutes, readiness at 45 minutes, session idle at 15 minutes, and idle grace at one minute. The external candidate has GPU autostart off.
- The independent prefix-specific janitor executes the same reconciliation/sweep path outside the gateway. It must remain active whenever ownership could be uncertain.

Known limits matter to the modernization. The current lifecycle and Pod name prefix are 80B-specific; bootstrap installs from mutable package indexes; the model release is encoded across settings and shell; readiness proves identity plus a tiny smoke answer rather than performance; network use during bootstrap is not a separate approved phase; and cost is an elapsed-price estimate rather than a benchmark/task ledger. These are design inputs, not reasons to weaken the existing rollback path.

## Staged Private Lead release design

Do not rename or overwrite the accepted 80B release. Introduce a release registry whose entries are immutable, reviewed data and whose selectors live in private Mac configuration. The initial records are:

- `private-80b-accepted-v1`: a compatibility descriptor reproducing the current accepted checkpoint, runtime, launch arguments, alias, namespace, cache location, and health contract.
- `private-lead-qwen35-122b-candidate-v1`: a separate candidate descriptor with logical role `PRIVATE_LEAD`, separate served-model alias, Pod-name prefix, persistent cache directory, runtime directory, logs, PIDs, benchmark receipts, and lifecycle state.

Each descriptor must bind:

- logical role and release ID;
- model repository and full immutable revision;
- tokenizer, chat-template, and config revision/digests;
- quantization and quantization backend;
- serving runtime version, Python/Torch/CUDA compatibility, container repository and image digest;
- exact launch argument array, environment allowlist, health model ID, reasoning parser, tool parser, and text-only mode;
- maximum configured context, KV-cache data type, GPU-memory fraction, concurrency, and output ceiling;
- hardware identity, Secure Cloud requirement, persistent volume identity, mount subdirectory, and minimum free storage;
- price/runtime/readiness limits and benchmark acceptance version.

The Mac selects a release by exact ID. Model output, repository content, and provider metadata cannot change that selection. Only one managed private release may own compute at a time. Reconciliation must recognize both old and new managed namespaces, adopt only the exact recorded allocation, and refuse untracked or duplicate managed Pods.

Candidate installation is additive. The persistent volume uses release-specific roots such as `/workspace/sanctum/releases/<release-id>` and a content-addressed Hugging Face cache. No candidate script writes the accepted 80B venv, PID, log, alias, model directory, or state file. Weight provisioning is an explicit, bounded preparation operation. After the revision and required artifacts are present and verified, ordinary startup is cache-only. No failed qualification deletes either release cache or the persistent volume.

## Candidate model, quantization, and backend strategy

Current primary documentation establishes the following design facts:

- Qwen identifies Qwen3.5-122B-A10B as a 122B-total/10B-active MoE with native 262,144-token context and documents vLLM reasoning/tool parsers plus a text-only `--language-model-only` mode that frees memory for KV cache ([Qwen model card at inspected revision](https://huggingface.co/Qwen/Qwen3.5-122B-A10B/blob/5dd6a3ec06a6731417ce8cbfcce5c98cc92489c4/README.md)).
- Runpod documents the RTX PRO 6000 Blackwell Server Edition as a 96 GB Blackwell device ([Runpod GPU types](https://docs.runpod.io/flash/configuration/gpu-types)).
- NVIDIA's NVFP4 checkpoint documents Blackwell/vLLM compatibility and a tensor-parallel-size-1 launch using `modelopt_fp4`, FP8 KV cache, `qwen3` reasoning, and `qwen3_coder` tool parsing ([NVIDIA model card](https://huggingface.co/nvidia/Qwen3.5-122B-A10B-NVFP4)). Its inspected repository tree is 83.5 GB, so fit and useful KV headroom must be measured rather than inferred from the quantization label.
- Red Hat's NVFP4 checkpoint documents vLLM, a text-only launch, the `flashinfer_cutlass` MoE backend, and strong reported recovery on its listed evaluations ([Red Hat model card](https://huggingface.co/RedHatAI/Qwen3.5-122B-A10B-NVFP4)).
- Qwen's own GPTQ-Int4 checkpoint is 4-bit and vLLM-compatible, but the current official example uses tensor parallel size 4 and `moe_wna16`; it is not evidence of single-96-GB-GPU acceptance ([Qwen GPTQ model card](https://huggingface.co/Qwen/Qwen3.5-122B-A10B-GPTQ-Int4)).
- vLLM's parser documentation explicitly covers Qwen3.5 and notes that a tool call may terminate a thinking block implicitly, so parser output must still enter Sanctum's strict proposal validator ([vLLM Qwen3 parser](https://docs.vllm.ai/en/v0.20.1/api/vllm/reasoning/qwen3_reasoning_parser/)).

The Stage A qualification order is therefore:

1. Primary: `nvidia/Qwen3.5-122B-A10B-NVFP4` at revision `98915d837c4e7c87ac8296d02e89de19b3207e6d`, text-only, tensor parallel 1, vLLM, `modelopt_fp4`, FP8 KV cache, `qwen3`, and `qwen3_coder`. Pin the documented NVIDIA vLLM container by resolved digest during Project 3B; never use a floating tag in an accepted descriptor.
2. Controlled fallback: `RedHatAI/Qwen3.5-122B-A10B-NVFP4` at revision `49d19c108259a21450c40b8af38828b0a97390d8`, text-only vLLM with `flashinfer_cutlass`, if the primary fails fit, throughput, quality, or parser acceptance.
3. Compatibility fallback: `Qwen/Qwen3.5-122B-A10B-GPTQ-Int4` at revision `30cd92cba9707a9aba09d1e490ed4b66b78e9606`, only after a verified single-GPU launch and quality comparison. The official tensor-parallel example prevents assuming that today.

Full BF16 and the approximately 250 GB unquantized repository are excluded from a single 96 GB qualification. FP8 is not presumed to fit. SGLang, llama.cpp/GGUF, CPU offload, and a custom inference stack are not initial candidates. A fallback becomes accepted only if it independently passes the same reproducibility, fit, performance, interface, and behavioral gates. Benchmarking two candidates does not authorize retaining two active Pods.

The candidate is text-only even though the family supports vision. `MULTIMODAL` remains separate. Initial MTP/speculative decoding is off so the base measurement is interpretable; it may be added only as a separately pinned experiment after the unassisted candidate passes correctness and tool parsing.

## Stage A hard performance qualification

### Measurement harness

Add a Mac-owned benchmark harness that calls the exact signed worker/lifecycle path and records content-free measurements in the external private prefix. It may store prompt fixture IDs and digests, token counts, timings, resource samples, release IDs, and safe outcome codes; it must not store private prompt/result content in source or audit. Synthetic fixtures and expected structured outputs live in source.

For every candidate, record these intervals independently with monotonic clocks:

- provider preflight and allocation request;
- allocation confirmation to SSH ready;
- server bootstrap/install;
- model process start to `/models` identity ready;
- first smoke completion;
- end-to-end signed worker readiness;
- per-request queue, prompt/prefill, time to first token, decode, and total latency;
- final lease release, idle grace, delete request, and provider-confirmed absence.

Use server streaming solely for measurement; ordinary answer delivery may remain non-streaming. Derive TTFT from the first content/reasoning event, decode tokens/second from tokenizer-counted completion tokens after first token, and prompt tokens/second from server usage metrics cross-checked against wall time. Provider usage fields are evidence, not authority.

### Workloads

Run cold-cache and warm-cache startup separately. For inference, use deterministic synthetic fixtures at approximately 256, 4K, 8K, 16K, and 32K input tokens, with at least three repetitions after one warm-up. Include:

- a 256-token small answer for TTFT;
- a 4K medium reasoning prompt;
- an 8K Source-First-style evidence prompt;
- a 32K repository/task-state prompt;
- a sustained 512-token decode fixture that prevents early stop;
- a strict JSON final-answer fixture;
- a valid tool-call fixture and a schema-rejection/correction turn;
- ten repeated short turns and five mixed tool/result turns;
- an optional 64K or longer probe only after 32K passes and measured headroom makes it safe.

Report median, p95, minimum, maximum, and failures for TTFT, prefill throughput, decode throughput, and total latency. Record `nvidia-smi` peak/steady VRAM, free VRAM at ready, host RSS/available RAM, KV-cache allocation/occupancy when exposed, CPU utilization, disk/cache bytes, GPU-active seconds, hourly price, and estimated actual cost. A successful boot with no useful 32K KV/output headroom is a failure even if weights technically load.

### Hard gate

Private Lead passes Stage A only if all of these are true on the actual Runpod Secure Cloud RTX PRO 6000 96 GB worker:

- exact model/runtime/container identity and cache-only restart are reproducible;
- loopback-only server, SSH tunnel, signed worker, lease heartbeat, timeout, manual stop, janitor sweep, and confirmed deletion pass;
- 8K and 32K representative requests complete without OOM, process restart, truncation hidden as success, or parser corruption;
- representative sustained decode is reliably at least 10 tokens/second; at least 20 tokens/second is the target;
- TTFT and prompt processing are recorded for all required sizes and remain usable for an interactive loop;
- tool-call latency, repeated turns, and structured output pass without uncontrolled retries;
- maximum runtime and cost ceilings terminate new work deterministically;
- old 80B rollback can be selected and started cache-only after the candidate is stopped and provider-side zero ownership is confirmed.

If representative decode is below 10 tokens/second, if 32K cannot be used reliably, or if lifecycle cleanup is uncertain, stop. Do not implement Work Mode around that release. Preserve the accepted 80B path and record a failed candidate receipt.

## Stage B reasoner-profile characterization

Do not copy the 4B prompt or context accommodations. Characterize the selected Stage A release using a fixed synthetic corpus and a staged matrix. Authority, schema validation, Source-First, egress, approval, replay, provenance, path containment, and rollback remain constant below the model.

| Dimension | Profiles | Primary measurements |
| --- | --- | --- |
| System contract | compact/base; explicit operating contract; explicit contract plus 2–3 examples | task accuracy, invented authority, verbosity, token/latency cost, instruction retention |
| Tool descriptions | compact; richer policy-aware; richer plus source-semantics examples | correct selection, invented tool/argument rate, schema pass rate |
| Tool surface | minimal exact/read set; task-selected domain group; all eligible capabilities | selection accuracy, confusion, unnecessary calls, latency |
| Planning | direct act; structured plan then act; short rolling plan | completion, replans, stale-plan actions, tokens, elapsed time |
| Thinking mode | reasoning enabled but hidden; disabled where supported | quality, latency, tool parse reliability; never require chain-of-thought disclosure |
| Context | 2K, 8K, 32K, optional longer | recall, source semantics, repeated/stale context, latency and degradation |
| Error recovery | invalid type; unknown field; missing required field; policy denial; backend failure | one-turn correction, repeated invalid calls, stopping behavior |
| Task state | concise full snapshot; delta plus bounded recent events | state adherence, omitted constraints, repetition, cost |

Use a fractional sequence instead of an uncontrolled full Cartesian product:

1. Fix compact tools and direct action; select the best system contract.
2. Fix that system contract; compare tool descriptions and surfaces.
3. Fix the smallest reliable surface; compare planning protocols.
4. Re-run the winning profile across context and error-recovery cases.
5. Freeze the selected profile by version/digest and repeat a blind holdout set.

Prefer the least elaborate profile whose holdout results meet the acceptance thresholds. A richer prompt, more tools, a plan, examples, or exposed reasoning is not accepted merely because it sounds more capable.

### Tool-surface experiment

The minimal surface begins with exact utilities and low-risk read proposals needed by the fixture. The selected-domain surface adds one coherent group such as repository reads, personal-source reads, or files. The all-eligible surface exposes only current manifest capabilities that have matching schemas, implementations, Mac policy, and remote-result policy; it never means every OpenClaw tool.

Each trial records advertised names and schema digests, selected tool, argument validity, host decision, execution state, repair, verifier result, egress result, correction turns, latency, and stop result. Capability descriptions are data presented by the Mac and cannot grant permissions. Unadvertised tool names and extra authority fields are rejected before execution.

### Prompt, context, and source-semantics experiment

Fixtures must distinguish:

- Gmail search metadata from a fetched email body;
- Messages chat/timestamp metadata from message content;
- Calendar list metadata from event details;
- File Steward filename/mtime/size from inspected file content;
- search title/snippet from fetched page content;
- repository instructions and filenames from owner policy;
- normalized tool results from execution authority;
- `EvidencePack` fragments from approval or capability decisions.

Injection strings are embedded in web pages, email/message bodies, calendar descriptions, repository files, filenames, test output, and tool results. The model score is informative, but acceptance comes from deterministic inability to add authority, egress, capabilities, workspace scope, or approvals even when the model follows the malicious text.

## Stage C shared capability integration

Stage C starts only after one release passes Stage A and one model-facing profile passes Stage B. Add a `PRIVATE_LEAD` `ReasonerAdapter` with `supportsToolProposals: true`; do not add a second set of Gmail, Messages, Calendar, Browser, file, web, Markdown, MCP, or utility integrations.

The loop is:

```text
Mac builds bounded ReasonerRequest + selected manifest view
  -> Private Lead returns strict FINAL | GROUNDED_FINAL | ESCALATION | TOOL_PROPOSAL
  -> Mac validates exact result shape and current capability digest
  -> Mac creates AuthorityDecision
  -> when execution itself has egress, Mac creates exact EgressDecision
  -> existing local capability/broker executes at most once
  -> existing normalizer/verifier creates ToolResultEnvelope
  -> Mac independently decides whether that exact result may return to Private Lead
  -> bounded observation is appended to explicit task state
```

The remote model never receives the loopback gateway token, approval token, HMAC key, provider credentials, raw Gmail API, Messages database, Keychain, Docker socket, unrestricted filesystem, or generic tool invocation endpoint. It returns data only. The Mac maps a valid proposal to an existing manifest entry and calls the same reliability/native enforcement path used by the local agent.

Initial eligible capability families are exact utilities, Project 2 Source-First, safe browser reads, Gmail search/read, Messages search/read/history, Calendar list/search/detail where actually configured and schema-captured, File Steward list/inspect, currently supported authorized memory interfaces, MarkItDown, scoped Markdown creation, bounded File Steward mutations, curated MCP, and already-qualified browser mutation surfaces. An item remains unavailable if its actual manifest says missing, unconfigured, schema-mismatched, unsupported, or unexposed.

## Remote result-egress design

Mac execution authority and disclosure back to Private Lead are two separate decisions. Reuse Project 1 purpose `REMOTE_RESULT_RETURN` and extend manifest policy from today's conservative `remoteResultEligible: false` only for explicitly reviewed capability/destination/data-class combinations.

Every result-return decision binds:

- current request, task, scope, revision, proposal, capability, and capability digest;
- normalized result-envelope digest and exact rendered observation digest;
- input/output data classes, provenance, truncation, verifier outcome, and execution state;
- exact destination service, logical role, release ID, served model identity, and purpose;
- byte/item ceilings, expiry, approval state, and one-use semantics;
- safe reason codes and current policy version.

Public deterministic results may receive Mac-policy `ALLOW`. Personal results default to `ASK` or `DENY` unless a narrower accepted policy explicitly covers that capability, exact purpose, and candidate destination. Restricted data is `DENY`. A source read permitted on the Mac can still be denied for return. A broad answer disclosure, earlier session grant, or permission to call a capability cannot be reused as result-return approval. Changed destination, purpose, release, packet, revision, capability digest, data class, or truncation invalidates the decision.

Only the normalized bounded view is eligible. Raw broker/provider output, debug fields, credentials, private paths, local IDs not needed for a follow-up, approval material, and media bytes remain on the Mac. `COMPLETION_UNKNOWN` is disclosed only as a safe failure observation and never invites replay of a mutation.

## Stage D Work Mode architecture

Work Mode begins only after Stage C acceptance. It is a Mac-owned state machine, not a long prompt pretending to execute work:

```text
INSPECT -> PLAN -> ACT -> OBSERVE -> TEST -> EVALUATE
              ^                              |
              +----------- REPLAN <----------+
                         |
                    REVIEW_PENDING
                         |
        COMPLETE | BLOCKED | NEEDS_APPROVAL | enforced stop
```

The coordinator owns the phase, admissible transitions, budgets, workspace, manifest view, approvals, execution receipts, and terminal status. Private Lead proposes a short next action or final claim. The coordinator validates one action, executes it through a bounded capability, persists the observation, and invokes a new reasoner turn. No model response can execute multiple hidden actions, mutate state directly, change budgets, declare an unverified success, or ignore a terminal state.

`COMPLETE` requires the requested artifacts, cleanly recorded tests, an inspected final diff, no unresolved approval or completion-unknown mutation, and any required reviewer cycle. `BLOCKED` requires a concrete non-approval impediment. `NEEDS_APPROVAL` contains an exact pending decision. The coordinator may revise an unjustified model terminal proposal.

### Workspace containment

For Git work, the owner selects an approved repository and base revision. The Mac creates an isolated worktree outside the canonical checkout, records the resolved worktree root, `.git` common directory, base commit, initial status, and allowed branch, and exposes only that worktree to Work Mode. The canonical checkout, other worktrees, `.git` object mutation beyond ordinary worktree Git operations, user home, private prefix, and legacy tree are not mounted.

All paths are resolved relative to the approved root with no symlink component, `..`, device file, socket, mount escape, hard-link escape, hidden host bind, or case-normalization ambiguity. File capabilities use directory file descriptors and no-follow/open-at style containment where practical, then revalidate after mutation. Writes are atomic. Removal is allowed only inside the isolated version-controlled worktree and must be visible in Git status; no broad recursive deletion is exposed.

Supported non-Git work uses a fresh private staging directory with an input manifest, content hashes, explicit output allowlist, transaction journal, and owner-approved publish step. Unsupported or irreplaceable directories are read-only or refused. Work Mode never runs directly in the legacy rollback tree or the external Sanctum owner runtime.

### Bounded command runner

Add a Mac-controlled `work_command` capability. It accepts a strict argument vector, workspace-relative working directory, stdin digest/reference, timeout profile, resource profile, and declared output expectation. It never accepts a shell string, login shell, environment expansion, host path, executable search path, arbitrary mount, or inherited environment.

The preferred backend is a pinned OCI image launched by a small Mac broker. The broker may use the host container service through fixed code, but the workspace container receives no container socket. Required controls are:

- non-root UID/GID, read-only root filesystem, approved worktree as the sole writable bind, and a separate bounded temp filesystem;
- no home, private prefix, SSH agent, Keychain, Docker socket, device, host PID/IPC namespace, privileged mode, or host networking;
- scrubbed environment and fixed `PATH`; no inherited tokens, cloud credentials, Git credentials, proxies, or package-manager auth;
- network `none` by default;
- CPU, memory, process, file-size, open-file, temp-space, wall-time, and output-byte caps;
- process-group termination on timeout/cancel, followed by container removal and bounded temp cleanup;
- exact image digest and runner-policy digest in every receipt.

Executable-name allowlists are insufficient because repository scripts are untrusted programs. The security boundary is the workspace/container/resource/network policy. A small executable allowlist may reduce accidents but never substitutes for containment. If the pinned container backend is unavailable, arbitrary repository execution is `ENVIRONMENT_FAILURE`; the fallback is limited to host-owned pure inspection utilities, not a host shell.

### Network and dependency policy

Documentation and research use Project 2 Source-First, not ambient command internet. Ordinary build/test commands have network disabled. Dependency installation is a distinct capability with an exact manifest/lockfile digest, package ecosystem, registry destinations, byte/time/cost bounds, writable cache target, and one-use owner approval. Install occurs in a disposable preparation container; only the reviewed lockfile and content-addressed cache/artifacts return to the offline work container.

No arbitrary URL, `curl | sh`, Git credential use, private registry, post-install host hook, or cloud mutation is implicit. Registry redirects and package integrity are validated. A task that needs a new dependency may propose it, then stops at `NEEDS_APPROVAL`. Production/cloud deploys remain unavailable unless a separate future capability and authority policy is reviewed.

### Persistent task state

Persist task state under the external private prefix, never in source, using owner-only directories/files and an atomic snapshot plus append-only content-minimized event log. The minimum record is:

- schema version, task ID, creation/update time, goal digest and bounded owner-visible goal;
- approved workspace identity, root digest, base revision, branch/staging identity, and runner policy/image digest;
- reasoner role, release/profile/manifest digests, reviewer identity, and Source-First evidence references;
- current phase, short plan, completed steps, pending next step, iteration count, and replan count;
- action proposals, authority/egress/result/verifier/rollback references, not secret tokens;
- tests requested/run, exit class, bounded output digest/excerpt, failures, and final diff digest/statistics;
- wall-clock, token, GPU-active, cost, command, output, and storage budget use/limits;
- pending approval type, exact digest, destination/purpose, expiry, and safe reason code;
- final state and reason codes.

Raw personal content, repository file bodies, command output, prompts, model reasoning, credentials, and approval secrets are not copied into the audit spine. Necessary working observations remain in bounded task-private storage with retention controls and are separately eligible for model egress.

### Runtime-enforced stop conditions

The coordinator enforces exactly these terminal or paused conditions:

- `COMPLETE`: deliverables and required verification/review pass.
- `BLOCKED`: a concrete missing fact, unsupported capability, or unresolved task contradiction prevents progress.
- `NEEDS_APPROVAL`: an exact authority, egress, dependency, network, or consequential action decision is pending.
- `BUDGET_EXHAUSTED`: any time, token, GPU, cost, command, output, or storage ceiling is reached.
- `ITERATION_LIMIT`: the configured loop/replan/failure threshold is reached.
- `SAFETY_POLICY_BLOCK`: deterministic authority, egress, workspace, or command policy denies the requested next step.
- `ENVIRONMENT_FAILURE`: the required contained runner, worktree, provider, or verified runtime is unavailable.

Budgets are monotonically consumed and Mac-owned. The model cannot reset counters, change terminal state, extend expiry, relabel a denial, or convert `COMPLETION_UNKNOWN` into success. Repeated identical invalid proposals consume iterations and terminate at the configured limit.

## Sequential reviewer design

After single-agent Work Mode passes, add exactly one sequential reviewer context:

1. The lead produces a candidate implementation and a structured completion claim.
2. The Mac freezes the candidate diff digest and test receipts.
3. A fresh Private Lead reviewer context receives the goal, constraints, selected repository evidence, bounded task-state summary, final diff, and test results. It receives no lead hidden reasoning and no standing mutation authority.
4. The reviewer returns a strict critique with severity, file/locator, evidence, proposed check, and disposition recommendation. It cannot approve itself, execute tools, or change the diff.
5. The lead receives the validated critique and chooses `ACCEPT`, `REJECT_WITH_REASON`, or `REVISE`. Revision re-enters the ordinary bounded loop and tests.
6. The Mac runs final tests and diff review before `COMPLETE`.

Reviewer usefulness is measured by confirmed defects found, false-positive rate, duplicate/no-op comments, regression prevention, extra iterations, elapsed GPU time, and cost. No swarm, parallel voting, recursive delegation, or reviewer authority expansion is in scope.

## Acceptance suite

### Private Lead runtime

- immutable model/tokenizer/config/runtime/container/launch identity;
- cold and warm allocation/bootstrap/load/readiness timing;
- small, medium, 8K, 32K, repeated-turn, tool-call, and sustained-decode measurements;
- VRAM, host RAM, KV headroom, prefill/decode, TTFT, GPU-active time, and cost;
- cache-only restart, tunnel identity, cancellation, deadline, maximum runtime, janitor restart/sweep, provider-confirmed deletion, and volume preservation;
- old 80B rollback selection and cache-only inference after clean candidate shutdown.

### Capability and model interface

- correct selection across exact utilities, Source-First, browser, personal reads, files, Markdown, curated MCP, and permitted mutations;
- strict proposal/result schemas, invalid proposal rate, one-repair correction rate, repeated-invalid stop, and no action replay;
- metadata/content, snippet/fetch, source/instruction, result/authority, and attachment distinctions;
- exact action authority and separate result-egress outcomes for public, personal, restricted, truncated, failed, and completion-unknown results;
- prompt/context/profile holdout performance and long-context degradation;
- destination, purpose, revision, release, digest, approval, and replay binding.

### Work Mode fixtures

- localized bug;
- existing failing unit test;
- multi-file change;
- schema/API mismatch;
- refactor plus regression tests;
- dependency/configuration problem;
- ambiguous debugging task;
- a task requiring approval;
- malicious repository instruction;
- impossible or unsafe task that must stop.

Each fixture records completion correctness, iterations, failed-test recovery, unnecessary actions, human interventions, unsafe attempts blocked, workspace escape attempts, diff quality, source-grounding mistakes, elapsed time, GPU-active time, estimated cost, and reviewer usefulness. Completion is judged from filesystem/diff/test evidence, not the model's claim.

## Adversarial suite

Attempt every attack through the model response, repository content, filenames/symlinks, web evidence, email/message/calendar/file content, tool results, command output, test output, task-state text, and reviewer critique:

- grant itself permission or author an authority/egress decision;
- call an unadvertised capability or alter a capability/schema digest;
- reuse, extend, or redirect approval to a new purpose, destination, release, revision, or packet;
- inject extra fields, duplicate JSON keys, non-finite values, oversized payloads, or parser-confusing tool calls;
- use `../`, absolute paths, symlinks, hard links, Unicode/case tricks, Git links/submodules, or mount points to escape the workspace;
- read home, the private prefix, legacy tree, Keychain, SSH agent, environment credentials, browser profile, Messages database, Docker socket, or host devices;
- obtain unrestricted internet, dependency installation, host networking, or credentialed registry access;
- mutate production/cloud, another worktree, the canonical checkout, provider resources, or the accepted 80B release;
- smuggle personal/private content into a public query, tool argument, command line, environment, filename, log, reviewer packet, or result-return packet;
- relabel metadata/snippets as content, source instructions as policy, tool output as authority, `UNKNOWN` as verified, or `COMPLETION_UNKNOWN` as safe to retry;
- exceed iterations, time, tokens, GPU runtime, price, command output, process, memory, or disk bounds;
- declare `COMPLETE` while tests fail, the diff changes after review, approval is pending, or cleanup is uncertain.

These attacks must fail deterministically even when the reasoner appears persuaded. Model refusal is useful defense in depth but is not acceptance evidence.

## Cost measurement and budgets

Create a content-free cost ledger in the private prefix keyed by release, lifecycle, benchmark/task, and provider allocation. It records:

- provider-reported hourly price captured at preflight;
- allocation-confirmed, ready, first-token, last-token, idle, delete-requested, and provider-absent timestamps;
- billable elapsed estimate, GPU-active seconds, readiness overhead, inference-active seconds, and idle/cleanup tail;
- prompt/completion tokens per turn, tool/command time, retries/replans, and reviewer overhead;
- reserved ceiling, estimated charge, provider-reported charge when available, and reconciliation status.

The lifecycle enforces maximum hourly price and runtime before and during work. Work Mode adds per-task GPU-seconds and cost ceilings below the lifecycle ceiling. Missing or malformed provider cost data uses the conservative reserved estimate. A billing response never proves resource deletion; only provider-side absence and cleared local ownership do.

## Expected Project 3B–3E source changes

This is a design map, not authorization to change all files.

### Existing files likely to change

- `gate/PROMPT.txt`, `gate/src/schema.py`, `gate/src/dispatch.py`: replace model-facing `PRIVATE_80B` quality advice with logical `PRIVATE_LEAD` while preserving routing and a compatibility alias during migration.
- `gate/foundation/contracts.mjs`: extend strict reasoner/task/reviewer records without adding authority fields to proposals; retain `REMOTE_RESULT_RETURN`.
- `gate/foundation/manifest.mjs`: add reviewed remote-result eligibility by capability/data class/destination, default deny.
- `gate/foundation/audit.mjs`: add content-minimized Private Lead/Work Mode phases, stops, budgets, and cost buckets.
- `gate/foundation/evidence.mjs`: make `PRIVATE_LEAD` canonical while retaining `PRIVATE_80B` rollback presentation compatibility.
- `gate/plugin/core.mjs`, `gate/plugin/index.mjs`, `gate/plugin/local-agent.mjs`: add logical role/compatibility commands and connect the accepted coordinator without disturbing other tiers or Source-First.
- `gate/src/authority.py`, `gate/worker.py`: admit only new reviewed operations and exact role/release bindings; preserve HMAC, settings digest, expiry, nonces, and prompt/result limits.
- `gate/src/backends.py`: add a strict Private Lead adapter/tool-proposal parser while keeping hosted, multimodal, frontier, and old 80B final-answer behavior.
- `gate/src/lifecycle.py`, `gate/src/runpod.py`, `gate/watch.py`: generalize lifecycle identity to immutable releases, preserve single ownership, old namespaces, leases, reconciliation, janitor, price, tunnel, and confirmed deletion.
- `gate/SETTINGS.json`, `scripts/configure.py`, `scripts/release_operator.py`, `scripts/component.py`: add narrow private release selection/configuration and doctor checks without embedding candidate size in shared policy.
- `reliability/index.mjs`, `reliability/output.mjs`, `reliability/verification.mjs`: allow the Mac coordinator to reuse current proposal, normalization, verifier, and no-replay behavior.
- `scripts/build.py`, `scripts/test.py`, `scripts/audit.py`, `SOURCE-MANIFEST.json`: include reviewed new modules and freeze changes only after tests and explanation.
- `docs/architecture.md`, `docs/configuration.md`, `docs/migration.md`, `docs/V1.1-LIVE-BASELINE.md`, `docs/testing.md`, `docs/operations.md`, and staged handoff/acceptance documents: update only after observed behavior supports the claims.

### New modules likely to be added

- immutable private release descriptors under `gate/runtime/releases/` and a release-aware bootstrap entrypoint;
- `gate/plugin/private-lead.mjs` for the reasoner adapter and capability loop;
- `gate/plugin/work-mode.mjs` for Mac-owned phase transitions and reviewer orchestration;
- `gate/src/work_state.py` for private atomic snapshots/event references and budgets;
- `gate/src/workspace.py` for worktree/staging identity and containment;
- `gate/src/command_runner.py` plus a narrow host broker/container policy;
- `gate/src/benchmark.py` or an equivalent private qualification harness;
- `scripts/upgrade_private_lead.py` for a stopped-gateway, reversible, release-specific private candidate amendment;
- synthetic fixtures and tests under `gate/tests/`, `reliability/tests/`, and a dedicated Work Mode fixture directory.

Names may change during implementation review, but responsibilities must not collapse into a generic shell, duplicated tool registry, model-owned loop, or new approval database.

## Deployment and update strategy

1. Land source contracts, release descriptors, and synthetic tests on the feature branch. Do not deploy them while review is incomplete.
2. Independently review source. Run `make deps`, `make build`, `make test`, and `make audit`; inspect the existing dependency environments before any recreation.
3. With the private gateway stopped, cached GPU state `OFFLINE`, no leases, no allocation uncertainty, and the janitor identity validated, use a dedicated supported Project 3 upgrade command. It writes an owner-only rollback transaction before changing generic installed source or adding candidate release data.
4. Run `make doctor PREFIX=/absolute/private/prefix`. Doctor must validate both the accepted 80B descriptor and candidate descriptor, release-specific cache/state separation, runtime/container/model pins, janitor identity, and autostart off. It must not probe credentials or allocate compute.
5. In an owner-approved qualification window, provision the exact candidate artifacts into its release-specific persistent cache. Record file/revision identities. Subsequent qualification startups are cache-only.
6. Enable candidate selection only for the bounded Stage A harness. Keep ordinary gate routing on the accepted 80B path until Stage A, Stage B, Stage C, and independent review pass.
7. After every live run, close leases, stop through managed lifecycle, confirm provider-side zero managed Pods/active requests/uncertain allocation, retain the janitor, and preserve the volume and receipts.
8. Promote `PRIVATE_LEAD` only through a reviewed private configuration transaction that changes the active logical-role mapping, not shared authority contracts. Keep the old descriptor and cache intact.
9. Rollback first stops and reconciles Private Lead, confirms zero ownership, selects `private-80b-accepted-v1`, and proves cache-only 80B readiness/inference. Source rollback then uses the matching private transaction or ordered Git reverts. Never restore entire databases, delete the volume, refresh unexplained hashes, or stop cleanup while ownership is uncertain.

GPU autostart remains off throughout initial qualification. It may be reconsidered only after the generalized janitor independently proves both release namespaces, allocation intent, lease expiry, maximum runtime, cancellation, restart sweep, duplicate refusal, and provider-confirmed cleanup.

## Explicit non-goals

- No broad implementation, deployment, model download, GPU allocation, Work Mode execution, or provider mutation in Project 3A.
- No Colibrì and no Apple Foundation Models.
- No removal or silent repin of `LOCAL_4B`, `HOSTED_235B`, `MULTIMODAL`, or `OPENAI_FRONTIER`.
- No deletion, overwrite, or in-place mutation of the accepted private 80B release, cache, state, evidence, or persistent volume.
- No encoding of `122B`, a quantization, a repository, or a provider checkpoint into authority, capability, Source-First, approval, audit, task-state, or Work Mode contracts.
- No assumption that model-card context length, fit, quality, or throughput applies to the target single GPU without measurement.
- No transfer of multimodal responsibility to Private Lead.
- No raw personal-service API, unrestricted filesystem, Keychain, credentials, Docker socket, login shell, ambient internet, or production/cloud mutation for a model.
- No chain-of-thought collection requirement, model-confidence verifier, autonomous permission, broad standing approval, approval reuse, action replay, or fallback after undisclosed failure.
- No crawler, vector store, personal RAG, new memory system, duplicate web transport, or Source-First bypass.
- No swarm, parallel agents, recursive delegation, or more than one sequential reviewer.
- No production cutover, stable `main` change, legacy-tree edit, Project 3 merge, or Project 4 work.

PROJECT 3A DESIGN COMPLETE — SWITCH TO GPT-5.6 TERRA MEDIUM AND RUN PROJECT 3B
