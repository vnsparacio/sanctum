# Sanctum V1 compendium

## Purpose and evidence

Sanctum began as VinceAI, a practical privacy-first personal AI project: use a small local model for ordinary work and stronger inference when useful, while keeping authority with the owner. The September 11, 2026 decision freezes the feature set as V1 and shifts work to reproducibility and release engineering.

This compendium separates historical evidence, inspected implementation and candidate behavior. The bootstrap sources summarize 25 historical artifacts. Current source/runtime inspection takes precedence over stale plans, but an implementation discrepancy never justifies weakening an invariant. The original private workspace is not the public source repository.

## The original plan and its changes

The initial handbook proposed a Mac Qwen 4B agent, then AWS GPU/vLLM through a controlled private connection, hosted 235B and eventually a home inference server. It planned incremental personal data and file capabilities behind approval. The central design survived: reasoning engines are interchangeable advisers and the Mac owns consequential authority.

The local foundation changed under real constraints. OpenClaw's broad tool/bootstrap surface consumed too much of a 16K context window and confused 4B. Tool Search was disabled, skills minimized, fetch/search bounded and MLX concurrency/cache/prefill tuned after a real memory failure. More context, more cache and more prompting were not interchangeable fixes.

A controlled OpenClaw upgrade became an inserted milestone. Messages and Gmail were implemented as semantic plugins over fixed local brokers/wrappers, rather than raw native APIs or generic commands. Messages access avoided broad OpenClaw disk permission and sending. Gmail used a dedicated read-only environment; drafts were plain text or create-only local Markdown. File Steward introduced opaque file identities, approved roots, reversible transactions and exact approvals without generic deletion or overwrite.

## Model and router evidence

Real-use benchmarking changed the assumed model ladder. General text 30B did not earn a distinct role; 80B was stronger on structured/technical work and 235B on nuanced qualitative reasoning. Local 4B remained valuable for privacy, tools, ordinary language and some writing/tone cases. A 54-pair generic scaffolding comparison showed limited rescues and regressions, so no universal prompt wrapper was adopted.

The final private-80B comparison contained 203 blinded qualitative cases. After unblinding, 80B won 108, local 4B won 47 and 48 tied. Objective scores were 25/32 versus 21/32. These dated results informed routing; they do not establish universal superiority or grant authority. Both models failed policy and deterministic long-context cases.

Risk-router research is part of the history because it failed. Embedding classifiers, conservative thresholds, separate urgency paths and QwenGuard-style experiments could appear excellent on small curated data yet fail fresh grouped holdouts. Urgency, stakes, quality, privacy and action authorization remained distinct. The production audit supplies probabilistic signals, while deterministic local policy owns the decision.

## Agent correction and source grounding

An early NORMAL gate route called bare MLX. The same model then appeared unable to use Gmail because the request bypassed OpenClaw's tool loop. The correction routes local work through the authenticated OpenClaw agent, explicitly pinned to the local model and loopback service.

Reliability initially focused on actual tool schemas, bounded argument repair, compact output and exact utilities. A schema-valid Gmail call still answered a reservation question using the email's receipt date. Source grounding therefore distinguishes locators, metadata, content and answer facts. `emailReceivedAt`, `messageSentAt`, calendar semantics and `fileModifiedAt` reduce ambiguity, but do not prove that a model selected the right source.

## Current architecture

The gate manages owner/session identity, retained risk, tier exclusions, exact-purpose approval, snapshots, routing and result retrieval. The local path invokes OpenClaw with its bounded tools and existing guards. Private 80B, hosted 235B, visual and frontier paths are tool-free reasoning transports. Audit is a separate role and cannot authorize itself.

Approval binds revision, destination/provider/settings, purpose, expiry and one use. Additional context is selected locally and approved separately. Changing the request invalidates stale approval. Remote outputs remain untrusted. They cannot become browser actions, shell commands, personal-source writes or provider-control requests without a separately authorized local path.

Private compute moved from the original AWS plan to Runpod after capacity delays and model evidence. Its controller persists allocation intent, reconciles ambiguous outcomes, validates readiness/model identity, leases compute across sessions and confirms deletion. Persistent cache storage survives. Independent Mac cleanup can reconcile/delete but cannot allocate or infer. A Mac/network/provider outage can still delay deletion and continue billing; no provider-side hard cutoff is claimed.

## Media and privacy

Attachments are locally normalized and bound to a digest/scope token before disclosure. Images are metadata-stripped and bounded, videos use sparse timestamped frames without audio, and PDFs use bounded text extraction. This preserves the gate's authority over egress instead of letting WebUI preprocessing send data elsewhere first.

The minimal first audit contains the current prompt and compact state/attachment summaries. Raw history, bytes, filenames and personal-source tool results are not sent just to decide whether they may be sent. Stronger models do not automatically inherit local evidence or tools. Hosted provider pins and retention flags are operational controls rather than an independent audit of provider internals.

## Packaging work and deviations found

The release audit found a private development workspace with 272,740 files, no Git repository, directly linked plugins, historical runs, model/dependency caches and live state. All 29 installed gate integrity entries matched. Baseline gate, reliability and MCP tests passed. The candidate was assembled by explicit allowlist while the working paths stayed intact.

Packaging exposed additional assumptions: Calendar and Browser Guard development manifests used latest; contact aliases were embedded in Messages; sockets/home paths and private runtime imports were machine-bound; the old installer required exact predecessor files. The candidate pins the inspected OpenClaw version, moves aliases and roots to private configuration, parameterizes paths/ports and uses synthetic prior-function fixtures in rollback tests.

The canonical build command itself tried to open default OpenClaw state. Builds now use temporary state. Hook-only plugins cannot use the tool-specific metadata generator, so their build path compiles and checks the registration export while semantic tool plugins retain canonical metadata generation and validation. Failed attempts remain in the private worklog/evidence.

## Running, testing and release status

The public operator interface provides dependency setup, build, synthetic tests, audit, isolated setup, doctor, gateway start/status/log location/stop and non-destructive uninstall. Foreground host components are explicit. Generated deployment settings and hashes remain private; setup refuses drift or ambiguous partial installation. Optional capabilities need account/root/permission configuration. The default candidate has no contacts, only exact utility tools, isolated ports and no automatic GPU allocation.

Tests separate contract correctness from real UI, provider and model acceptance. Historical successful GPU runs are not new candidate acceptance. Read acceptance.md for the precise fresh-copy and runtime checks, unresolved gaps, dependency advisory and owner decisions. No live production replacement, credential migration or provider-resource mutation occurred during packaging.

## Limits and next steps

V1 does not solve prompt injection, hallucination, long context, distributed durable jobs or all-container installation. It does not send communications, mutate calendars, expose generic shell/deletion or grant remote Mac control. Those are deliberate boundaries.

Immediate work is release validation, operational use and evidence gathering. Later retrieval, local visual inference, home hardware, planner/executor protocols, broader filesystem workflows or communication writes require separate decisions and evaluations. Learned routing can be revisited only with fresh data and can never become authorization. Keep the history nonlinear, the tests bounded and the authority local.
